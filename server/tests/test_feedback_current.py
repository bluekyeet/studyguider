from fastapi import FastAPI
from fastapi.testclient import TestClient
from marking import marking_router


def test_feedback_read_requires_current_answer_and_scan():
    class Database:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params):
            if 'DISTINCT ON' in sql:
                assert 'm.answer_text=i.answer' in sql
                assert 'm.scan_revision=COALESCE(s.revision,0)' in sql
                assert 's.confirmed IS NULL OR s.confirmed' in sql
                assert 'm.created_at DESC,m.id DESC' in sql
            return self
        def fetchall(self): return []
        def fetchone(self): return None

    app = FastAPI()
    app.include_router(marking_router(Database, lambda: None, None))
    response = TestClient(app).get('/exams/7/answers/2/feedback')
    assert response.status_code == 404
    assert 'current saved answer' in response.json()['detail']
