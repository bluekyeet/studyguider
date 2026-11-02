"""Opt-in real gateway check; one call is retained in normal usage accounting.

Get-Content server/tests/live_stream_usage_check.py -Raw |
  docker compose exec -T -e RUN_LIVE_STREAM_CHECK=yes api python -
"""
import json
import os
import uuid

from app import connect, model_reply_stream

assert os.environ.get("RUN_LIVE_STREAM_CHECK") == "yes", "Explicit gateway-call opt-in required"
task = "acceptance-stream-usage-" + uuid.uuid4().hex[:12]
chunks = list(model_reply_stream("education", [{"role": "user", "content": "Explain frequency in one short English sentence."}], task=task))
text = "".join(json.loads(chunk[5:].strip())["text"] for chunk in chunks)
with connect() as db:
    rows = db.execute("SELECT outcome,response_chars,prompt_tokens,completion_tokens FROM ai_runs WHERE task=%s", (task,)).fetchall()
assert len(rows) == 1, rows
outcome, chars, prompt, completion = rows[0]
assert outcome == "ok" and chars == len(text) and chars > 0, rows
assert prompt is None or (type(prompt) is int and prompt >= 0)
assert completion is None or (type(completion) is int and completion >= 0)
print("STREAM_ACCOUNTING_PASS", {"chunks": len(chunks), "response_chars": chars, "outcome": outcome,
                                 "prompt_tokens": prompt, "completion_tokens": completion})
assert prompt is not None and completion is not None, "Stream succeeded, but gateway omitted complete token usage"
print("GATEWAY_TOKEN_USAGE_PASS")
