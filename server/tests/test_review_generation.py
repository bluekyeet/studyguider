import json
import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from review_generation import ReviewGeneration, review_generation_router


class ReviewGenerationTests(unittest.TestCase):
    def setUp(self):
        self.authorised = lambda: None
        self.model = Mock(return_value='[" What is osmosis? "]')
        self.search = Mock(return_value=[{"resource_id": 7, "filename": "notes.pdf", "page": 2, "content": "Osmosis is diffusion of water."}])
        self.router = review_generation_router(self.authorised, self.model, self.search)
        self.endpoint = self.router.routes[0].endpoint

    def test_grounded_draft(self):
        result = self.endpoint(3, ReviewGeneration(query=" osmosis "))
        self.assertEqual(result["status"], "generated")
        self.assertEqual(result["questions"][0]["question"], "What is osmosis?")
        self.assertEqual(result["questions"][0]["expected_answer"], "")
        self.assertEqual(result["sources"][0]["page"], 2)
        self.search.assert_called_once_with(3, "osmosis")
        messages = self.model.call_args.args[1]
        self.assertEqual(json.loads(messages[1]["content"])["sources"], result["sources"])
        self.assertIs(self.router.routes[0].dependencies[0].dependency, self.authorised)

    def test_no_sources_or_invalid_model_output(self):
        self.search.return_value = []
        with self.assertRaises(HTTPException) as error:
            self.endpoint(3, ReviewGeneration(query="osmosis"))
        self.assertEqual(error.exception.status_code, 422)
        self.model.assert_not_called()
        self.search.return_value = [{"resource_id": 7, "filename": "n", "page": 1, "content": "text"}]
        for reply in ("not json", "[]", '[" "]', '[42]', '"question"', '["x", "x", "x", "x", "x", "x"]'):
            self.model.return_value = reply
            with self.subTest(reply=reply), self.assertRaises(HTTPException) as error:
                self.endpoint(3, ReviewGeneration(query="osmosis"))
            self.assertEqual(error.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
