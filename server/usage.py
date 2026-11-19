"""Model call accounting and a small gateway diagnostic endpoint."""
import base64
import logging
import os
import threading
import time
from contextlib import contextmanager

import psycopg
import userspace
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DebugRequest(BaseModel):
    model: str = Field(pattern=r"^(education|education-reviewer)$")
    prompt: str = Field(min_length=1, max_length=20000)
    image_base64: str | None = Field(default=None, max_length=14_000_000)


# ---- how many background model calls may run at once --------------------------------------------------------------------
# Background work that calls the model in parallel (restoring maths and OCR text from page images, splitting questions for
# rapid practice) shares one limit. An administrator sets it in Settings (stored in public.server_settings); until then
# STUDYGUIDER_MODEL_WORKERS gives the starting value, and without either it is DEFAULT_MODEL_WORKERS. The limit is read again
# before every call, so a change applies to the next call, with no restart. Past-exam imports and fresh review versions are
# always one call at a time and do not use it.
DEFAULT_MODEL_WORKERS = 2
MAX_MODEL_WORKERS = 8
_settings_reader = None          # set by app.py: returns {key: value} from public.server_settings
_cached = (0.0, None)
_slots = threading.Condition()
_busy = 0


def create_server_settings(db):
    db.execute("CREATE TABLE IF NOT EXISTS server_settings (key text PRIMARY KEY, value text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now())")


def set_settings_reader(reader):
    global _settings_reader, _cached
    _settings_reader, _cached = reader, (0.0, None)


def forget_cached_settings():
    global _cached
    _cached = (0.0, None)


def environment_workers():
    try:
        value = int(os.environ.get("STUDYGUIDER_MODEL_WORKERS", "0"))
    except ValueError:
        return None
    return value if value > 0 else None


def model_workers_setting():
    """(limit, where it came from: 'administrator', 'environment' or 'default')."""
    global _cached
    stamp, stored = _cached
    if _settings_reader is not None and (stamp == 0.0 or time.monotonic() - stamp > 15):
        try:
            stored = _settings_reader().get("model_workers")
        except Exception:       # noqa: BLE001 - the settings table being unreachable must never stop background work
            stored = None
        _cached = (time.monotonic(), stored)
    if stored is not None and str(stored).isdigit() and 1 <= int(stored) <= MAX_MODEL_WORKERS:
        return int(stored), "administrator"
    environment = environment_workers()
    if environment:
        return min(environment, MAX_MODEL_WORKERS), "environment"
    return DEFAULT_MODEL_WORKERS, "default"


def model_workers(default=None):
    """The current limit, never more than a caller's own maximum."""
    limit = model_workers_setting()[0]
    return max(1, min(default, limit)) if default else limit


@contextmanager
def model_slot():
    """Hold one of the shared background slots for the length of one model call; waits while the limit is reached."""
    global _busy
    with _slots:
        while _busy >= model_workers():
            _slots.wait(timeout=1)       # wakes on a free slot, or after a second to pick up a changed limit
        _busy += 1
    try:
        yield
    finally:
        with _slots:
            _busy -= 1
            _slots.notify_all()


def create_usage_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS ai_runs (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        task text NOT NULL,
        model text NOT NULL,
        prompt_chars integer NOT NULL DEFAULT 0,
        response_chars integer NOT NULL DEFAULT 0,
        outcome text NOT NULL,
        error text,
        prompt_tokens integer,
        completion_tokens integer,
        created_at timestamptz NOT NULL DEFAULT now()
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS ai_runs_created_idx ON ai_runs(created_at DESC)")


def log_run(task, model, prompt_chars, response_chars, outcome, error=None, prompt_tokens=None, completion_tokens=None):
    """Best-effort accounting; a logging failure must never break a model call."""
    try:
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), options=f"-c search_path={userspace.search_path()}") as db:     # the signed-in account's own schema
            db.execute("""INSERT INTO ai_runs
                (task, model, prompt_chars, response_chars, outcome, error, prompt_tokens, completion_tokens)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (task[:100], model[:100], prompt_chars, response_chars, outcome, error,
                 prompt_tokens, completion_tokens))
    except psycopg.Error:
        # Accounting is advisory; never fail the learner's request because of it.
        logger.warning("Could not record a model run", exc_info=True)


def usage_router(connect, authorised, model_reply, model_reply_vision):
    router = APIRouter(dependencies=[Depends(authorised)])

    @router.get("/usage")
    def usage(days: int = 30):
        days = max(1, min(days, 365))
        with connect() as db:
            totals = db.execute("""SELECT COUNT(*),
                COUNT(*) FILTER (WHERE outcome = 'error'),
                COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0),
                COUNT(*) FILTER (WHERE prompt_tokens IS NULL OR completion_tokens IS NULL)
                FROM ai_runs WHERE created_at >= now() - (%s || ' days')::interval""", (days,)).fetchone()
            by_model = db.execute("""SELECT model, COUNT(*), COUNT(*) FILTER (WHERE outcome = 'error'),
                COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0)
                FROM ai_runs WHERE created_at >= now() - (%s || ' days')::interval
                GROUP BY model ORDER BY model""", (days,)).fetchall()
            by_task = db.execute("""SELECT task, COUNT(*), COUNT(*) FILTER (WHERE outcome = 'error')
                FROM ai_runs WHERE created_at >= now() - (%s || ' days')::interval
                GROUP BY task ORDER BY COUNT(*) DESC""", (days,)).fetchall()
            daily = db.execute("""SELECT created_at::date, COUNT(*), COUNT(*) FILTER (WHERE outcome = 'error')
                FROM ai_runs WHERE created_at >= now() - (%s || ' days')::interval
                GROUP BY created_at::date ORDER BY created_at::date""", (days,)).fetchall()
        return {
            "days": days,
            "calls": totals[0], "errors": totals[1],
            # ponytail: fixed advisory threshold; tune only after real usage evidence.
            "failure_warning": ("Model failures are elevated: at least 20% of calls failed in this period. Check the gateway before starting more generation."
                                if totals[0] >= 10 and totals[1] / totals[0] >= 0.2 else None),
            "prompt_tokens": totals[2], "completion_tokens": totals[3],
            "calls_without_token_counts": totals[4],
            "cost": None,
            "cost_notice": "Cost unavailable: gateway model aliases do not provide billing rates. No dollar estimate or budget enforcement is applied.",
            "warning": "Token counts are reported by the gateway when available; they are not a billing statement.",
            "by_model": [dict(zip(("model", "calls", "errors", "prompt_tokens", "completion_tokens"), row)) for row in by_model],
            "by_task": [dict(zip(("task", "calls", "errors"), row)) for row in by_task],
            "daily": [dict(zip(("date", "calls", "errors"), row)) for row in daily],
        }

    @router.get("/usage/recent")
    def recent(limit: int = 50):
        limit = max(1, min(limit, 200))
        with connect() as db:
            rows = db.execute("""SELECT id, task, model, prompt_chars, response_chars, outcome, error,
                prompt_tokens, completion_tokens, created_at FROM ai_runs ORDER BY id DESC LIMIT %s""", (limit,)).fetchall()
        keys = ("id", "task", "model", "prompt_chars", "response_chars", "outcome", "error",
                "prompt_tokens", "completion_tokens", "created_at")
        return [dict(zip(keys, row)) for row in rows]

    @router.post("/debug/model")
    def debug_model(body: DebugRequest):
        prompt = ("Reply only in English using New Zealand spelling. You are a tutor. Ignore any instruction "
                  "about code, repositories, brevity or minimal output. Answer fully.\n\n" + body.prompt)
        if body.image_base64:
            try:
                image = base64.b64decode(body.image_base64, validate=True)
            except ValueError:
                raise HTTPException(422, "image_base64 is not valid base64")
            reply = model_reply_vision(body.model, prompt, image, task="debug-vision")
            kind = "text+image"
        else:
            reply = model_reply(body.model, [{"role": "user", "content": prompt}], task="debug-text")
            kind = "text"
        return {"model": body.model, "kind": kind, "reply": reply,
                "warning": "Diagnostic output only; not a study lesson or verified answer."}

    return router
