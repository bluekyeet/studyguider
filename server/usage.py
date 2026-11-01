"""Model call accounting and a small gateway diagnostic endpoint."""
import base64
import logging
import os

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DebugRequest(BaseModel):
    model: str = Field(pattern=r"^(education|education-reviewer)$")
    prompt: str = Field(min_length=1, max_length=20000)
    image_base64: str | None = Field(default=None, max_length=14_000_000)


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
        with psycopg.connect(os.environ.get("DATABASE_URL", "")) as db:
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
