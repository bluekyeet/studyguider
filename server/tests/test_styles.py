import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException
from pydantic import ValidationError

from styles import StyleAnalysis, StyleProfile, style_router


class StyleTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        connect = MagicMock()
        connect.return_value.__enter__.return_value = self.db
        self.authorised = lambda: None
        self.router = style_router(connect, self.authorised)

    def endpoint(self, method):
        return next(route.endpoint for route in self.router.routes if method in route.methods)

    def test_read_and_edit_profile(self):
        self.db.execute.return_value.fetchone.return_value = ("",)
        self.assertEqual(self.endpoint("GET")(2), {"subject_id": 2, "content": ""})
        self.db.execute.return_value.fetchone.return_value = ("Use worked examples",)
        self.assertEqual(self.endpoint("PUT")(2, StyleProfile(content="Use worked examples")),
                         {"subject_id": 2, "content": "Use worked examples"})
        self.assertEqual(self.db.execute.call_args.args[1], ("Use worked examples", 2))
        self.assertIn("ON CONFLICT", self.db.execute.call_args.args[0])

    def test_missing_subject_and_validation(self):
        self.db.execute.return_value.fetchone.return_value = None
        for method, args in (("GET", (99,)), ("PUT", (99, StyleProfile(content="")))):
            with self.assertRaises(HTTPException) as error:
                self.endpoint(method)(*args)
            self.assertEqual(error.exception.status_code, 404)
        with self.assertRaises(ValidationError):
            StyleProfile(content="x" * 50001)
        self.assertTrue(all(route.dependencies[0].dependency is self.authorised for route in self.router.routes))

    def test_analyse_passes_slide_evidence_to_model(self):
        self.db.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=("Physics",))),
            MagicMock(fetchall=MagicMock(return_value=[("sample.txt", 1, "A sample slide")])),
        ]
        model = MagicMock(return_value="Worked examples")
        router = style_router(lambda: self.db_context(), self.authorised, model)
        analyse = next(route.endpoint for route in router.routes if route.path.endswith("/analyse"))
        self.assertEqual(analyse(2, StyleAnalysis())["profile"], "Worked examples")
        self.assertIn("A sample slide", model.call_args.args[1][1]["content"])

    def db_context(self):
        context = MagicMock()
        context.__enter__.return_value = self.db
        return context


if __name__ == "__main__":
    unittest.main()
