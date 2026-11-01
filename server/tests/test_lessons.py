import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from lessons import lesson_router


def test_automatic_lesson_requires_an_enrolled_topic():
    class EmptyDatabase:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *args): return self
        def fetchone(self): return None

    app = FastAPI()
    app.include_router(lesson_router(EmptyDatabase, lambda: None, None, None, None))
    response = TestClient(app).post("/topics/42/lessons/automatic")
    assert response.status_code == 404


class Database:
    def __init__(self):
        self.rows = []
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=()):
        if "COALESCE(tp.content" in sql:
            # Subject style plus topic override; this fixture uses a subject style only.
            self.result = ("Use worked examples", "") if params[0] == 1 else None
        elif "FROM courses c" in sql:
            self.result = (7, 0, 0) if params[0] == 1 else None
        elif "UPDATE lessons SET completed_at" in sql:
            self.result = ("2026-11-01T00:00:00Z",) if any(r[0] == params[0] for r in self.rows) else None
        elif "SELECT section, revision FROM lesson_progress" in sql:
            self.result = getattr(self, "progress", None)
        elif "INSERT INTO lesson_progress" in sql:
            self.result = None if hasattr(self, "progress") else (1,)
            if self.result:
                self.progress = (params[1], 1)
        elif "UPDATE lesson_progress" in sql:
            self.result = None
            if self.progress[1] == params[2]:
                self.progress = (params[0], params[2] + 1)
                self.result = (self.progress[1],)
        elif "INSERT INTO lesson_answers" in sql:
            self.result = None if hasattr(self, "saved_answer") else (1,)
            if self.result:
                self.saved_answer = params
                self.answer_revision = 1
        elif "UPDATE lesson_answers" in sql:
            if params[5] != self.answer_revision:
                self.result = None
            else:
                self.answer_revision += 1
                self.saved_answer = (params[3], params[4], params[0], params[1], params[2])
                self.result = (self.answer_revision,)
        elif "FROM lesson_answers" in sql:
            a = getattr(self, "saved_answer", None)
            self.result = [(a[1], a[2], a[3], a[4], "2026-11-01", self.answer_revision)] if a and a[0] == params[0] else []
        elif "FROM review_questions" in sql:
            self.result = []
        elif "FROM resources WHERE id = ANY" in sql:
            self.result = [(value,) for value in params[0]]
        elif "INSERT INTO lessons" in sql:
            (topic, query, lesson, review, status, sources, standards,
             review_focus, verdict, course_id, stage) = params
            self.rows.append((len(self.rows) + 1, topic, query, lesson, review, status,
                              json.loads(sources), json.loads(standards),
                              json.loads(review_focus), verdict, 1, "2026-01-01", course_id, stage))
            self.result = self.rows[-1]
        elif "SELECT 1 FROM topics" in sql:
            self.result = (1,) if params[0] == 1 else None
        elif "completed_at IS NOT NULL" in sql:
            self.result = []
        elif "FROM lessons WHERE topic_id" in sql:
            self.result = [r for r in reversed(self.rows) if r[1] == params[0]][params[2]:params[2] + params[1]]
        elif "UPDATE lesson_schedule_runs" in sql:
            self.result = None
        elif "DELETE FROM lessons" in sql:
            found = [r for r in self.rows if r[0] == params[0]]
            self.rows = [r for r in self.rows if r[0] != params[0]]
            self.result = (params[0],) if found else None
        elif "SELECT id FROM lessons WHERE id" in sql:
            self.result = (params[0],) if any(r[0] == params[0] for r in self.rows) else None
        elif "FROM lessons WHERE id" in sql:
            self.result = next((r for r in self.rows if r[0] == params[0]), None)
        else:
            raise AssertionError(sql)
        return self

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


def setup(reply, sources=None):
    db = Database()
    app = FastAPI()
    source = {"resource_id": "abc", "filename": "source.pdf", "page": 2,
              "standard_number": 91171, "content": "x" * 5000}
    def model(model_name, messages, task="general"):
        return reply(model_name, messages)

    app.include_router(lesson_router(lambda: db, lambda: None, model,
        lambda topic, q: [source] if sources is None else sources,
        lambda topic: [{"number": 91171, "title": "Standard", "description": "description"}]))
    return TestClient(app), db, source


def test_generation_snapshot_and_history():
    calls = []

    def reply(model, messages, task="general"):
        calls.append((model, messages, task))
        return "draft" if model == "education" else json.dumps({"pass": True, "issues": []})

    client, db, source = setup(reply)
    response = client.post("/topics/1/lessons", json={"query": " algebra "})
    assert response.status_code == 201
    item = response.json()
    assert item["status"] == "draft" and item["review_status"] == "passed"
    assert item["reviewer_verdict"] == "passed"
    assert item["version"] == 1
    assert "Relevant formulae" in calls[0][1][0]["content"]
    assert len(item["sources"][0]["content"]) == 4000
    assert json.loads(calls[0][1][1]["content"])["evidence"]["sources"] == item["sources"]
    assert json.loads(calls[0][1][1]["content"])["teaching_style"] == "Subject teaching style:\nUse worked examples"
    source["content"] = "changed"
    assert client.get("/lessons/1").json() == item
    assert client.get("/topics/1/lessons").json() == [item]
    assert client.post("/lessons/1/complete").status_code == 200
    assert client.post("/lessons/1/complete").json() == {"completed_at": "2026-11-01T00:00:00Z"}
    assert client.post("/lessons/999/complete").status_code == 404
    assert client.get("/lessons/1/progress").json() == {"section": 0, "revision": 0}
    assert client.put("/lessons/1/progress", json={"section": 2}).status_code == 200
    assert client.put("/lessons/1/progress", json={"section": 3}).status_code == 409
    assert client.put("/lessons/1/progress", json={"section": 3, "revision": 1}).status_code == 200
    assert client.get("/lessons/1/progress").json() == {"section": 3, "revision": 2}
    assert client.put("/lessons/1/answers/section1", json={"question": "Explain force", "answer": "A push", "feedback": "Partly correct"}).status_code == 200
    assert client.get("/lessons/1/answers").json()[0]["answer"] == "A push"
    assert client.put("/lessons/1/answers/section1", json={"question": "Explain force", "answer": "stale"}).status_code == 409
    assert client.put("/lessons/1/answers/section1", json={"question": "Explain force", "answer": "A push or pull", "revision": 1}).status_code == 200
    assert client.get("/lessons/1/answers").json()[0]["answer"] == "A push or pull"
    assert client.put("/lessons/1/answers/bad.key", json={"question": "Why?", "answer": ""}).status_code == 422
    assert client.get("/lessons/999/answers").status_code == 404
    assert client.get("/lessons/2").status_code == 404
    assert client.get("/topics/2/lessons").status_code == 404
    assert client.get("/topics/1/lessons?limit=101").status_code == 422
    assert client.delete("/lessons/1").status_code == 200
    assert client.get("/lessons/1").status_code == 404
    assert client.delete("/lessons/1").status_code == 404


def test_review_failure_keeps_draft():
    def reply(model, messages, task="general"):
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


def test_reviewer_endpoint_is_advisory():
    client, _, _ = setup(lambda *_: "review text")
    response = client.post("/review/lesson", json={"lesson": "draft", "evidence": [],
                                                   "standards": []})
    assert response.status_code == 200
    assert response.json()["status"] == "reviewed"
    assert "advisory" in response.json()["warning"]
