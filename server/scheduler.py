"""Opt-in UTC nightly lesson scheduling; the host owns startup and shutdown.

Pass the existing lesson route's generation callable (topic_id, LessonGeneration)
to run_due/start_scheduler. Claims are at-most-once: inspect running/failed runs
after a crash rather than retrying a potentially already-created lesson.
"""
import logging
import threading
from datetime import datetime, timezone

from lessons import LessonGeneration

log = logging.getLogger(__name__)


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
