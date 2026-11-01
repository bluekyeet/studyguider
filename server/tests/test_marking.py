import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from marking import grade_for, marking_router, clean_transcription, _validate, uses_ncea_question_scale


ROW = (
    "My answer", "1(a)", 91171, 2017, 15,
    "Question 1(a): Explain the change in momentum.",
    "Achieved: Correct change in momentum.",
    "paper-id", 2, "Paper page text",
    "schedule-id", 3, "Achieved: Correct change in momentum. Merit: Correct force.",
    "Demonstrate understanding of mechanics.", "Mechanics", "Physics", 2,
)


def marking_json(marks=5, available=15, outcome="not_achieved", quote="Correct change in momentum."):
    return json.dumps({
        "marks_awarded": marks,
        "marks_available": available,
        "outcome": outcome,
        "feedback": "Feedback linked to the schedule.",
        "evidence": [{"quote": quote, "explanation": "Schedule criterion.", "marks": marks}],
        "missing": ["Correct force."],
        "confidence": 0.8,
    })


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.row or []


class DB:
    def __init__(self, row=ROW):
        self.row = row
        self.markings = {}
        self.overrides = {}
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=()):
        self.queries.append((sql, params))
        if "UPDATE markings SET answer_text" in sql:
            return Result()
        if "SELECT image, confirmed" in sql:
            return Result()
        if "COALESCE(tp.content" in sql:
            # Subject style plus topic override; this fixture uses neither.
            return Result(("", ""))
        if "resource_pages paper" in sql:
            return Result(self.row)
        if "marking_overrides" in sql and "FROM exam_items i JOIN exam_questions q" in sql:
            first = self.markings.get((params[0], 2, None, "first"))
            return Result([(2, 15, "1(a)", first, None)])
        if "SELECT result FROM markings" in sql:
            kind = "second" if "kind = 'second'" in sql else "first"
            found = self.markings.get((params[0], params[1], params[2], kind))
            return Result((found,) if found is not None else None)
        if "SELECT 1 FROM exam_items" in sql:
            return Result((1,))
        if "SELECT outcome, note FROM marking_overrides" in sql:
            return Result(self.overrides.get((params[0], params[1])))
        if "INSERT INTO markings" in sql:
            kind = "second" if "'second'" in sql else "first"
            self.markings[(params[0], params[1], params[2], kind)] = json.loads(params[3])
            return Result()
        if "INSERT INTO marking_overrides" in sql:
            self.overrides[(params[0], params[1])] = (params[2], params[3])
            return Result()
        if "SELECT total_marks FROM exams" in sql:
            return Result((15,))
        raise AssertionError(sql)


def make_client(row=ROW, replies=None, auth=None):
    calls = []
    db = DB(row)

    def model(model_name, messages, task="general"):
        calls.append((model_name, messages, task))
        if replies is not None:
            return replies.pop(0)
        return marking_json()

    app = FastAPI()
    app.include_router(marking_router(lambda: db, auth or (lambda: None), model))
    return TestClient(app), calls, db


def test_grade_boundaries():
    assert grade_for(15, 15) == "excellence"
    assert grade_for(11, 15) == "merit"
    assert grade_for(8, 15) == "achieved"
    assert grade_for(7, 15) == "not_achieved"
    assert grade_for(0, 0) == "uncertain"


def test_ncea_descriptor_scale_is_not_percentage_graded():
    schedule = "N1 N2 A3 A4 M5 M6 E7 E8: Correct change in momentum."
    assert uses_ncea_question_scale(schedule)
    assert not uses_ncea_question_scale("Achieved: correct answer")
    for score, outcome in ((2, "not_achieved"), (3, "achieved"), (5, "merit"), (7, "excellence")):
        result = _validate(marking_json(marks=score, available=8), schedule, 8)
        assert result.outcome == outcome


def test_rejects_contaminated_ocr_and_accepts_fenced_marking():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        clean_transcription('```text\n[No answer found]\n```\nLazier alternative: Manual transcription.\nskipped: Full page OCR pipeline')
    with pytest.raises(HTTPException):
        clean_transcription('[No answer found]')
    assert clean_transcription('```text\n(a) F = 2 N\n```') == '(a) F = 2 N'
    assert _validate('```json\n' + marking_json() + '\n```', ROW[12], 15).marks_awarded == 5


def test_scan_rejects_invalid_images_before_calling_vision():
    calls = []
    app = FastAPI()
    app.include_router(marking_router(lambda: DB(ROW), lambda: None, lambda *a, **k: None,
        lambda *a, **k: calls.append(a)))
    client = TestClient(app)
    response = client.post("/exams/1/answers/2/scan", files={"file": ("answer.png", b"not an image", "image/png")})
    assert response.status_code == 422
    assert not calls


def test_feedback_quotes_schedule_and_reports_pages():
    client, calls, _ = make_client()
    response = client.post("/exams/1/answers/2/feedback")
    assert response.status_code == 200
    result = response.json()
    assert result["experimental"] is True
    assert result["schedule"]["page"] == 3
    assert result["paper"]["page"] == 2
    assert result["marks_awarded"] == 5
    assert result["outcome"] == "not_achieved"
    payload = json.loads(calls[0][1][1]["content"])
    assert payload["schedule_text"].startswith("Achieved: Correct change")
    assert payload["answer"] == "My answer"
    assert payload["marks_available"] == 15


def test_totals_only_select_marks_for_current_saved_answer():
    client, _, db = make_client()
    client.get("/exams/1/marks")
    queries = [sql for sql, _ in db.queries if "AS first_mark" in sql]
    assert queries
    assert "m.answer_text = i.answer" in queries[0]
    assert "m.scan_revision=COALESCE" in queries[0]
    assert "AND NOT confirmed" in queries[0]


def test_low_confidence_triggers_second_marker_without_request():
    first = json.loads(marking_json())
    first["confidence"] = 0.4
    client, calls, _ = make_client(replies=[json.dumps(first), marking_json()])
    response = client.post("/exams/1/answers/2/feedback")
    assert response.status_code == 200
    assert response.json()["automatic_second_review"] is True
    assert [call[0] for call in calls] == ["education", "education-reviewer"]


def test_uncertain_image_gets_independent_vision_review():
    class ImageDatabase(DB):
        def execute(self, sql, params=()):
            if "SELECT image, confirmed" in sql:
                return Result((b"sample-image", True, 2))
            if "UPDATE markings SET scan_revision" in sql:
                return Result()
            return super().execute(sql, params)

    db = ImageDatabase(ROW)
    calls = []
    def vision(model, prompt, image, task):
        calls.append((model, task))
        result = json.loads(marking_json())
        result["confidence"] = 0.4
        return json.dumps(result)
    app = FastAPI()
    app.include_router(marking_router(lambda: db, lambda: None, None, vision))
    response = TestClient(app).post("/exams/1/answers/2/feedback")
    assert response.status_code == 200
    assert response.json()["automatic_second_review"] is True
    assert calls == [("education", "exam-image-mark"), ("education-reviewer", "exam-image-second-mark")]


def test_repeated_marks_are_identical_and_cached():
    client, calls, _ = make_client()
    first = client.post("/exams/1/answers/2/feedback").json()
    second = client.post("/exams/1/answers/2/feedback").json()
    assert first["marks_awarded"] == second["marks_awarded"]
    assert first["feedback"] == second["feedback"]
    assert second["cached"] is True
    assert len(calls) == 1


def test_missing_answer_or_schedule_does_not_call_model():
    no_schedule = ROW[:6] + ("",) + ROW[7:12] + ("",) + ROW[13:]
    for row, status in [(None, 404), ((None,) + ROW[1:], 422), (no_schedule, 422)]:
        client, calls, _ = make_client(row=row)
        assert client.post("/exams/1/answers/2/feedback").status_code == status
        assert not calls


def test_invalid_model_outputs_are_rejected_after_retry():
    outputs = [
        "not json",
        marking_json(quote="invented quote"),
        marking_json(marks=20),
        json.dumps({"outcome": "achieved", "feedback": "ok", "evidence": []}),
    ]
    for output in outputs:
        client, calls, _ = make_client(replies=[output, output])
        assert client.post("/exams/1/answers/2/feedback").status_code == 502
        assert len(calls) == 2  # one bounded retry before giving up


def test_invalid_json_is_recovered_on_retry():
    client, calls, _ = make_client(replies=["not json", marking_json(marks=5)])
    response = client.post("/exams/1/answers/2/feedback")
    assert response.status_code == 200
    assert response.json()["marks_awarded"] == 5
    assert len(calls) == 2


def test_second_review_and_self_override_are_advisory():
    client, calls, _ = make_client(replies=[marking_json(marks=5), marking_json(marks=7)])
    result = client.post("/exams/1/answers/2/feedback", json={
        "second_review": True, "self_override": "merit"}).json()
    assert result["outcome"] == "not_achieved"
    assert result["second_review"]["marks_awarded"] == 7
    assert result["disagreement"] is True
    assert result["self_override"] == "merit"
    assert "not saved" in result["self_override_disclaimer"]
    assert calls[1][0] == "education-reviewer"
    assert calls[1][2] == "exam-second-mark"


def test_second_review_is_cached():
    client, calls, _ = make_client(replies=[marking_json(marks=5), marking_json(marks=7)])
    client.post("/exams/1/answers/2/feedback", json={"second_review": True})
    result = client.post("/exams/1/answers/2/feedback", json={"second_review": True}).json()
    assert result["second_review"]["marks_awarded"] == 7
    assert len(calls) == 2


def test_authentication_is_required():
    def deny():
        raise HTTPException(401, "Authentication required")

    client, calls, _ = make_client(auth=deny)
    assert client.post("/exams/1/answers/2/feedback").status_code == 401
    assert not calls


def test_override_is_stored_separately():
    client, calls, db = make_client()
    response = client.put("/exams/1/answers/2/override",
                          json={"outcome": "merit", "note": "Teacher checked this."})
    assert response.status_code == 200
    assert db.overrides[(1, 2)] == ("merit", "Teacher checked this.")
    assert "separately" in response.json()["disclaimer"]
