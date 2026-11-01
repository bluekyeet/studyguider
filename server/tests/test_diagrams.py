"""SVG sanitising for AI diagrams, plus the usage summary shape.

The SVG samples are written for this test.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagrams import _sanitise
from diagrams import diagram_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
import json

SAFE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect x="1" y="1" width="20" height="20" fill="#1E3A8A"/>'
        '<text x="5" y="40">Force</text></svg>')


def test_safe_svg_is_kept_verbatim():
    assert _sanitise(SAFE) == SAFE


def test_fenced_svg_is_unwrapped():
    assert _sanitise("```svg\n" + SAFE + "\n```") == SAFE


def test_prose_around_the_svg_is_dropped():
    assert _sanitise("Here is the diagram:\n" + SAFE + "\nLet me know!") == SAFE


@pytest.mark.parametrize("svg", [
    SAFE.replace("<text", "<script>alert(1)</script><text"),
    SAFE.replace("<rect", '<rect onclick="alert(1)"'),
    SAFE.replace("<svg", '<svg xmlns:xlink="http://www.w3.org/1999/xlink"><image xlink:href="https://e.invalid/a.png"/>'),
    '<!DOCTYPE svg [<!ENTITY x "y">]>' + SAFE,
    SAFE.replace("<text", "<iframe/><text"),
])
def test_unsafe_svg_is_rejected(svg):
    with pytest.raises(ValueError):
        _sanitise(svg)


def test_a_reply_without_svg_is_rejected():
    with pytest.raises(ValueError):
        _sanitise("I cannot draw that.")


def test_oversized_svg_is_rejected():
    with pytest.raises(ValueError):
        _sanitise(SAFE.replace("Force", "x" * 500_001))


@pytest.mark.parametrize("verdict,expected", [
    ({"pass": True, "issues": []}, "passed"),
    ({"pass": True, "issues": ["Unsupported label"]}, "flagged"),
    ({"pass": True}, "flagged"),
    ({"pass": True, "issues": "bad schema"}, "flagged"),
    ({"pass": False, "issues": []}, "flagged"),
])
def test_lesson_diagram_is_grounded_and_only_clean_review_passes(monkeypatch, tmp_path, verdict, expected):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr("diagrams._render", lambda svg: b"test PNG")
    captured = []

    class Database:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()):
            self.sql, self.params = sql, params
            return self
        def fetchone(self):
            if "SELECT name" in self.sql: return ("Waves",)
            if "SELECT lesson" in self.sql: return ("Draft", [{"content": "Source evidence"}], [])
            return (1,) + self.params + ("today",)

    def generate(model, messages, task):
        captured.append(messages[-1]["content"])
        return SAFE

    def review(model, prompt, png, task):
        captured.append(prompt)
        return json.dumps(verdict)

    app = FastAPI()
    app.include_router(diagram_router(Database, lambda: None, generate, review))
    response = TestClient(app).post("/topics/1/diagrams", json={"lesson_id": 2, "description": "Show waves"})
    assert response.status_code == 201
    assert response.json()["status"] == expected
    assert all("Source evidence" in prompt for prompt in captured)
