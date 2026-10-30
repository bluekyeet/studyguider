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

    def execute(self, sql, params):
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
    return {"topic_id": 1, "standard_number": 12345, "year": 2020,
            "question_number": "1(a)", "paper_resource_id": str(uuid4()),
            "paper_page": 2, "schedule_resource_id": str(uuid4()),
            "schedule_page": 1, "verified_against_originals": True}


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
