import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from lessons import lesson_router


class Database:
    def __init__(self):
        self.rows = []
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params):
        if "INSERT INTO lessons" in sql:
            topic, query, lesson, review, status, sources, standards = params
            self.rows.append((len(self.rows) + 1, topic, query, lesson, review, status,
                              json.loads(sources), json.loads(standards), "2026-01-01"))
            self.result = self.rows[-1]
        elif "SELECT 1 FROM topics" in sql:
            self.result = (1,) if params[0] == 1 else None
        elif "WHERE topic_id" in sql:
            self.result = [r for r in reversed(self.rows) if r[1] == params[0]][params[2]:params[2] + params[1]]
        else:
            self.result = next((r for r in self.rows if r[0] == params[0]), None)
        return self

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


def setup(reply, sources=None):
    db = Database()
    app = FastAPI()
    source = {"resource_id": "abc", "filename": "source.pdf", "page": 2, "content": "x" * 5000}
    app.include_router(lesson_router(lambda: db, lambda: None, reply,
        lambda topic, q: [source] if sources is None else sources,
        lambda topic: [{"number": 1, "title": "Standard", "description": "description"}]))
    return TestClient(app), db, source


def test_generation_snapshot_and_history():
    calls = []
    def reply(model, messages):
        calls.append((model, messages))
        return "draft" if model == "education" else "check citations"
    client, db, source = setup(reply)
    response = client.post("/topics/1/lessons", json={"query": " algebra "})
    assert response.status_code == 201
    item = response.json()
    assert item["status"] == "draft" and item["review_status"] == "completed"
    assert len(item["sources"][0]["content"]) == 4000
    assert json.loads(calls[0][1][1]["content"])["evidence"]["sources"] == item["sources"]
    source["content"] = "changed"
    assert client.get("/lessons/1").json() == item
    assert client.get("/topics/1/lessons").json() == [item]
    assert client.get("/lessons/2").status_code == 404
    assert client.get("/topics/2/lessons").status_code == 404
    assert client.get("/topics/1/lessons?limit=101").status_code == 422


def test_review_failure_keeps_draft():
    def reply(model, messages):
        if model == "education-reviewer":
            raise HTTPException(502, "failed")
        return "draft"
    client, _, _ = setup(reply)
    item = client.post("/topics/1/lessons", json={"query": "test"}).json()
    assert item["review"] is None and item["review_status"] == "unavailable"
    assert "not verification" in item["warning"]
    assert client.get("/lessons/1").json() == item


def test_generation_errors_do_not_save():
    client, db, _ = setup(lambda *_: "draft", sources=[])
    assert client.post("/topics/1/lessons", json={"query": "test"}).status_code == 422
    assert not db.rows
    client, db, _ = setup(lambda *_: "x" * 100001)
    assert client.post("/topics/1/lessons", json={"query": "test"}).status_code == 502
    assert client.post("/topics/1/lessons", json={"query": "   "}).status_code == 422
    assert not db.rows
