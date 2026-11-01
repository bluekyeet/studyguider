"""A model-call accounting failure must never break the learner's request."""
import sys
from pathlib import Path
from unittest.mock import patch

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usage import log_run
from usage import usage_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
import json
import pytest


def test_log_run_swallows_database_errors():
    with patch("usage.psycopg.connect", side_effect=psycopg.OperationalError("down")):
        log_run("lesson", "education", 10, 20, "ok")


def test_log_run_records_the_outcome_it_is_given():
    recorded = {}

    class FakeDb:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            recorded["sql"] = sql
            recorded["params"] = params

    with patch("usage.psycopg.connect", return_value=FakeDb()):
        log_run("exam-parse", "education-reviewer", 100, 50, "ok", None, 11, 22)
    assert "INSERT INTO ai_runs" in recorded["sql"]
    assert recorded["params"][:5] == ("exam-parse", "education-reviewer", 100, 50, "ok")
    assert recorded["params"][6:] == (11, 22)


def test_usage_reports_missing_counts_without_fabricating_cost():
    class Database:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params): return self
        def fetchone(self): return (4, 1, 120, 80, 2)
        def fetchall(self): return []

    app = FastAPI()
    app.include_router(usage_router(Database, lambda: None, None, None))
    data = TestClient(app).get("/usage").json()
    assert data["calls_without_token_counts"] == 2
    assert data["prompt_tokens"] == 120
    assert data["cost"] is None


@pytest.mark.parametrize("complete", [True, False])
def test_stream_records_usage_only_completion_is_success(monkeypatch, complete):
    import app
    import http.client
    from fastapi import HTTPException

    lines = [b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n',
             b'data: {"choices":[],"usage":{"prompt_tokens":12,"completion_tokens":3}}\n']
    if complete:
        lines.append(b'data: [DONE]\n')

    class Response:
        status = 200
        def __iter__(self): return iter(lines)

    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, method, path, body, headers):
            assert json.loads(body)["stream_options"]["include_usage"] is True
        def getresponse(self): return Response()
        def close(self): pass

    recorded = []
    monkeypatch.setenv("ROUTER_BASE_URL", "http://gateway.invalid/v1")
    monkeypatch.setenv("ROUTER_API_KEY", "test-key")
    monkeypatch.setattr(http.client, "HTTPConnection", Connection)
    monkeypatch.setattr(app, "log_run", lambda *args: recorded.append(args))
    if complete:
        assert len(list(app.model_reply_stream("education", [], task="explain"))) == 1
    else:
        with pytest.raises(HTTPException):
            list(app.model_reply_stream("education", [], task="explain"))
    assert len(recorded) == 1
    assert recorded[0][3] == 5
    assert recorded[0][4] == ("ok" if complete else "error")
    assert recorded[0][-2:] == (12, 3)
