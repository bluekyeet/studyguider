import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from lessons import lesson_router


SYNTHETIC_LESSON = """# Learning goal
Explain frequency.
## Explanation
Frequency is the number of cycles per second.
## Worked example
Eight cycles in twenty seconds means 0.4 cycles per second.
### Your Turn 1
What does frequency measure?
### Your Turn 2
A wave completes ten cycles in five seconds. Calculate its frequency.
### Your Turn 3
What does a frequency of two hertz mean?
"""


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
        elif "SELECT q.concept, count(*) FROM review_answers" in sql:
            assert "same_concept.topic_id=q.topic_id" in sql
            self.result = [("Frequency", 3)]
        elif "FROM review_questions" in sql:
            self.result = []
        elif "FROM resources WHERE id = ANY" in sql:
            self.result = [(value,) for value in params[0]]
        elif "INSERT INTO lesson_requests" in sql:
            requests = self.__dict__.setdefault("requests", {})
            key, topic = params
            if key in requests or topic != 1:
                self.result = None
            else:
                requests[key] = {"topic": topic, "status": "running", "lesson": None}
                self.result = (key,)
        elif "SELECT topic_id, status, lesson_id FROM lesson_requests" in sql:
            row = self.__dict__.get("requests", {}).get(params[0])
            self.result = (row["topic"], row["status"], row["lesson"]) if row else None
        elif "UPDATE lesson_requests" in sql:
            row = self.requests[params[1]]
            row["status"], row["lesson"] = "completed", params[0]
            self.result = None
        elif "DELETE FROM lesson_requests" in sql:
            row = self.requests.get(params[0])
            if row and row["status"] == "running" and row["lesson"] is None:
                del self.requests[params[0]]
            self.result = None
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
        return SYNTHETIC_LESSON if model == "education" else json.dumps({"pass": True, "issues": []})

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
    assert json.loads(calls[0][1][1]["content"])["learner_strengths"] == [{"concept": "Frequency", "correct_answers": 3}]
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


def test_generation_cannot_promote_missing_practice_despite_reviewer_approval():
    client, _, _ = setup(lambda model, messages: "draft" if model == "education"
                         else json.dumps({"pass": True, "issues": []}))
    response = client.post("/topics/1/lessons", json={"query": "frequency"})
    assert response.status_code == 201
    item = response.json()
    assert item["lesson"] == "draft"
    assert item["review_status"] == item["reviewer_verdict"] == "flagged"
    assert any("3–5 Your Turn sections" in issue for issue in json.loads(item["review"])["issues"])


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


def _events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def test_progress_stream_reports_stages_and_sends_only_the_reviewed_lesson():
    reviews = iter([{"pass": False, "issues": ["Fix it"]}, {"pass": True, "issues": []}])

    def reply(model, messages, task="general"):
        if model == "education-reviewer":
            return json.dumps(next(reviews))
        return "DRAFT-ONLY-TEXT" if task == "lesson-generate" else SYNTHETIC_LESSON

    client, db, _ = setup(reply)
    response = client.post("/topics/1/lessons/stream", json={"query": "frequency"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response)
    assert [e["stage"] for e in events[:-1]] == ["sources", "writing", "reviewing", "rewriting", "reviewing", "saving"]
    assert events[-1]["done"] is True and events[-1]["lesson"]["review_status"] == "passed"
    assert events[-1]["lesson"] == client.get("/lessons/1").json()
    assert "DRAFT-ONLY-TEXT" not in response.text
    assert len(db.rows) == 1


def test_progress_stream_reports_errors_without_saving():
    client, db, _ = setup(lambda model, messages: "unused", sources=[])
    events = _events(client.post("/topics/1/lessons/stream", json={"query": "frequency"}))
    assert events[-1]["status"] == 422 and "No matching extracted sources" in events[-1]["error"]
    assert not db.rows

    def broken(model, messages, task="general"):
        raise HTTPException(502, "Model returned nothing")

    client, db, _ = setup(broken)
    events = _events(client.post("/topics/1/lessons/stream", json={"query": "frequency"}))
    assert events[-1] == {"error": "Model returned nothing", "status": 502}
    assert not db.rows


def test_automatic_progress_stream_requires_an_enrolled_topic():
    class EmptyDatabase:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *args): return self
        def fetchone(self): return None

    app = FastAPI()
    app.include_router(lesson_router(EmptyDatabase, lambda: None, None, None, None))
    assert TestClient(app).post("/topics/42/lessons/automatic/stream").status_code == 404


KEY = "retry-key-0001"


def test_idempotency_key_returns_the_saved_lesson_instead_of_generating_again():
    calls = []

    def reply(model, messages, task="general"):
        calls.append(task)
        return SYNTHETIC_LESSON if model == "education" else json.dumps({"pass": True, "issues": []})

    client, db, _ = setup(reply)
    first = client.post("/topics/1/lessons", json={"query": "frequency"}, headers={"Idempotency-Key": KEY})
    assert first.status_code == 201
    used = len(calls)
    again = client.post("/topics/1/lessons", json={"query": "frequency"}, headers={"Idempotency-Key": KEY})
    assert again.status_code == 201 and again.json() == first.json()
    assert len(calls) == used and len(db.rows) == 1  # no second model call or lesson
    other = client.post("/topics/1/lessons", json={"query": "frequency"}, headers={"Idempotency-Key": "another-key-02"})
    assert other.status_code == 201 and len(db.rows) == 2
    # A request without a key keeps the old behaviour: every call makes a lesson.
    assert client.post("/topics/1/lessons", json={"query": "frequency"}).status_code == 201 and len(db.rows) == 3


def test_idempotency_key_is_released_after_a_failure_and_rejected_when_malformed():
    attempts = []

    def reply(model, messages, task="general"):
        attempts.append(1)
        if len(attempts) == 1:
            raise HTTPException(502, "gateway down")
        return SYNTHETIC_LESSON if model == "education" else json.dumps({"pass": True, "issues": []})

    client, db, _ = setup(reply)
    failed = client.post("/topics/1/lessons", json={"query": "x"}, headers={"Idempotency-Key": KEY})
    assert failed.status_code == 502 and not db.rows and not db.requests
    retry = client.post("/topics/1/lessons", json={"query": "x"}, headers={"Idempotency-Key": KEY})
    assert retry.status_code == 201 and len(db.rows) == 1
    assert client.post("/topics/1/lessons", json={"query": "x"}, headers={"Idempotency-Key": "short"}).status_code == 422
    assert client.post("/topics/9/lessons", json={"query": "x"}, headers={"Idempotency-Key": "missing-topic-1"}).status_code == 404


def test_idempotency_key_in_progress_or_for_another_topic_is_a_conflict():
    client, db, _ = setup(lambda model, messages: "unused")
    db.requests = {KEY: {"topic": 1, "status": "running", "lesson": None}}
    running = client.post("/topics/1/lessons", json={"query": "x"}, headers={"Idempotency-Key": KEY})
    assert running.status_code == 409 and "already running" in running.json()["detail"]
    db.requests[KEY]["topic"] = 2
    assert client.post("/topics/1/lessons", json={"query": "x"}, headers={"Idempotency-Key": KEY}).status_code == 409
