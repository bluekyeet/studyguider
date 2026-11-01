import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException
from pydantic import ValidationError

from styles import StyleAnalysis, StyleProfile, style_for_topic, style_router


class StyleTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        connect = MagicMock()
        connect.return_value.__enter__.return_value = self.db
        self.authorised = lambda: None
        self.router = style_router(connect, self.authorised)

    def endpoint(self, method):
        return next(route.endpoint for route in self.router.routes if method in route.methods and route.path == "/subjects/{subject_id}/style-profile")

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
        instructions = model.call_args.args[1][0]["content"]
        self.assertIn("not a summary of the subject content", instructions)
        self.assertIn("teach NEW material using that same method", instructions)
        self.assertIn("cannot be inferred", instructions)

    def test_global_method_applies_across_topics_and_overrides_legacy_profiles(self):
        self.db.execute.return_value.fetchone.return_value = ("old subject", "old topic", "Explain one step at a time")
        for topic in (1, 2):
            self.assertEqual(style_for_topic(self.db, topic), "App-wide teaching method:\nExplain one step at a time")
        self.db.execute.return_value.fetchone.return_value = ("old subject", "old topic", "")
        self.assertEqual(style_for_topic(self.db, 1), "")

    def test_global_profile_read_and_save(self):
        get = next(r.endpoint for r in self.router.routes if r.path == "/style-profile" and "GET" in r.methods)
        put = next(r.endpoint for r in self.router.routes if r.path == "/style-profile" and "PUT" in r.methods)
        self.db.execute.return_value.fetchone.return_value = ("Use small steps",)
        self.assertEqual(get(), {"content": "Use small steps"})
        self.assertEqual(put(StyleProfile(content="Use examples")), {"content": "Use examples"})

    def db_context(self):
        context = MagicMock()
        context.__enter__.return_value = self.db
        return context


if __name__ == "__main__":
    unittest.main()
