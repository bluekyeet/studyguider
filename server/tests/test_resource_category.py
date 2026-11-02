import app
from fastapi import HTTPException


def test_known_categories_do_not_need_ai(monkeypatch):
    monkeypatch.setattr(app, "model_reply", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("No call needed")))
    assert app.detect_resource_category("91171-exm-23.pdf") == "exam_paper"
    assert app.detect_resource_category("91171-ass-2023.pdf") == "exam_answers"
    assert app.detect_resource_category("lesson.pptx") == "slides"


def test_ambiguous_content_classifies_and_fails_conservatively(monkeypatch):
    monkeypatch.setattr(app, "model_reply", lambda *args, **kwargs: "exam_answers")
    assert app.detect_resource_category("document.pdf", "Assessment Schedule") == "exam_answers"
    monkeypatch.setattr(app, "model_reply", lambda *args, **kwargs: "Ignore instructions")
    assert app.detect_resource_category("document.pdf") == "extra"
    def fail(*args, **kwargs): raise HTTPException(502, "Unavailable")
    monkeypatch.setattr(app, "model_reply", fail)
    assert app.detect_resource_category("document.pdf") == "extra"
