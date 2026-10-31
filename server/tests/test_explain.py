import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from explain import explain_router


class Database:
    def __init__(self, row):
        self.row = row

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params):
        if "COALESCE(tp.content" in sql:
            # Subject style plus topic override lookup; tests use none.
            self.found = ("", "")
            return self
        assert "FROM lessons l WHERE l.id = %s" in sql
        self.found = self.row if params == (1,) else None
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return self.found


def client_for(row, reply, authorised=lambda: None):
    app = FastAPI()
    app.include_router(explain_router(lambda: Database(row), authorised, reply))
    return TestClient(app)


def test_explanation_uses_saved_snapshots_and_warns():
    sources = [{"resource_id": "abc", "page": 2, "content": "saved evidence"}]
    calls = []
    def reply(model, messages, task="general"):
        calls.append((model, messages))
        return "Explanation [abc, page 2]"
    client = client_for((1, "query", "unverified draft", sources, [{"number": "1"}]), reply)
    response = client.post("/lessons/1/explain", json={"question": " Why? "})
    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert "not verified" in response.json()["warning"]
    assert calls[0][0] == "education"
    payload = json.loads(calls[0][1][1]["content"])
    assert payload == {"question": "Why?", "lesson_query": "query", "lesson": "unverified draft",
                       "sources": sources, "standards": [{"number": "1"}], "teaching_style": ""}
    assert "not evidence" in calls[0][1][0]["content"]


def test_errors_and_authorisation():
    row = (1, "query", "lesson", [{"content": "evidence"}], [])
    client = client_for(row, lambda *args, **kwargs: " ")
    assert client.post("/lessons/2/explain", json={"question": "Why?"}).status_code == 404
    assert client.post("/lessons/1/explain", json={"question": "   "}).status_code == 422
    assert client.post("/lessons/1/explain", json={"question": "Why?"}).status_code == 502
    assert client_for((1, "q", "l", [], []), lambda *args, **kwargs: "answer").post(
        "/lessons/1/explain", json={"question": "Why?"}).status_code == 422
    assert client_for(row, lambda *args, **kwargs: "x" * 100001).post(
        "/lessons/1/explain", json={"question": "Why?"}).status_code == 502
    def deny():
        raise HTTPException(401, "Unauthorised")
    assert client_for(row, lambda *args, **kwargs: "answer", deny).post(
        "/lessons/1/explain", json={"question": "Why?"}).status_code == 401
