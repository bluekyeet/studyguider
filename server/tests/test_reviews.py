import unittest
from datetime import date

from pydantic import ValidationError

from reviews import ReviewAnswer, ReviewQuestion, review_router


class ReviewTests(unittest.TestCase):
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
