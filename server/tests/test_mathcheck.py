import json

import pytest

import mathcheck
from mathcheck import arithmetic_problems


def test_the_wrong_sum_the_lesson_reviewer_let_through_is_caught():
    # From a real generated lesson's multiple-choice explanation: 10101110 in binary is 128 + 32 + 8 + 4 + 2, and the 8 is missing.
    text = r"B: 174 is correct because $128 + 0 + 32 + 0 + 4 + 2 + 0 = 174$. *"
    found = arithmetic_problems(text)
    assert found == [{"claim": "128 + 0 + 32 + 0 + 4 + 2 + 0 = 174", "computed": 166.0, "stated": 174.0}]
    assert "comes to 166, not 174" in mathcheck.issues(text)[0]
    assert arithmetic_problems("128 + 32 + 4 + 2 = 174") and not arithmetic_problems("128 + 32 + 8 + 4 + 2 = 174")


@pytest.mark.parametrize("text", [
    r"$F = \frac{mv^2}{r} = \frac{1200 \times 15^2}{50} = 5400\text{ N}$",
    r"$q = 400 \times 4.18 \times 16.2 = 27086.4\text{ J} \approx 27.1\text{ kJ}$",
    r"$400 \times 4.18 \times 16.2 = 27100$ J",                   # stated to three significant figures
    r"$v = \sqrt{2 \times 9.8 \times 5} = 9.9\text{ m s}^{-1}$",
    r"$2^{10} = 1024$ and 2³ = 8",
    r"Mean = (2 + 4 + 4 + 5 + 7 + 8) / 6 = 30 / 6 = 5 kg",
    "P = 1/36 and 6/36 = 1/6",
    "Break-even when 40q = 1000 + 15q, so 25q = 1000 and q = 40.",
    "The year 2019 = Test 1; Q1 = 3 marks; x = 5; pH = 14 - 4.5 = 9.5",
    "12 / 7 = 1.71 and 7 / 3 = 2.33",
    r"Area $= 3.0 \times 4.0 = 12.0$ m.",
    "2.5 km = 2500 m and 350 mL = 0.35 L",
    "momentum: 2.0 × 3.0 = 3.0 v, so v = 2.0 m/s",                # "3.0 v" is algebra, not the number 3.0
    r"$1500 	imes 1000 = 1.5$ megapixels",                        # the scale is in the unit
])
def test_correct_working_and_things_that_are_not_sums_pass(text):
    assert arithmetic_problems(text) == []


@pytest.mark.parametrize("text, computed", [
    ("Total = 2 + 2 = 5 marks", 4),
    (r"$\frac{1200 \times 15^2}{50} = 4500$", 5400),
    (r"$\sqrt{2 \times 9.8 \times 5} = 7.0$", 9.8995),
    ("2.5 km = 250 m", 2500),
    ("v = 3.0 × 4 = 13", 12),
    ("The ratio is 27,086 / 2 = 13,000", 13543),
])
def test_wrong_working_is_found(text, computed):
    found = arithmetic_problems(text)
    assert found and abs(found[0]["computed"] - computed) < 0.01, found


def test_nothing_unsafe_is_ever_evaluated():
    assert mathcheck.evaluate("__import__('os').system('echo hi')") is None
    assert mathcheck.evaluate("9 ** 9 ** 9") is None
    assert mathcheck.evaluate("1 / 0") is None
    assert arithmetic_problems("open('x') + 1 = 2") == []


def test_a_lesson_with_wrong_arithmetic_is_sent_back_and_flagged_if_it_stays_wrong(monkeypatch):
    import lesson_quality
    monkeypatch.setattr(lesson_quality, "formula_issues", lambda text: [])
    monkeypatch.setattr(lesson_quality, "teaching_structure_issues", lambda text: [])
    lesson = "### Worked example\nConvert 10101110: $128 + 32 + 4 + 2 = 174$."
    calls = []

    def model(name, messages, task="general"):
        calls.append(task)
        if task == "lesson-review":
            return json.dumps({"pass": True, "issues": []})          # the reviewing model passes it, as it did for real
        assert "comes to 166, not 174" in messages[1]["content"]       # the rewrite is told exactly what is wrong
        return "### Worked example\nConvert 10101110: $128 + 32 + 8 + 4 + 2 = 174$."

    fixed, _, status = lesson_quality.review_and_revise(lesson, {}, model)
    assert status == "passed" and "8 + 4" in fixed and calls == ["lesson-review", "lesson-revise", "lesson-review"]

    stubborn = lambda name, messages, task="general": json.dumps({"pass": True, "issues": []}) if task == "lesson-review" else lesson
    assert lesson_quality.review_and_revise(lesson, {}, stubborn)[2] == "flagged"


def test_revision_pack_questions_with_wrong_worked_answers_are_dropped():
    import revision
    section = {"concept": "Binary", "why": "", "teaching": "Add the place values: $128 + 32 = 160$.",
               "questions": [{"question": "Convert 10101110 to decimal.", "expected_answer": "128 + 32 + 4 + 2 = 174"},
                             {"question": "Convert 110 to decimal.", "expected_answer": "4 + 2 = 6"},
                             {"question": "Convert 111 to decimal.", "expected_answer": "4 + 2 + 1 = 7"}]}
    kept = [q for q in section["questions"] if not arithmetic_problems(q["expected_answer"])]
    assert [q["question"] for q in kept] == ["Convert 110 to decimal.", "Convert 111 to decimal."]
    assert hasattr(revision, "mathcheck")


def test_an_import_corrects_ai_written_working_once_and_marks_what_stays_wrong():
    import exam_import
    form = exam_import.choice.normalise_form({"options": [{"key": "A", "text": "166"}, {"key": "B", "text": "174"}]})
    key = {"correct": ["B"], "explanations": {"B": "128 + 32 + 4 + 2 = 174."}, "partial": False, "source": "ai"}
    question = {"number": "4", "stem": "", "text": "What is 10101110 in decimal?", "parts": []}
    written = {"guide": "", "key": dict(key), "marks": 1, "source": "ai", "note": ""}
    guide = {"guide": "Model answer: 25 x 4 = 1000, so q = 40.", "key": None, "marks": 2, "source": "ai", "note": ""}
    todo = [(question, "", question["text"], form, written), ({**question, "number": "5"}, "", "Find q.", None, guide)]
    asked = []

    def model(name, messages, task="general", timeout=120):
        asked.append(json.loads(messages[1]["content"]))
        # It fixes the explanation but not the written guide.
        return json.dumps({"guides": [{"id": 0, "explanations": {"B": "128 + 32 + 8 + 4 + 2 = 174."}},
                                      {"id": 1, "guide": "Model answer: 25 x 4 = 1000, so q = 40."}]})

    exam_import._correct_arithmetic(model, todo, {"calls": 0})
    assert len(asked) == 1 and asked[0]["items"][0]["arithmetic_errors"]           # one call for every wrong item
    assert written["key"]["explanations"]["B"] == "128 + 32 + 8 + 4 + 2 = 174." and not written["note"]
    assert guide["guide"].startswith(mathcheck.WARNING) and "arithmetic error" in guide["note"]
    # Nothing wrong: no call at all.
    exam_import._correct_arithmetic(lambda *a, **k: pytest.fail("no call when the arithmetic is right"), todo[:1], {"calls": 0})


def test_a_practice_rubric_still_wrong_after_correction_carries_a_warning():
    rubric = "Worked answer: 128 + 32 + 4 + 2 = 174"
    assert mathcheck.warning(arithmetic_problems(rubric)).startswith("Check the arithmetic: The working states")
    assert mathcheck.warning([]) == ""


def test_a_choice_key_note_reaches_the_feedback():
    import choice
    form = choice.normalise_form({"options": [{"text": "166"}, {"text": "174"}]})
    key = {"correct": ["B"], "explanations": {}, "source": "ai", "note": "Check the arithmetic: ..."}
    result = choice.mark(form, key, "Choice: B")
    assert result["key_note"] == "Check the arithmetic: ..." and "Check the arithmetic" in choice.feedback(result)
