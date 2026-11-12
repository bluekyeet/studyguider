"""Opt-in UTC nightly lesson scheduling; the host owns startup and shutdown.

Pass the existing lesson route's generation callable (topic_id, LessonGeneration)
to run_due/start_scheduler. Claims are at-most-once for crashed (running) runs: inspect them rather than
retrying a potentially already-created lesson. A run that failed with no lesson saved is retried with backoff.
"""
import logging
import threading

import clock
import userspace
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lessons import LessonGeneration

log = logging.getLogger(__name__)


class Schedule(BaseModel):
    query: str = Field(min_length=1, max_length=200, pattern=r"\S")
    hour_utc: int = Field(ge=0, le=23, strict=True)
    enabled: bool
    timezone: Literal["UTC", "Pacific/Auckland"] = "UTC"


class RunResolution(BaseModel):
    """The learner's decision about a run whose outcome is unknown."""
    action: Literal["link", "abandon"]
    lesson_id: int | None = Field(default=None, gt=0)


def scheduler_router(connect, authorised):
    router = APIRouter(dependencies=[Depends(authorised)])

    @router.put("/topics/{topic_id}/schedule")
    def put_schedule(topic_id: int, body: Schedule):
        with connect() as db:
            row = db.execute("""INSERT INTO lesson_schedules (topic_id, query, hour_utc, enabled, timezone)
                SELECT id, %s, %s, %s, %s FROM topics WHERE id = %s
                ON CONFLICT (topic_id) DO UPDATE SET query = EXCLUDED.query,
                hour_utc = EXCLUDED.hour_utc, enabled = EXCLUDED.enabled, timezone = EXCLUDED.timezone
                RETURNING query, hour_utc, enabled, timezone""",
                (body.query.strip(), body.hour_utc, body.enabled, body.timezone, topic_id)).fetchone()
            if row is None:
                raise HTTPException(404, "Topic not found")
        return {"topic_id": topic_id, "query": row[0], "hour_utc": row[1], "enabled": row[2], "timezone": row[3]}

    @router.get("/topics/{topic_id}/schedule")
    def get_schedule(topic_id: int):
        with connect() as db:
            if not db.execute("SELECT 1 FROM topics WHERE id = %s", (topic_id,)).fetchone():
                raise HTTPException(404, "Topic not found")
            row = db.execute("SELECT query, hour_utc, enabled, timezone FROM lesson_schedules WHERE topic_id = %s", (topic_id,)).fetchone()
        return {"topic_id": topic_id, "query": row[0], "hour_utc": row[1], "enabled": row[2], "timezone": row[3]} if row else None

    @router.get("/topics/{topic_id}/schedule/runs")
    def schedule_runs(topic_id: int):
        with connect() as db:
            if not db.execute("SELECT 1 FROM topics WHERE id = %s", (topic_id,)).fetchone():
                raise HTTPException(404, "Topic not found")
            rows = db.execute("""SELECT r.run_date, r.query, r.status, r.lesson_id, r.error, r.started_at, r.finished_at,
                l.review_status FROM lesson_schedule_runs r LEFT JOIN lessons l ON l.id = r.lesson_id
                WHERE r.topic_id = %s ORDER BY r.run_date DESC""", (topic_id,)).fetchall()
        return [dict(zip(("run_date", "query", "status", "lesson_id", "error", "started_at", "finished_at", "review_status"), row)) for row in rows]

    @router.post("/topics/{topic_id}/schedule/runs/{run_date}/resolve")
    def resolve_run(topic_id: int, run_date: date, body: RunResolution):
        """Settle an unlinked running/failed run by explicit choice; never retries or guesses.

        link: attach a lesson of this topic that the learner has confirmed belongs to the run.
        abandon: record that no lesson came of it. Neither calls a model.
        """
        with connect() as db:
            run = db.execute("""SELECT status, lesson_id, started_at < now() - interval '1 hour'
                FROM lesson_schedule_runs WHERE topic_id = %s AND run_date = %s FOR UPDATE""",
                (topic_id, run_date)).fetchone()
            if run is None:
                raise HTTPException(404, "Run not found")
            if run[0] == "completed" or run[1] is not None:
                raise HTTPException(409, "This run already has a lesson")
            if run[0] == "running" and not run[2]:
                # A live worker may still finish; its own atomic save will fail if this changes the claim.
                raise HTTPException(409, "This run started less than an hour ago and may still be working")
            if body.action == "link":
                if body.lesson_id is None:
                    raise HTTPException(422, "lesson_id is required to link a lesson")
                if not db.execute("SELECT 1 FROM lessons WHERE id = %s AND topic_id = %s", (body.lesson_id, topic_id)).fetchone():
                    raise HTTPException(404, "No such lesson in this topic")
                if db.execute("SELECT 1 FROM lesson_schedule_runs WHERE lesson_id = %s", (body.lesson_id,)).fetchone():
                    raise HTTPException(409, "That lesson is already linked to another run")
                db.execute("""UPDATE lesson_schedule_runs SET status = 'completed', lesson_id = %s, error = NULL,
                    finished_at = COALESCE(finished_at, now()) WHERE topic_id = %s AND run_date = %s""",
                    (body.lesson_id, topic_id, run_date))
            else:
                db.execute("""UPDATE lesson_schedule_runs SET status = 'failed',
                    error = 'Resolved by you: no lesson was produced for this run',
                    finished_at = COALESCE(finished_at, now()) WHERE topic_id = %s AND run_date = %s""",
                    (topic_id, run_date))
        return {"status": "completed" if body.action == "link" else "failed", "run_date": run_date,
                "lesson_id": body.lesson_id if body.action == "link" else None}

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
    db.execute("ALTER TABLE lesson_schedules ADD COLUMN IF NOT EXISTS timezone text NOT NULL DEFAULT 'UTC'")
    db.execute("ALTER TABLE lesson_schedule_runs ADD COLUMN IF NOT EXISTS attempts integer NOT NULL DEFAULT 1")


MAX_FLAGGED_PER_DAY = 3


def waiting_lesson(db, topic_id, zone, today):
    """Today's lesson is an earlier one of this topic: reviewed and never opened (it moves to today instead of piling up
    another), or finished today after being carried over (today's one lesson is done, so no second).
    Lessons that were started but not finished are not carried: the topic gets a fresh lesson instead."""
    return db.execute("""SELECT 1 FROM lessons l WHERE l.topic_id = %s AND l.review_status IN ('passed', 'completed')
        AND (l.created_at AT TIME ZONE %s)::date < %s
        AND ((l.completed_at IS NULL
              AND NOT EXISTS (SELECT 1 FROM lesson_progress p WHERE p.lesson_id = l.id AND p.section > 0)
              AND NOT EXISTS (SELECT 1 FROM lesson_answers a WHERE a.lesson_id = l.id))
             OR (l.completed_at AT TIME ZONE %s)::date = %s) LIMIT 1""",
                      (topic_id, zone, today, zone, today)).fetchone()


def reopen_flagged(db, topic_id, zone, today):
    """Today's lesson failed its review and is hidden, so the topic would show nothing: claim the run again to write
    a replacement, at most MAX_FLAGGED_PER_DAY times a day. Returns the run's query, or None."""
    row = db.execute("""UPDATE lesson_schedule_runs r SET status = 'running', lesson_id = NULL, error = NULL,
        finished_at = NULL, started_at = now() FROM lessons l
        WHERE r.topic_id = %s AND r.run_date = %s AND r.status = 'completed' AND l.id = r.lesson_id
        AND l.review_status = 'flagged'
        AND (SELECT count(*) FROM lessons x WHERE x.topic_id = r.topic_id AND x.review_status = 'flagged'
             AND (x.created_at AT TIME ZONE %s)::date = r.run_date) < %s
        RETURNING r.query""", (topic_id, today, zone, MAX_FLAGGED_PER_DAY)).fetchone()
    return row


MAX_RUN_ATTEMPTS = 10


def retry_failed(db, topic_id, today):
    """Today's run failed before any lesson was saved (the model gateway was down, say): claim it again once its wait
    is over (1 min, 2 min, 4 min ... up to an hour), at most MAX_RUN_ATTEMPTS tries. A run the learner abandoned stays failed.
    Returns the run's query, or None."""
    return db.execute("""UPDATE lesson_schedule_runs r SET status = 'running', error = NULL, finished_at = NULL,
        started_at = now(), attempts = r.attempts + 1
        WHERE r.topic_id = %s AND r.run_date = %s AND r.status = 'failed' AND r.lesson_id IS NULL
        AND r.error NOT LIKE 'Resolved by you%%' AND r.attempts < %s
        AND r.finished_at <= now() - make_interval(secs => least(60 * power(2, r.attempts - 1), 3600))
        RETURNING r.query""", (topic_id, today, MAX_RUN_ATTEMPTS)).fetchone()


MAINTENANCE_EVERY_DAYS = 7


def planned_phase(db, topic_id, today):
    """The study planner's phase for a topic (review_plan.topic_phase): 'learn', 'exam_prep' or 'maintain'."""
    import review_plan
    return review_plan.topic_phase(db, topic_id, today)[0]


def run_due(connect, generate, now=None, phase_of=None):
    """Run today's due schedules once; no catch-up for previous UTC days.

    With `phase_of(db, topic_id, local_date)`, lessons follow the calendar: a topic whose assessments are all past gets a short
    maintenance lesson at most every MAINTENANCE_EVERY_DAYS days instead of a new one each night (reviews keep the knowledge),
    and the phase is passed on so the lesson is written for it (new content, exam preparation or maintenance)."""
    now = now or clock.now()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(timezone.utc)
    with connect() as db:
        # Enrolled courses own their daily schedule; no second opt-in or search text.
        db.execute("""INSERT INTO lesson_schedules (topic_id, query, hour_utc, enabled, timezone)
            SELECT c.topic_id, left(t.name,200), 2, true, 'Pacific/Auckland'
            FROM courses c JOIN topics t ON t.id=c.topic_id WHERE c.active
            ON CONFLICT (topic_id) DO NOTHING""")
        schedules = db.execute("""SELECT topic_id, timezone FROM lesson_schedules
            WHERE enabled AND NOT EXISTS (SELECT 1 FROM courses c
                WHERE c.topic_id=lesson_schedules.topic_id AND NOT c.active)
            ORDER BY topic_id""").fetchall()
    for topic_id, zone in schedules:
        local = now.astimezone(ZoneInfo(zone))
        # Commit the claim before calling external services. The primary key also
        # prevents duplicate work across processes and concurrent scheduler ticks.
        with connect() as db:
            if waiting_lesson(db, topic_id, zone, local.date()):
                continue        # a lesson nobody opened is still waiting; it moves to today instead of piling up another
            phase = phase_of(db, topic_id, local.date()) if phase_of else None
            # A run already claimed today keeps its retries; otherwise a maintenance topic waits for its weekly lesson.
            if phase == "maintain" and not db.execute("SELECT 1 FROM lesson_schedule_runs WHERE topic_id = %s AND run_date = %s",
                                                      (topic_id, local.date())).fetchone() \
                    and db.execute("""SELECT 1 FROM lessons WHERE topic_id = %s
                        AND (created_at AT TIME ZONE %s)::date > %s::date - %s LIMIT 1""",
                                   (topic_id, zone, local.date(), MAINTENANCE_EVERY_DAYS)).fetchone():
                continue
            claim = db.execute("""INSERT INTO lesson_schedule_runs (topic_id, run_date, query, status)
                SELECT topic_id, %s, query, 'running' FROM lesson_schedules
                WHERE topic_id = %s AND enabled AND hour_utc <= %s
                ON CONFLICT (topic_id, run_date) DO NOTHING RETURNING query""",
                (local.date(), topic_id, local.hour)).fetchone()
            if not claim:
                claim = reopen_flagged(db, topic_id, zone, local.date()) or retry_failed(db, topic_id, local.date())
        if not claim:
            continue
        body = LessonGeneration(query=claim[0])
        body._schedule_run = (topic_id, local.date())
        body._phase = phase
        try:
            lesson = generate(topic_id, body)
            lesson_id = lesson["id"]
        except Exception as exc:
            log.exception("Scheduled lesson failed for topic %s on %s", topic_id, local.date())
            with connect() as db:
                db.execute("""UPDATE lesson_schedule_runs SET status = 'failed', error = %s,
                    finished_at = now() WHERE topic_id = %s AND run_date = %s
                    AND status = 'running' AND lesson_id IS NULL""",
                    (str(exc)[:2000] or type(exc).__name__, topic_id, local.date()))
            continue
        if body._schedule_persisted:
            continue
        # ponytail: legacy callbacks may return an already-saved lesson; only the
        # lesson route above guarantees atomic insertion/linkage for new lessons.
        with connect() as db:
            db.execute("""UPDATE lesson_schedule_runs SET status = 'completed', lesson_id = %s,
                finished_at = now() WHERE topic_id = %s AND run_date = %s
                AND status = 'running' AND lesson_id IS NULL""",
                (lesson_id, topic_id, local.date()))


def start_scheduler(connect, generate, interval=60, prepare_reviews=None, user_ids=None, phase_of=planned_phase):
    """Start a daemon worker; return (stop event, thread) for clean shutdown."""
    if interval <= 0:
        raise ValueError("interval must be positive")
    stop = threading.Event()

    def worker():
        while not stop.is_set():
            def tick():
                if prepare_reviews is not None:
                    try:
                        prepare_reviews()
                    except Exception:
                        log.exception("Automatic review preparation failed; continuing lesson schedules")
                run_due(connect, generate, phase_of=phase_of)
            try:
                if user_ids is not None:
                    userspace.each_user(user_ids, tick)        # every account gets its own lessons and reviews
                else:
                    tick()
            except Exception:
                log.exception("Lesson scheduler tick failed")
            stop.wait(interval)

    thread = threading.Thread(target=worker, name="lesson-scheduler", daemon=True)
    thread.start()
    return stop, thread
