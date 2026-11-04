import json
import unittest
from datetime import date, datetime, timedelta, timezone

from pydantic import ValidationError

from reviews import ReviewAnswer, ReviewQuestion, next_interval, review_router


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.row


class Database:
    def __init__(self):
        self.timestamp = datetime(2026, 10, 31, tzinfo=timezone.utc)
        self.calls = []
        self.answers = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM review_questions q JOIN topics t" in sql:
            return Result((8, "Osmosis is diffusion of water.", [], "osmosis", 1,
                           "Cells", "Biology", 91164))
        if "SELECT question FROM review_questions" in sql:
            return Result(("What is osmosis?",))
        if "INSERT INTO review_answers" in sql:
            self.answers.append(params)
            return Result((42, self.timestamp))
        if "SELECT AVG(mastery)" in sql:
            return Result((0.25,))
        if "UPDATE review_questions" in sql or "UPDATE topics" in sql:
            return Result()
        raise AssertionError(sql)


def test_completed_lessons_automatically_get_reviews_once():
    class ReviewDatabase:
        generated = False
        inserted = []

        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()):
            if "FROM lessons" in sql:
                return Result([] if self.generated else [(1, 2, "Assistant-written lesson", [])])
            if "FROM lesson_answers" in sql:
                return Result([])
            if "INSERT INTO review_questions" in sql:
                self.inserted.append(params)
            elif "UPDATE lessons" in sql:
                self.generated = True
            elif "WHERE q.due_date" in sql:
                return Result([])
            return Result()

    db = ReviewDatabase()
    model_calls = []
    def reply(*args, **kwargs):
        model_calls.append(args)
        return json.dumps([{"question": "What is force?", "expected_answer": "A push or pull.", "concept": "force"}])
    router = review_router(lambda: db, lambda: None, reply)
    due = next(route.endpoint for route in router.routes if route.path == "/review-questions/due")
    due(date.today())
    due(date.today())
    assert len(db.inserted) == 1
    assert len(model_calls) == 1
    assert "Relevant formulae" in model_calls[0][1][0]["content"]
    assert "Do not substitute values" in model_calls[0][1][0]["content"]
    assert db.inserted[0][0] == 2


def make_router(reply=None):
    db = Database()
    calls = []

    def model(model_name, messages, task="general"):
        calls.append((model_name, messages, task))
        return reply if reply is not None else json.dumps(
            {"correct": True, "feedback": "Yes, water moves by diffusion.", "concept": "osmosis"})

    router = review_router(lambda: db, lambda: None, model)
    endpoint = next(r.endpoint for r in router.routes if r.path.endswith("/answers") and "POST" in r.methods)
    return db, calls, endpoint


class ReviewTests(unittest.TestCase):
    def test_self_assessed_intervals(self):
        self.assertEqual([next_interval(0, c) for c in range(1, 6)], [1, 1, 1, 2, 4])
        self.assertEqual([next_interval(8, c) for c in range(1, 6)], [1, 1, 8, 16, 24])
        self.assertEqual(next_interval(36500, 5), 36500)
        self.assertEqual(next_interval(8, 5, correct=False), 1)
        self.assertEqual(next_interval(8, 5, correct=True), 24)

    def test_answer_is_ai_marked_and_rescheduled(self):
        db, calls, endpoint = make_router()
        result = endpoint(7, ReviewAnswer(answer=" water moves ", confidence=4))
        self.assertEqual(result["answer"], "water moves")
        self.assertEqual(result["correct"], True)
        self.assertEqual(result["outcome"], "correct")
        self.assertEqual(result["interval_days"], 16)
        self.assertEqual(result["next_due"], date.today() + timedelta(days=16))
        self.assertEqual(calls[0][0], "education")
        self.assertEqual(calls[0][2], "review-mark")
        payload = json.loads(calls[0][1][1]["content"])
        self.assertEqual(payload["expected_answer"], "Osmosis is diffusion of water.")
        self.assertIn("FOR UPDATE", db.calls[0][0])
        self.assertIn("Pacific/Auckland", db.calls[3][0])

    def test_wrong_answer_returns_tomorrow(self):
        db, calls, endpoint = make_router(reply=json.dumps(
            {"correct": False, "feedback": "No, that is not diffusion.", "concept": "osmosis"}))
        result = endpoint(7, ReviewAnswer(answer="active transport", confidence=5))
        self.assertEqual(result["correct"], False)
        self.assertEqual(result["interval_days"], 1)
        self.assertEqual(result["outcome"], "incorrect")
        self.assertEqual(db.answers[0][3], False)

    def test_invalid_mark_falls_back_to_confidence(self):
        db, calls, endpoint = make_router(reply="not json")
        result = endpoint(7, ReviewAnswer(answer="something", confidence=4))
        self.assertEqual(result["outcome"], "confidence-based")
        self.assertEqual(result["correct"], True)
        self.assertIn("unavailable", result["feedback"])

    def test_validation(self):
        self.assertEqual(ReviewQuestion(question="Why?", due_date="2026-10-31").due_date, date(2026, 10, 31))
        for values in ({"answer": " ", "confidence": 3}, {"answer": "Yes", "confidence": 0}, {"answer": "Yes", "confidence": 6}):
            with self.assertRaises(ValidationError):
                ReviewAnswer(**values)

    def test_routes_require_authentication(self):
        def authorised():
            pass

        router = review_router(None, authorised, lambda *args: "")
        self.assertEqual(len(router.routes), 6)
        self.assertTrue(all(route.dependencies[0].dependency is authorised for route in router.routes))


if __name__ == "__main__":
    unittest.main()


def test_all_questions_lists_due_and_future_questions_with_optional_topic_filter():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    class ListDatabase:
        calls = []

        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()):
            assert "review_questions q" in sql
            self.calls.append(params)
            return Result([(1, 2, "Now?", date(2026, 11, 3), "force", None, 0.5, 1, 2, None),
                           (2, 2, "Later?", date(2026, 12, 1), "", 91171, 0.0, 0, 0, None)])

    app = FastAPI()
    app.include_router(review_router(ListDatabase, lambda: None, None))
    client = TestClient(app)
    rows = client.get("/review-questions?topic_id=2").json()
    assert [r["question"] for r in rows] == ["Now?", "Later?"]
    assert rows[1]["due_date"] == "2026-12-01" and rows[0]["answer_count"] == 2
    assert ListDatabase.calls[-1] == (2, 2, 200, 0)
    client.get("/review-questions")
    assert ListDatabase.calls[-1] == (None, None, 200, 0)
    assert client.get("/review-questions?limit=501").status_code == 422


def test_estimated_grade_needs_enough_answers_and_uses_fixed_bands():
    from reviews import estimate_grade
    assert estimate_grade(0.9, 4) is None
    assert [estimate_grade(m, 5) for m in (0.0, 0.39, 0.4, 0.59, 0.6, 0.79, 0.8, 1.0)] == [
        "Not achieved", "Not achieved", "Achieved", "Achieved", "Merit", "Merit", "Excellence", "Excellence"]
