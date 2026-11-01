import json

from marking import queue_exam_review
from test_marking import ROW, marking_json


def test_exam_mistake_reuses_source_once_and_rejects_stale_or_uncertain_marks():
    class Database:
        answer = ROW[0]
        origins = set()
        inserts = []
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()):
            self.sql = sql
            if "INSERT INTO review_questions" in sql:
                assert "ON CONFLICT (exam_origin) DO NOTHING" in sql
                if params[-1] not in self.origins:
                    self.origins.add(params[-1])
                    self.inserts.append(params)
            return self
        def fetchone(self):
            return (self.answer,) if "SELECT answer FROM exam_items" in self.sql else None

    db = Database()
    result = json.loads(marking_json())
    schedule = ROW[6]
    for _ in range(2):
        queue_exam_review(lambda: db, 7, 2, ROW, result, schedule)
    assert len(db.inserts) == 1
    assert db.inserts[0][1:3] == (ROW[5], schedule)
    assert json.loads(db.inserts[0][3])[0]["content"] == schedule
    db.answer = "Changed after marking started"
    queue_exam_review(lambda: db, 8, 2, ROW, result, schedule)
    assert len(db.inserts) == 1
    db.answer = ROW[0]
    queue_exam_review(lambda: db, 9, 2, ROW, {**result, "outcome": "uncertain"}, schedule)
    queue_exam_review(lambda: db, 10, 2, ROW, result, schedule, disagreement=True)
    assert len(db.inserts) == 1
