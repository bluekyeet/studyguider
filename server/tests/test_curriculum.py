import io
import json
from datetime import date

import pymupdf
import pytest
from fastapi import HTTPException

import curriculum


def descriptor_pdf():
    """A small PDF laid out like AUT's descriptor report: one text block per field and per assessment row."""
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    blocks = ["Course Title:\nProgramming Concepts and Techniques", "Course Code:\nCOMP500", "POINTS:\n15.00", "LEVEL:\n5",
              "PREREQUISITE/S:\nNone", "LEARNING HOURS\nTotal learning hours: 150", "LEARNING OUTCOMES",
              "1.\nWrite, compile, test and debug small-scale programs that adhere to a programming standard\n(a, b, c)",
              "2.\nDevelop programs featuring input and output that use sequence, selection and iteration (a, b)",
              "3.\nImplement programs that store data using arrays (a, c)",
              "Disclaimer: Course descriptors may be amended between teaching periods/semesters\nPage 1 of 2",
              "ASSESSMENT PLAN", "Assessment Event\nWeighting %\nLearning Outcomes", "Lab work\n20.00\n1-3",
              "Assignment 2: Arrays,\nFiles\n30.00\n2,3", "Final  Exam\n50.00\n1,2,3",
              "Grade Map\nMAP1\nA+ A A- Pass with Distinction", "Overall requirement/s to pass the course:",
              "To pass this course, students must attempt all summative assessments and achieve a minimum\noverall grade of C-.",
              "LEARNING & TEACHING STRATEGIES"]
    y = 30
    for text in blocks:
        lines = text.count("\n") + 1
        page.insert_textbox(pymupdf.Rect(40, y, 560, y + 13 * lines + 4), text, fontsize=9)
        y += 13 * lines + 12
    return document.tobytes()


def test_reads_an_aut_descriptor():
    draft = curriculum.parse_aut_descriptor(descriptor_pdf())
    assert (draft["code"], draft["title"], draft["points"], draft["level"], draft["hours"]) == (
        "COMP500", "Programming Concepts and Techniques", 15.0, 5, 150)
    assert [o["code"] for o in draft["outcomes"]] == ["LO1", "LO2", "LO3"]
    assert draft["outcomes"][0]["title"] == "Write, compile, test and debug small-scale programs that adhere to a programming standard"
    assert [(a["title"], a["weight_pct"], a["outcome_codes"], a["kind"]) for a in draft["assessments"]] == [
        ("Lab work", 20.0, ["LO1", "LO2", "LO3"], "lab"),
        ("Assignment 2: Arrays, Files", 30.0, ["LO2", "LO3"], "assignment"),
        ("Final Exam", 50.0, ["LO1", "LO2", "LO3"], "exam")]
    assert draft["pass_rule"].startswith("To pass this course, students must attempt all summative assessments")
    assert not any(a["must_pass"] for a in draft["assessments"])     # an overall C- is not a must-pass on one item


def test_aut_fetch_refuses_unknown_codes_and_bad_input():
    class Response:
        def __init__(self, kind, body): self.headers, self.body = {"Content-Type": kind}, body
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return self.body
    seen = []

    def missing(request, timeout):
        seen.append(request.full_url)
        return Response("text/html; charset=utf-8", b"Course descriptor does not exist.")
    with pytest.raises(HTTPException) as error:
        curriculum.fetch_aut_descriptor("math 604", date(2026, 11, 12), opener=missing)
    assert error.value.status_code == 404
    assert "courseCode=MATH604&date=2026-11-12&saveFormat=pdf" in seen[0]
    with pytest.raises(HTTPException) as error:
        curriculum.fetch_aut_descriptor("COMPSCI 110", opener=missing)
    assert error.value.status_code == 422
    url, data = curriculum.fetch_aut_descriptor("COMP500", date(2026, 11, 12), opener=lambda r, timeout: Response("Application/pdf", b"%PDF-1.4"))
    assert data.startswith(b"%PDF")


UOA_OUTLINE = """COMPSCI 110 : Introduction to Computer Systems
15 points  Semester One 2027
Learning Outcomes
By the end of this course, students will be able to:
1. Describe how data is represented in a computer system
2. Explain the operation of a simple processor and its
instruction cycle
3. Write small programs in assembly language
Assessments
Assessment Type | Percentage | Classification
Assignments | 20% | Individual Coursework
Tutorials | 10% | Individual Coursework
Test | 20% | Individual Test  (LO 1, 2) 24 April 2027
Final Exam | 50% | Individual Examination
A student must obtain at least 45% in the final exam to pass this course.
"""


def test_reads_a_pasted_outline_without_a_model():
    draft = curriculum.extract_outline(UOA_OUTLINE)
    assert draft["method"] == "pattern"
    assert draft["code"] == "COMPSCI 110" and draft["points"] == 15.0 and draft["level"] == 1
    assert draft["title"] == "Introduction to Computer Systems"
    assert [o["code"] for o in draft["outcomes"]] == ["LO1", "LO2", "LO3"]
    assert draft["outcomes"][1]["title"] == "Explain the operation of a simple processor and its instruction cycle"
    assert [(a["title"], a["weight_pct"]) for a in draft["assessments"]] == [
        ("Assignments", 20.0), ("Tutorials", 10.0), ("Test", 20.0), ("Final Exam", 50.0)]
    test = draft["assessments"][2]
    assert test["due_date"] == "2027-04-24" and test["outcome_codes"] == ["LO1", "LO2"]
    assert draft["assessments"][3]["must_pass"] is True        # "at least 45% in the final exam"
    assert "45%" in draft["pass_rule"]


def test_model_reading_is_validated_and_falls_back():
    good = json.dumps({"code": "COMPSCI 110", "title": "Intro", "points": 15,
                       "learning_outcomes": [{"code": "LO1", "title": "Describe data"}],
                       "assessments": [{"title": "Exam", "weight_pct": 60, "due_date": "2027-06-20", "outcome_codes": ["LO1"]},
                                       {"title": "Lab", "weight_pct": 140, "due_date": "soon"}]})
    draft = curriculum.extract_outline(UOA_OUTLINE, lambda *args, **kwargs: good)
    assert draft["method"] == "ai" and draft["level"] == 1
    assert draft["assessments"][0]["due_date"] == "2027-06-20" and draft["assessments"][1]["weight_pct"] is None
    assert draft["assessments"][1]["due_date"] is None
    assert curriculum.extract_outline(UOA_OUTLINE, lambda *args, **kwargs: "not json")["method"] == "pattern"


def test_outcome_numbers_and_letters():
    assert curriculum.outcome_numbers("1,2,3") == ["1", "2", "3"]
    assert curriculum.outcome_numbers("LO1, LO4") == ["1", "4"]
    assert curriculum.outcome_numbers("1-5") == ["1", "2", "3", "4", "5"]
    assert [curriculum.letter_for(p)[0] for p in (95, 85, 79.9, 70, 50, 49.9, 10)] == ["A+", "A", "B+", "B", "C-", "D+", "D-"]
    assert curriculum.letter_for(72)[1] == 5      # B is 5 grade points


def test_university_estimate_is_weighted_and_flags_must_pass():
    items = [{"title": "Test", "weight_pct": 20, "result_pct": 80, "must_pass": False},
             {"title": "Assignment", "weight_pct": 30, "result_pct": 60, "must_pass": False},
             {"title": "Exam", "weight_pct": 50, "result_pct": None, "must_pass": True}]
    estimate = curriculum.estimate_university(items, "uoa9")
    assert estimate["percent"] == 68.0 and estimate["estimate"] == "B-" and estimate["weight_counted"] == 50
    assert estimate["passing"] and "scale_note" not in estimate
    items[2]["result_pct"] = 40
    failed = curriculum.estimate_university(items, "aut9")
    assert failed["must_pass_failed"] == ["Exam"] and not failed["passing"] and "scale_note" in failed
    assert curriculum.estimate_university([{"title": "Exam", "weight_pct": 100, "result_pct": None, "must_pass": False}], "uoa9")["estimate"] is None


def test_assessment_kinds_and_validation():
    assert [curriculum.guess_kind(t) for t in ("Final Exam", "Mid-semester practical test", "Lab work", "Portfolio", "Essay")] == [
        "exam", "test", "lab", "portfolio", "assignment"]
    with pytest.raises(ValueError):
        curriculum.Programme(kind="ncea", institution="massey")
    assert curriculum.Assessment(title="Quiz", kind="weird").kind == "other"
    with pytest.raises(ValueError):
        curriculum.Assessment(title="Quiz", result_pct=120)


def test_ncea_exam_dates_come_from_the_nzqa_timetable_by_subject_and_level():
    from curriculum import exam_session
    assert exam_session("Chemistry", 3, 2026) == {"date": "2026-11-20", "session": "2:00 pm", "subject": "L3 Chemistry"}
    assert exam_session("Mathematics", 2, 2026)["subject"] == "L2 Mathematics and Statistics"
    assert exam_session("Physics", 1, 2026)["subject"] == "L1 Physics and Earth Space Science"
    assert exam_session("Woodwork", 2, 2026) is None          # not timetabled: entered by hand
    assert exam_session("Chemistry", 3, 2031) is None         # a year whose timetable is not known
    assert exam_session("Chemistry", 7, 2026) is None


def test_an_assessment_says_when_it_is_multiple_choice():
    from curriculum import guess_format
    assert guess_format("Mid-semester test (multiple choice)") == "multiple_choice"
    assert guess_format("Final exam: MCQ and short answer") == "mixed"
    assert guess_format("Assignment 1") == ""
