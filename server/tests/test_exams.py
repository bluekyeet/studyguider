import json
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from exams import exam_router


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Database:
    def __init__(self):
        self.link = True
        self.resources = True
        self.inserts = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=()):
        if "FROM topic_standards" in sql:
            return Result([(1,)] if self.link else [])
        if "FROM resources" in sql:
            return Result([(params[1],), (params[2],)] if self.resources else [])
        if "INSERT INTO exam_questions" in sql:
            self.inserts.append(params)
            return Result([(1, "2026-01-01T00:00:00Z")])
        return Result([])


def setup_client():
    db = Database()
    app = FastAPI()

    def auth():
        raise HTTPException(401, "Authentication required")

    app.include_router(exam_router(lambda: db, auth))
    return app, auth, db, TestClient(app)


def sample():
    return {"topic_id": 1, "standard_number": 91171, "year": 2017,
            "question_number": "1(a)", "paper_resource_id": str(uuid4()),
            "paper_page": 2, "schedule_resource_id": str(uuid4()),
            "schedule_page": 1, "marks": 15,
            "question_text": "Calculate the change in momentum.",
            "schedule_text": "Achieved: Correct change in momentum.",
            "verified_against_originals": True}


def test_auth_and_manual_registration():
    app, auth, db, client = setup_client()
    assert client.get("/exam-questions").status_code == 401
    app.dependency_overrides[auth] = lambda: None
    body = sample()
    assert client.post("/exam-questions", json=body).status_code == 201
    assert len(db.inserts) == 1
    assert client.get("/exam-questions").json() == []


def test_verification_and_resource_checks():
    app, auth, db, client = setup_client()
    app.dependency_overrides[auth] = lambda: None
    body = sample()
    body["verified_against_originals"] = False
    assert client.post("/exam-questions", json=body).status_code == 422
    body["verified_against_originals"] = True
    body["schedule_resource_id"] = body["paper_resource_id"]
    assert client.post("/exam-questions", json=body).status_code == 422
    body = sample()
    db.link = False
    assert client.post("/exam-questions", json=body).status_code == 404
    db.link = True
    db.resources = False
    assert client.post("/exam-questions", json=body).status_code == 404
    assert not db.inserts


class WorkflowDatabase(Database):
    def __init__(self):
        super().__init__()
        self.questions = {
            1: (1, 1, 91171, 2017, "1(a)", "paper", 2, "schedule", 1,
                "2026-01-01T00:00:00Z", 15, json.dumps([]), "Question", "Schedule", json.dumps([])),
        }
        self.exams = {}

    def execute(self, sql, params=()):
        if "FROM exams e LEFT JOIN exam_items" in sql:
            return Result([(exam_id, "2026-01-01T00:00:00Z", len(items), None, "manual", 15)
                           for exam_id, items in sorted(self.exams.items())])
        if "SELECT id, marks FROM exam_questions WHERE id = ANY" in sql:
            return Result([(i, 15) for i in params[0] if i in self.questions])
        if "INSERT INTO exams" in sql:
            self.exams[1] = []
            return Result([(1, "2026-01-01T00:00:00Z")])
        if "INSERT INTO exam_items" in sql:
            self.exams[params[0]].append([params[1], params[2], None])
            return Result([])
        if "UPDATE exam_items" in sql:
            for item in self.exams.get(params[1], []):
                if item[0] == params[2]:
                    revision = item[3] if len(item) > 3 else 0
                    if params[3] != revision:
                        return Result([])
                    item[2] = params[0]
                    if len(item) == 3: item.append(revision + 1)
                    else: item[3] = revision + 1
                    return Result([(item[0], revision + 1)])
            return Result([])
        if sql.startswith("SELECT revision FROM exam_answer_scans"):
            return Result([])
        if "SELECT 1 FROM exam_items WHERE" in sql:
            return Result([(1,)] if any(item[0] == params[1] for item in self.exams.get(params[0], [])) else [])
        if "SELECT id, created_at, subject_id, kind, total_marks FROM exams" in sql:
            return Result([(params[0], "2026-01-01T00:00:00Z", None, "manual", 15)]
                          if params[0] in self.exams else [])
        if "FROM exam_items i JOIN exam_questions" in sql:
            rows = []
            for item in self.exams[params[0]]:
                question = self.questions[item[0]]
                rows.append(question[:10] + (item[1], item[2]) + question[10:] + ((item[3] if len(item) > 3 else 0), 0))
            return Result(rows)
        return super().execute(sql, params)


def test_exam_workflow_and_missing_questions():
    db = WorkflowDatabase()
    app = FastAPI()
    app.include_router(exam_router(lambda: db, lambda: None))
    client = TestClient(app)
    assert client.get("/exams").json() == []
    assert client.post("/exams", json={"question_ids": []}).status_code == 422
    assert client.post("/exams", json={"question_ids": [1, 1]}).status_code == 422
    assert client.post("/exams", json={"question_ids": [1, 999]}).status_code == 404
    assert not db.exams
    assert client.post("/exams", json={"question_ids": [1]}).status_code == 201
    listed = client.get("/exams").json()
    assert listed[0]["question_count"] == 1 and listed[0]["total_marks"] == 15
    assert client.put("/exams/1/answers/999", json={"answer": "x"}).status_code == 404
    assert client.put("/exams/1/answers/1", json={"answer": "wrong scan", "scan_revision": 99}).status_code == 409
    assert client.put("/exams/1/answers/1", json={"answer": "My answer"}).status_code == 200
    assert client.put("/exams/1/answers/1", json={"answer": "Stale answer"}).status_code == 409
    assert client.put("/exams/1/answers/1", json={"answer": "Revised answer", "revision": 1}).json()["revision"] == 2
    question = client.get("/exams/1").json()["questions"][0]
    assert question["answer"] == "Revised answer"
    assert question["paper_page"] == 2 and question["schedule_page"] == 1
    assert question["marks"] == 15
    assert client.get("/exams/2").status_code == 404


def test_workflow_requires_authentication():
    _, _, _, client = setup_client()
    assert client.post("/exams", json={"question_ids": [1]}).status_code == 401
    assert client.get("/exams").status_code == 401
    assert client.put("/exams/1/answers/1", json={"answer": "x"}).status_code == 401
    assert client.get("/exams/1").status_code == 401
