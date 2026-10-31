import unittest
from datetime import date

from pydantic import ValidationError

from reviews import ReviewAnswer, ReviewQuestion, next_interval, review_router


class ReviewTests(unittest.TestCase):
    def test_self_assessed_intervals(self):
        self.assertEqual([next_interval(0, c) for c in range(1, 6)], [1, 1, 1, 2, 4])
        self.assertEqual([next_interval(8, c) for c in range(1, 6)], [1, 1, 8, 16, 24])
        self.assertEqual(next_interval(36500, 5), 36500)

    def test_answer_locks_and_updates_schedule(self):
        from datetime import datetime, timezone
        from unittest.mock import MagicMock

        db = MagicMock()
        timestamp = datetime(2026, 10, 31, tzinfo=timezone.utc)
        db.execute.return_value.fetchone.side_effect = [(8,), (42, timestamp)]
        connect = MagicMock()
        connect.return_value.__enter__.return_value = db
        router = review_router(connect, lambda: None)
        endpoint = next(r.endpoint for r in router.routes if r.path.endswith('/answers') and 'POST' in r.methods)
        result = endpoint(7, ReviewAnswer(answer=' answer ', confidence=4))
        self.assertEqual(result, {'id': 42, 'question_id': 7, 'answer': 'answer', 'confidence': 4, 'answered_at': timestamp})
        calls = db.execute.call_args_list
        self.assertIn('FOR UPDATE', calls[0].args[0])
        self.assertEqual(calls[1].args[1], (7, 'answer', 4))
        self.assertEqual(calls[2].args[1], (16, 16, 7))
        self.assertIn("Pacific/Auckland", calls[2].args[0])

    def test_validation(self):
        self.assertEqual(ReviewQuestion(question="Why?", due_date="2026-10-31").due_date, date(2026, 10, 31))
        for values in ({"answer": " ", "confidence": 3}, {"answer": "Yes", "confidence": 0}, {"answer": "Yes", "confidence": 6}):
            with self.assertRaises(ValidationError):
                ReviewAnswer(**values)

    def test_routes_require_authentication(self):
        def authorised():
            pass

        router = review_router(None, authorised)
        self.assertEqual(len(router.routes), 4)
        self.assertTrue(all(route.dependencies[0].dependency is authorised for route in router.routes))


if __name__ == "__main__":
    unittest.main()
