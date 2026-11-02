"""Real PostgreSQL checks for scheduled-lesson claims, a killed worker and manual retries.

Run with the current source mounted (no gateway calls, no study data touched):
  docker compose run --rm -T -v "$PWD/server:/app" api python tests/recovery_concurrency_check.py
Everything lives in one uniquely named schema that is dropped at the end. Model calls are
stubbed, so this proves claim/persistence behaviour, not lesson quality. Commit-acknowledgement
loss is not simulated.
"""
import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from threading import Event
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from psycopg import sql

import app
from lessons import LessonGeneration, lesson_router
from scheduler import RunResolution, run_due, scheduler_router

SCHEMA = os.environ.get("RECOVERY_CHECK_SCHEMA") or "recovery_check_" + uuid4().hex
ORIGINAL = app.connect
# 03:00 in Auckland on 2026-11-05, after the 02:00 start.
NIGHT_ONE = datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc)
NIGHT_TWO = datetime(2026, 11, 5, 14, 0, tzinfo=timezone.utc)


def isolated():
    db = ORIGINAL()
    db.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(SCHEMA)))
    return db


class StoppedThread:
    def join(self, timeout):
        pass


def seed():
    with isolated() as db:
        subject = db.execute("INSERT INTO subjects(name, level) VALUES ('Check', 2) RETURNING id").fetchone()[0]
        topics = [db.execute("INSERT INTO topics(subject_id, name) VALUES (%s, %s) RETURNING id", (subject, name)).fetchone()[0]
                  for name in ("Topic A", "Topic B")]
        for topic in topics:
            db.execute("INSERT INTO courses(topic_id) VALUES (%s)", (topic,))
        resource = db.execute("""INSERT INTO resources(id, topic_id, filename, size, status)
            VALUES (gen_random_uuid(), %s, 'check.pdf', 1, 'extracted') RETURNING id""", (topics[0],)).fetchone()[0]
    return topics, str(resource)


def save_lesson(topic_id, text="synthetic lesson"):
    with isolated() as db:
        row = db.execute("""INSERT INTO lessons(topic_id, query, lesson, review_status, sources, standards)
            VALUES (%s, 'q', %s, 'passed', '[]', '[]') RETURNING id""", (topic_id, text)).fetchone()
    return {"id": row[0]}


def runs(night):
    with isolated() as db:
        return {r[0]: r[1:] for r in db.execute(
            "SELECT topic_id, status, lesson_id FROM lesson_schedule_runs WHERE run_date = %s", (night.astimezone(ZoneInfo('Pacific/Auckland')).date(),)).fetchall()}


def check_concurrent_claims(topics):
    calls, lock = [], threading.Lock()

    def generate(topic_id, body):
        with lock:
            calls.append(topic_id)
        time.sleep(0.6)  # long enough for the other scheduler tick to overlap
        return save_lesson(topic_id)

    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in [pool.submit(run_due, isolated, generate, NIGHT_ONE) for _ in range(3)]:
            future.result(timeout=60)
    assert sorted(calls) == sorted(topics), f"each topic must be generated once across 3 ticks, got {calls}"
    state = runs(NIGHT_ONE)
    assert all(v[0] == "completed" and v[1] for v in state.values()), state
    print("PASS: three overlapping scheduler ticks made exactly one lesson per topic", calls)


def check_killed_worker(topics):
    code = (f"import os, sys\nos.environ['RECOVERY_CHECK_SCHEMA']='{SCHEMA}'\nimport app\n"
            "from psycopg import sql\nfrom datetime import datetime, timezone\nfrom scheduler import run_due\n"
            "orig=app.connect\n"
            "def iso():\n    d=orig(); d.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(os.environ['RECOVERY_CHECK_SCHEMA']))); return d\n"
            "run_due(iso, lambda t,b: os._exit(9), datetime(2026,11,5,14,0,tzinfo=timezone.utc))\n")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert result.returncode == 9, (result.returncode, result.stderr[-500:])
    state = runs(NIGHT_TWO)
    stuck = [t for t, v in state.items() if v == ("running", None)]
    assert len(stuck) == 1, f"the killed worker must leave exactly one unlinked running claim, got {state}"
    calls = []

    def generate(topic_id, body):
        calls.append(topic_id)
        return save_lesson(topic_id)

    run_due(isolated, generate, NIGHT_TWO)
    assert stuck[0] not in calls, "an interrupted run must never be retried automatically"
    assert runs(NIGHT_TWO)[stuck[0]] == ("running", None)
    print("PASS: after the worker was killed mid-run its claim stayed 'running' and the provider was not called again", stuck[0])
    return stuck[0]


def check_resolution(stuck_topic, topics):
    router = scheduler_router(isolated, lambda: None)
    resolve = next(r.endpoint for r in router.routes if r.path.endswith("/resolve"))
    night = NIGHT_TWO.astimezone(ZoneInfo('Pacific/Auckland')).date()
    try:
        resolve(stuck_topic, night, RunResolution(action="abandon"))
        raise AssertionError("a run started moments ago must not be resolvable")
    except HTTPException as error:
        assert error.status_code == 409, error.detail
    with isolated() as db:
        db.execute("UPDATE lesson_schedule_runs SET started_at = now() - interval '2 hours' WHERE topic_id = %s AND run_date = %s", (stuck_topic, night))
    lesson = save_lesson(stuck_topic, "found it")
    other = next(t for t in topics if t != stuck_topic)
    try:
        resolve(stuck_topic, night, RunResolution(action="link", lesson_id=save_lesson(other)["id"]))
        raise AssertionError("a lesson from another topic must not link")
    except HTTPException as error:
        assert error.status_code == 404
    answer = resolve(stuck_topic, night, RunResolution(action="link", lesson_id=lesson["id"]))
    assert answer == {"status": "completed", "run_date": night, "lesson_id": lesson["id"]}, answer
    for again in (RunResolution(action="abandon"), RunResolution(action="link", lesson_id=lesson["id"])):
        try:
            resolve(stuck_topic, night, again)
            raise AssertionError("a settled run must not change")
        except HTTPException as error:
            assert error.status_code == 409
    # Abandoning needs a fresh unlinked run.
    with isolated() as db:
        db.execute("""INSERT INTO lesson_schedule_runs(topic_id, run_date, query, status, started_at)
            VALUES (%s, '2026-11-01', 'old', 'running', now() - interval '3 days')""", (stuck_topic,))
    resolve(stuck_topic, date(2026, 11, 1), RunResolution(action="abandon"))
    with isolated() as db:
        row = db.execute("SELECT status, lesson_id FROM lesson_schedule_runs WHERE topic_id=%s AND run_date='2026-11-01'", (stuck_topic,)).fetchone()
    assert row == ("failed", None), row
    print("PASS: explicit resolution links a same-topic lesson or abandons an old run, refuses fresh/settled runs and never calls a model")


def check_manual_idempotency(topics, resource):
    calls, lock = [], threading.Lock()

    def model(model_name, messages, task="general"):
        with lock:
            calls.append(task)
        time.sleep(0.5)
        if model_name == "education-reviewer":
            return json.dumps({"pass": True, "issues": []})
        return ("## Learning goal\nx\n\n### Your Turn 1\nExplain a.\n\n### Your Turn 2\nExplain b.\n\n### Your Turn 3\nExplain c.\n")

    source = {"resource_id": resource, "filename": "check.pdf", "page": 1, "standard_number": None, "content": "evidence"}
    router = lesson_router(isolated, lambda: None, model, lambda topic, q: [source], lambda topic: [])
    post = next(r.endpoint for r in router.routes if r.path == "/topics/{topic_id}/lessons" and "POST" in r.methods)
    key = "manual-" + uuid4().hex
    outcomes = []

    def attempt():
        try:
            outcomes.append(("ok", post(topics[0], LessonGeneration(query="frequency"), key)["id"]))
        except HTTPException as error:
            outcomes.append(("http", error.status_code))

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert sorted(o[0] for o in outcomes) == ["http", "ok"] and [o[1] for o in outcomes if o[0] == "http"] == [409], outcomes
    generated = calls.count("lesson-generate")
    assert generated == 1, f"only one request may reach the provider, got {generated}"
    lesson_id = next(o[1] for o in outcomes if o[0] == "ok")
    replay = post(topics[0], LessonGeneration(query="frequency"), key)
    assert replay["id"] == lesson_id and calls.count("lesson-generate") == 1
    with isolated() as db:
        count = db.execute("SELECT count(*) FROM lessons WHERE topic_id=%s AND query='frequency'", (topics[0],)).fetchone()[0]
    assert count == 1, count
    print("PASS: two simultaneous requests with one key made one lesson and one provider call; a later retry returned the same lesson", lesson_id)


async def main():
    async with app.lifespan(app.app):
        topics, resource = seed()
        check_concurrent_claims(topics)
        stuck = check_killed_worker(topics)
        check_resolution(stuck, topics)
        check_manual_idempotency(topics, resource)


try:
    with ORIGINAL() as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(SCHEMA)))
    app.connect = isolated
    app.start_scheduler = app.start_worker = lambda *args, **kwargs: (Event(), StoppedThread())
    asyncio.run(main())
finally:
    app.connect = ORIGINAL
    with ORIGINAL() as db:
        for (table,) in db.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s", (SCHEMA,)).fetchall():
            db.execute(sql.SQL("DROP TABLE {}.{} CASCADE").format(sql.Identifier(SCHEMA), sql.Identifier(table)))
        db.execute(sql.SQL("DROP SCHEMA IF EXISTS {}").format(sql.Identifier(SCHEMA)))
    print("CLEANUP: disposable schema removed")
