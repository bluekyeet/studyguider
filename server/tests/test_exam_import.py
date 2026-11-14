import fitz
import pytest

import exam_import

PAPER = """Question 1
[2.5 marks] Which one of the following is an example of volatile storage?
(a) USB drive
(b) RAM
(c) SSD
Question 2
[5 marks] Explain why an SSD is faster than an HDD when reading many small files.
Question 3
(a) Convert 10101110 to decimal. (2 marks)
(b) State true or false: one byte holds 8 bits. True / False (1 mark)"""


def reply(**question):
    base = {"number": "1", "page": 1, "marks": 2.5, "group": "", "stem": "", "kind": "choice", "multiple": False,
            "text": "Which one of the following is an example of volatile storage?",
            "options": [{"key": "a", "text": "USB drive"}, {"key": "b", "text": "RAM"}, {"key": "c", "text": "SSD"}],
            "parts": [], "needs_figure": False, "outcomes": ["LO1"]}
    base.update(question)
    return base


def test_questions_whose_wording_is_on_the_paper_are_kept_with_options_and_outcomes():
    data = {"rubric": {"marks_per_question": 2.5, "negative_marking": None, "total_marks": None}, "questions": [reply()]}
    questions, rubric, warnings = exam_import.clean_questions(data, PAPER, {"LO1", "LO2"}, [(1, PAPER)])
    assert not warnings and rubric["marks_per_question"] == 2.5
    q = questions[0]
    assert q["number"] == "1" and q["marks"] == 2.5 and q["outcomes"] == ["LO1"]
    assert [o["text"] for o in q["choice"]["options"]] == ["USB drive", "RAM", "SSD"]


def test_wording_the_model_made_up_is_left_out_and_reported():
    invented = reply(number="9", text="Describe the history of the abacus in ancient Mesopotamia and its cultural meaning.",
                     kind="written", options=[])
    questions, _, warnings = exam_import.clean_questions({"questions": [invented]}, PAPER, set(), [(1, PAPER)])
    assert questions == [] and "Question 9 was left out" in warnings[0]


def test_outcome_codes_not_in_the_paper_are_dropped():
    questions, _, _ = exam_import.clean_questions({"questions": [reply(outcomes=["LO1", "LO7", "made up"])]}, PAPER, {"LO1"}, [(1, PAPER)])
    assert questions[0]["outcomes"] == ["LO1"]


def test_parts_keep_their_own_kind_marks_and_true_false_options():
    q3 = reply(number="3", kind="written", options=[], text="", marks=None, parts=[
        {"label": "(a)", "text": "Convert 10101110 to decimal.", "marks": 2, "kind": "written", "options": []},
        {"label": "(b)", "text": "State true or false: one byte holds 8 bits.", "marks": 1, "kind": "choice", "options": []}])
    questions, _, warnings = exam_import.clean_questions({"questions": [q3]}, PAPER, set(), [(1, PAPER)])
    assert not warnings
    parts = questions[0]["parts"]
    assert [p["label"] for p in parts] == ["a", "b"] and parts[0]["choice"] is None
    assert [o["text"] for o in parts[1]["choice"]["options"]] == ["True", "False"]


def test_the_page_is_where_the_question_starts_not_the_page_number_the_model_reports():
    pages = [(3, "Cover page and instructions"), (4, PAPER)]
    questions, _, _ = exam_import.clean_questions({"questions": [reply(page=1)]}, PAPER, set(), pages)
    assert questions[0]["page"] == 4


def test_rows_carry_keys_marks_and_where_the_guide_came_from():
    questions, rubric, _ = exam_import.clean_questions({"rubric": {"marks_per_question": 2.5}, "questions": [
        reply(), reply(number="2", kind="written", options=[], marks=5, text="Explain why an SSD is faster than an HDD when reading many small files.")]},
        PAPER, {"LO1"}, [(1, PAPER)])
    official = {("1", ""): {"correct": ["b"], "guide": "", "marks": None, "partial": False}}
    guides = {("1", ""): {"guide": "", "key": exam_import.choice.normalise_key({"correct": ["b"]}, questions[0]["choice"], "official"),
                          "marks": None, "source": "official", "note": ""},
              ("2", ""): {"guide": "Two marks for random access; three for no seek time.", "key": None, "marks": 5, "source": "ai", "note": ""}}
    assert official     # the shape pair_guide returns
    rows = exam_import.build_rows(questions, guides, rubric)
    first, second = rows
    assert first["keys"][""]["correct"] == ["B"] and first["marks"] == 3 and first["marks_exact"] == 2.5
    assert first["forms"][""][0]["kind"] == "choice" and first["guide_source"] == "official"
    assert "Correct option: B. RAM" in first["guide"]
    assert second["keys"] == {} and second["guide_source"] == "ai" and second["guide"].startswith(exam_import.AI_GUIDE_NOTE)


def test_unprinted_marks_fall_back_to_the_papers_rule_then_one_per_choice():
    questions, _, _ = exam_import.clean_questions({"questions": [reply(marks=None)]}, PAPER, set(), [(1, PAPER)])
    guides = {("1", ""): {"guide": "", "key": None, "marks": None, "source": "ai", "note": ""}}
    assert exam_import._marks_of(questions[0], guides, {"marks_per_question": 2.5})[0] == 2.5
    assert exam_import._marks_of(questions[0], guides, {})[0] == 1.0


def test_highlighted_options_in_a_model_answer_file_are_flagged(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Question 1")
    page.insert_text((72, 120), "(a) USB drive")
    page.insert_text((72, 140), "(b) RAM")
    page.draw_rect(fitz.Rect(70, 129, 140, 144), color=None, fill=(1, 1, 0), overlay=False)
    path = tmp_path / "answers.pdf"
    doc.save(path)
    pages, scanned = exam_import.read_file(path, "answers.pdf", marks=True)
    lines = pages[0][1].splitlines()
    assert not scanned
    assert any(line.startswith(exam_import.MARK) and "RAM" in line for line in lines)
    assert not any(line.startswith(exam_import.MARK) and "USB" in line for line in lines)


def test_long_papers_are_read_in_runs_of_pages_that_show_the_next_page_start():
    pages = [(n, "x" * 4000) for n in range(1, 6)]
    groups = exam_import.chunks(pages, size=9000)
    assert [[n for n, _ in group] for group, _ in groups] == [[1, 2], [3, 4], [5]]
    assert groups[0][1] == "x" * 2500 and groups[-1][1] == ""


def test_an_upload_that_is_not_a_paper_is_refused():
    from fastapi import HTTPException
    router = exam_import.exam_import_router(lambda: None, lambda: None, None, None)
    create = next(r.endpoint for r in router.routes if r.path.endswith("/exam-imports") and "POST" in r.methods)

    class Upload:
        filename = "virus.exe"
        file = None
    with pytest.raises(HTTPException) as refused:
        create(1, Upload(), None, "", None, "exam", None)
    assert refused.value.status_code == 422
