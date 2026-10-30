"""Opt-in UTC nightly lesson scheduling; the host owns startup and shutdown.

Pass the existing lesson route's generation callable (topic_id, LessonGeneration)
to run_due/start_scheduler. Claims are at-most-once: inspect running/failed runs
after a crash rather than retrying a potentially already-created lesson.
"""
import logging
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lessons import LessonGeneration

log = logging.getLogger(__name__)


class Schedule(BaseModel):
    query: str = Field(min_length=1, max_length=200, pattern=r"\S")
    hour_utc: int = Field(ge=0, le=23, strict=True)
    enabled: bool


def scheduler_router(connect, authorised):
    router = APIRouter(dependencies=[Depends(authorised)])

    @router.put("/topics/{topic_id}/schedule")
    def put_schedule(topic_id: int, body: Schedule):
        with connect() as db:
            row = db.execute("""INSERT INTO lesson_schedules (topic_id, query, hour_utc, enabled)
                SELECT id, %s, %s, %s FROM topics WHERE id = %s
                ON CONFLICT (topic_id) DO UPDATE SET query = EXCLUDED.query,
                hour_utc = EXCLUDED.hour_utc, enabled = EXCLUDED.enabled
                RETURNING query, hour_utc, enabled""",
                (body.query.strip(), body.hour_utc, body.enabled, topic_id)).fetchone()
            if row is None:
                raise HTTPException(404, "Topic not found")
        return {"topic_id": topic_id, "query": row[0], "hour_utc": row[1], "enabled": row[2]}

    @router.get("/topics/{topic_id}/schedule")
    def get_schedule(topic_id: int):
        with connect() as db:
            if not db.execute("SELECT 1 FROM topics WHERE id = %s", (topic_id,)).fetchone():
                raise HTTPException(404, "Topic not found")
            row = db.execute("SELECT query, hour_utc, enabled FROM lesson_schedules WHERE topic_id = %s", (topic_id,)).fetchone()
        return {"topic_id": topic_id, "query": row[0], "hour_utc": row[1], "enabled": row[2]} if row else None

    @router.get("/topics/{topic_id}/schedule/runs")
    def schedule_runs(topic_id: int):
        with connect() as db:
            if not db.execute("SELECT 1 FROM topics WHERE id = %s", (topic_id,)).fetchone():
                raise HTTPException(404, "Topic not found")
            rows = db.execute("""SELECT run_date, query, status, lesson_id, error, started_at, finished_at
                FROM lesson_schedule_runs WHERE topic_id = %s ORDER BY run_date DESC""", (topic_id,)).fetchall()
        return [dict(zip(("run_date", "query", "status", "lesson_id", "error", "started_at", "finished_at"), row)) for row in rows]

    return router


def create_scheduler_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS lesson_schedules (
        topic_id bigint PRIMARY KEY REFERENCES topics(id) ON DELETE CASCADE,
        query text NOT NULL CHECK (length(query) BETWEEN 1 AND 200 AND query ~ '\\S'),
        hour_utc smallint NOT NULL CHECK (hour_utc BETWEEN 0 AND 23),
        enabled boolean NOT NULL DEFAULT false
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS lesson_schedule_runs (
        topic_id bigint NOT NULL REFERENCES topics(id) ON DELETE RESTRICT,
        run_date date NOT NULL, query text NOT NULL,
        status text NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
        lesson_id bigint REFERENCES lessons(id) ON DELETE RESTRICT,
        error text, started_at timestamptz NOT NULL DEFAULT now(),
        finished_at timestamptz, PRIMARY KEY (topic_id, run_date)
    )""")


def run_due(connect, generate, now=None):
    """Run today's due schedules once; no catch-up for previous UTC days."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    with connect() as db:
        schedules = db.execute("""SELECT topic_id FROM lesson_schedules
            WHERE enabled AND hour_utc <= %s ORDER BY topic_id""", (now.hour,)).fetchall()
    for (topic_id,) in schedules:
        # Commit the claim before calling external services. The primary key also
        # prevents duplicate work across processes and concurrent scheduler ticks.
        with connect() as db:
            claim = db.execute("""INSERT INTO lesson_schedule_runs (topic_id, run_date, query, status)
                SELECT topic_id, %s, query, 'running' FROM lesson_schedules
                WHERE topic_id = %s AND enabled AND hour_utc <= %s
                ON CONFLICT (topic_id, run_date) DO NOTHING RETURNING query""",
                (now.date(), topic_id, now.hour)).fetchone()
        if not claim:
            continue
        try:
            lesson = generate(topic_id, LessonGeneration(query=claim[0]))
            lesson_id = lesson["id"]
        except Exception as exc:
            log.exception("Scheduled lesson failed for topic %s on %s", topic_id, now.date())
            with connect() as db:
                db.execute("""UPDATE lesson_schedule_runs SET status = 'failed', error = %s,
                    finished_at = now() WHERE topic_id = %s AND run_date = %s""",
                    (str(exc)[:2000] or type(exc).__name__, topic_id, now.date()))
            continue
        with connect() as db:
            db.execute("""UPDATE lesson_schedule_runs SET status = 'completed', lesson_id = %s,
                finished_at = now() WHERE topic_id = %s AND run_date = %s""",
                (lesson_id, topic_id, now.date()))


def start_scheduler(connect, generate, interval=60):
    """Start a daemon worker; return (stop event, thread) for clean shutdown."""
    if interval <= 0:
        raise ValueError("interval must be positive")
    stop = threading.Event()

    def worker():
        while not stop.is_set():
            try:
                run_due(connect, generate)
            except Exception:
                log.exception("Lesson scheduler tick failed")
            stop.wait(interval)

    thread = threading.Thread(target=worker, name="lesson-scheduler", daemon=True)
    thread.start()
    return stop, thread
