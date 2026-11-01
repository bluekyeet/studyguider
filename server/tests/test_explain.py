"""Tests for grounded paragraph explanations and streaming failures."""
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from explain import explain_router


class FakeDB:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, sql, params=()):
        if "FROM lessons" in sql:
            self._last = "lesson"
        elif "COALESCE" in sql or "style" in sql.lower():
            self._last = "style"
        return self
    def fetchone(self):
        if getattr(self, "_last", None) == "style":
            return None
        # topic_id=1, query, lesson, sources, standards
        return (1, "motion", "Lesson body here.", [{"id": "r1", "page": 1}], [{"number": 91171}])


def make_client(stream_fn=None):
    app = FastAPI()
    replies = []

    def fake_reply(model, messages, task="general", **kw):
        replies.append(task)
        return "Correct. The answer is 9.8 m/s²."

    app.include_router(explain_router(FakeDB, lambda: None, fake_reply, stream_fn))
    return TestClient(app), replies


def test_explain_returns_explanation():
    client, replies = make_client()
    resp = client.post("/lessons/1/explain", json={"question": "What is g?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "explanation" in body
    assert body["status"] == "draft"
    assert "warning" in body
    assert "explain" in replies


def test_explain_paragraph_requires_paragraph_field():
    client, _ = make_client()
    resp = client.post("/lessons/1/explain/paragraph", json={"question": "What is g?"})
    assert resp.status_code == 422


def test_explain_paragraph_includes_focus_in_payload():
    captured = []
    app = FastAPI()

    def fake_reply(model, messages, task="general", **kw):
        captured.append(messages)
        return "The paragraph discusses acceleration due to gravity."

    app.include_router(explain_router(FakeDB, lambda: None, fake_reply))
    client = TestClient(app)
    resp = client.post("/lessons/1/explain/paragraph",
                       json={"question": "Explain this", "paragraph": "g = 9.8 m/s²"})
    assert resp.status_code == 200
    import json
    payload = json.loads(captured[0][-1]["content"])
    assert payload.get("paragraph_in_focus") == "g = 9.8 m/s²"
    assert "instruction" in payload


def test_explain_missing_lesson_returns_404():
    class NoLesson:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *a, **kw): return self
        def fetchone(self): return None

    app = FastAPI()
    app.include_router(explain_router(NoLesson, lambda: None, lambda *a, **kw: "x"))
    client = TestClient(app)
    assert client.post("/lessons/99/explain", json={"question": "test"}).status_code == 404


@pytest.mark.parametrize("failure", [None, HTTPException(502, "upstream failed"), OSError("connection lost")])
def test_explain_stream_completion_and_interruption(failure):
    def stream(model, messages, task):
        yield 'data: {"text": "First paragraph."}\n\n'
        if failure:
            raise failure
        yield 'data: {"text": " Second paragraph."}\n\n'

    client, replies = make_client(stream)
    response = client.post("/lessons/1/explain?stream=1", json={"question": "Explain g"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:")]
    assert events[0] == {"text": "First paragraph."}
    assert ("error" in events[-1]) if failure else events[-1] == {"done": True}
    assert not replies


def test_stream_does_not_silently_ignore_save_to_notes():
    client, _ = make_client(lambda *args, **kwargs: iter(()))
    response = client.post("/lessons/1/explain?stream=1",
                           json={"question": "Explain g", "save_to_notes": True})
    assert response.status_code == 422


@pytest.mark.parametrize("diagram,status", [
    (("Force arrows", "<svg>labelled force</svg>", "passed"), 200),
    (("Force arrows", "<svg/>", "flagged"), 422),
    (None, 404),
])
def test_diagram_explanation_is_lesson_scoped_and_grounded(diagram, status):
    captured = []

    class DiagramDB(FakeDB):
        def execute(self, sql, params=()):
            if "FROM diagrams" in sql:
                assert "lesson_id = %s AND topic_id = %s" in sql
                assert params == (9, 1, 1)
                self._last = "diagram"
                return self
            return super().execute(sql, params)

        def fetchone(self):
            return diagram if self._last == "diagram" else super().fetchone()

    def reply(model, messages, **kwargs):
        captured.append(json.loads(messages[-1]["content"]))
        return "The arrow represents force."

    app = FastAPI()
    app.include_router(explain_router(DiagramDB, lambda: None, reply))
    response = TestClient(app).post("/lessons/1/explain", json={"question": "Explain arrows", "diagram_id": 9})
    assert response.status_code == status
    if status == 200:
        assert captured[0]["diagram_in_focus"]["svg"] == diagram[1]
        assert captured[0]["sources"]
        assert "unverified AI illustration" in captured[0]["instruction"]
    else:
        assert not captured


def test_diagram_id_must_be_positive():
    client, calls = make_client()
    assert client.post("/lessons/1/explain", json={"question": "Explain", "diagram_id": 0}).status_code == 422
    assert not calls
