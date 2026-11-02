"""Fault injection only: never stop the user's gateway or change its settings."""
import io
import json
import urllib.error

import pytest
from fastapi import HTTPException

import app
from lesson_quality import review_and_revise


def test_gateway_connection_failure_then_same_request_recovers(monkeypatch):
    monkeypatch.setenv("ROUTER_BASE_URL", "http://gateway.invalid/v1")
    monkeypatch.setenv("ROUTER_API_KEY", "synthetic-test-key")
    calls = []
    logged = []
    online = False

    def request(req, timeout):
        calls.append(json.loads(req.data))
        if not online:
            raise urllib.error.URLError("Synthetic connection refused")
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": "Frequency is cycles per second."}}],
                                     "usage": {"prompt_tokens": 10, "completion_tokens": 6}}).encode())

    monkeypatch.setattr(app.urllib.request, "urlopen", request)
    monkeypatch.setattr(app, "log_run", lambda *args: logged.append(args))
    messages = [{"role": "user", "content": "Explain my saved question without changing it."}]
    original = json.dumps(messages)
    with pytest.raises(HTTPException) as failure:
        app.model_reply("education", messages, task="recovery-check")
    assert failure.value.status_code == 502
    assert failure.value.detail == "Model gateway failed or returned an invalid response"
    online = True
    assert app.model_reply("education", messages, task="recovery-check") == "Frequency is cycles per second."
    assert calls[0] == calls[1]
    assert json.dumps(messages) == original
    assert [entry[4] for entry in logged] == ["error", "ok"]


def test_reviewer_outage_preserves_exact_draft_and_can_be_retried():
    draft = ("# Learning goal\nExplain frequency.\n## Explanation\nFrequency is cycles per second.\n"
             "## Worked example\nEight cycles in twenty seconds means 0.4 cycles per second.\n"
             "### Your Turn 1\nWhat does frequency measure?\n"
             "### Your Turn 2\nA wave completes ten cycles in five seconds. Calculate its frequency.\n"
             "### Your Turn 3\nWhat does a frequency of two hertz mean?")
    evidence = {"sources": [{"content": "Frequency is cycles per second."}]}

    def offline(*args, **kwargs):
        raise HTTPException(502, "Synthetic outage")

    preserved, review, status = review_and_revise(draft, evidence, offline)
    assert (preserved, review, status) == (draft, None, "unavailable")
    recovered, review, status = review_and_revise(preserved, evidence,
        lambda *args, **kwargs: '{"pass":true,"issues":[]}')
    assert recovered == draft and status == "passed"
    assert json.loads(review) == {"pass": True, "issues": []}
