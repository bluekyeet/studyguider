from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from exams import exam_router


def test_delete_exam_is_authenticated_and_removes_only_attempt():
    class Database:
        exists = True
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params):
            assert sql == "DELETE FROM exams WHERE id = %s RETURNING id"
            assert params == (7,)
            return self
        def fetchone(self):
            if not self.exists: return None
            Database.exists = False
            return (7,)

    allowed = False
    def authorised():
        if not allowed:
            raise HTTPException(401, "Unauthorised")

    app = FastAPI()
    app.include_router(exam_router(Database, authorised))
    client = TestClient(app)
    assert client.delete("/exams/7").status_code == 401
    assert Database.exists
    allowed = True
    response = client.delete("/exams/7")
    assert response.status_code == 204 and not response.content
    assert client.delete("/exams/7").status_code == 404
