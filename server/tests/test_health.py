import sys
import io
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError

from fastapi import HTTPException, UploadFile
from app import LessonRequest, Subject, Topic, delete_subject, health, lesson_draft, model_reply, upload_resource


class HealthTest(unittest.TestCase):
    def test_gateway_requests_non_streaming_json(self):
        response = MagicMock()
        response.read.return_value = b'{"choices":[{"message":{"content":"hello"}}]}'
        with patch.dict("os.environ", {"ROUTER_BASE_URL": "https://example.invalid/v1", "ROUTER_API_KEY": "test"}), \
                patch("app.urllib.request.urlopen") as urlopen, patch("app.log_run") as log_run:
            urlopen.return_value.__enter__.return_value = response
            self.assertEqual(model_reply("education", [{"role": "user", "content": "hi"}]), "hello")
            import json
            self.assertIs(json.loads(urlopen.call_args.args[0].data)["stream"], False)
            log_run.assert_called_once()
            self.assertEqual(log_run.call_args.args[0], "general")

    def test_health(self):
        self.assertEqual(health(), {"status": "ok"})

    def test_subject_deletion_locks_before_checking(self):
        db = MagicMock()
        db.execute.return_value.fetchone.side_effect = [(1,), (False,), (1,)]     # found and locked, not a global subject, deleted
        with patch("app.connect") as connect:
            connect.return_value.__enter__.return_value = db
            delete_subject(1)
        self.assertIn("FOR UPDATE", db.execute.call_args_list[0].args[0])
        self.assertIn("NOT EXISTS", db.execute.call_args_list[2].args[0])

    def test_upload_collision_preserves_existing_file(self):
        resource_id = uuid.uuid4()
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = (1,)
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"UPLOAD_DIR": directory}), patch("app.uuid.uuid4", return_value=resource_id), patch("app.connect") as connect:
            connect.return_value.__enter__.return_value = db
            path = Path(directory) / str(resource_id)
            path.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                upload_resource(1, UploadFile(filename="new.txt", file=io.BytesIO(b"new")), category="extra")
            self.assertEqual(path.read_bytes(), b"existing")

    def test_subject_and_topic_validation(self):
        self.assertEqual(Subject(name="Physics", level=2).level, 2)
        for data in ({"name": "  ", "level": 2}, {"name": "Physics", "level": 4}):
            with self.assertRaises(ValidationError):
                Subject(**data)
        with self.assertRaises(ValidationError):
            Topic(name=" ")

    @patch("app.model_reply", side_effect=["Draft lesson", "Review notes"])
    @patch("app.topic_standards", return_value=[])
    @patch("app.search_resources", return_value=[{"resource_id": "example", "filename": "a.txt", "page": 1, "content": "Evidence"}])
    def test_lesson_stays_draft(self, search, standards, model):
        result = lesson_draft(1, LessonRequest(query="waves"))
        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["review"], "Review notes")
        self.assertEqual([call.args[0] for call in model.call_args_list], ["education", "education-reviewer"])


if __name__ == "__main__":
    unittest.main()
