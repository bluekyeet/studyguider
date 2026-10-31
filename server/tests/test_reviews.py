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
        self.assertEqual(len(router.routes), 4)
        self.assertTrue(all(route.dependencies[0].dependency is authorised for route in router.routes))


if __name__ == "__main__":
    unittest.main()
