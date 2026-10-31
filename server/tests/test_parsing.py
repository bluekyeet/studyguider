"""Question parsing units: marks, labels, JSON tolerance and the heading fallback.

All sample text here is written for this test, not copied from a real paper.
"""
import pytest

from parsing import (_clean_json, _fallback_questions, _normalise_label, _schedule_for,
                     normalise_number, part_marks, printed_marks)


def test_printed_marks_reads_every_part_total():
    assert printed_marks("(a) 3 marks (b) (i) 2 marks (c) 4 marks") == [3, 2, 4]


def test_printed_marks_uses_the_printed_question_total_when_parts_have_none():
    assert printed_marks("QUESTION ONE: SAMPLES\nTotal: 15 marks") == [15]


def test_printed_marks_reports_nothing_when_the_paper_prints_no_total():
    assert printed_marks("QUESTION ONE: SAMPLES\nExplain your reasoning.") == []


def test_part_marks_keeps_sub_parts_with_their_own_marks():
    assert part_marks("(a) 3 marks (b) (i) 2 marks") == [
        {"label": "a", "marks": 3},
        {"label": "b(i)", "marks": 2},
    ]


@pytest.mark.parametrize("value, expected", [
    ("(a)", "a"), ("a", "a"), ("(b)(i)", "b(i)"), ("b (ii)", "b(ii)"), ("(a)(iii)", "a(iii)"),
])
def test_part_labels_have_one_form(value, expected):
    assert _normalise_label(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("one", "1"), ("Three", "3"), ("2(b)(i)", "2"), ("QUESTION FOUR", "4"),
])
def test_question_numbers_are_single_numbers(value, expected):
    assert normalise_number(value) == expected


def test_clean_json_accepts_a_fenced_reply():
    assert _clean_json('```json\n[{"question_number": "1"}]\n```') == [{"question_number": "1"}]


def test_clean_json_keeps_json_surrounded_by_prose():
    assert _clean_json('Here are the questions: [{"question_number": "1"}] I hope this helps.') == [
        {"question_number": "1"}]


def test_clean_json_rejects_a_reply_without_json():
    with pytest.raises(ValueError):
        _clean_json("I cannot help with that.")


def test_clean_json_keeps_only_the_first_of_two_arrays():
    reply = '[{"question_number": "1"}] [{"question_number": "2"}]'
    assert _clean_json(reply) == [{"question_number": "1"}]


def test_clean_json_rejects_a_truncated_array():
    with pytest.raises(ValueError):
        _clean_json('[{"question_number": "1"}, {"question_number": "2"')


def test_schedule_lookup_skips_a_bare_mention_in_body_text():
    schedule = [(1, "This paper covers one topic.\nONE  (a)  Correct answer."), (2, "unused")]
    page, text = _schedule_for(schedule, "1")
    assert page == 1
    assert "ONE  (a)" in text


def test_schedule_lookup_prefers_the_page_where_the_heading_owns_its_line():
    schedule = [(1, "Notes about one learner."), (2, "ONE\n(a)  Correct answer.")]
    assert _schedule_for(schedule, "1")[0] == 2


def test_fallback_groups_every_part_under_one_question():
    paper = [(1, "QUESTION ONE: SAMPLE\n(a) 2 marks\n(b) 3 marks"),
             (2, "QUESTION TWO: SAMPLE\n(a) 4 marks")]
    schedule = [(1, "ONE  (a)  Any answer.\nTWO  (a)  Any answer.")]
    questions = _fallback_questions(paper, schedule, 91171, 2017, {1})
    assert [question["question_number"] for question in questions] == ["1", "2"]
    assert questions[0]["marks"] == 5
    assert questions[1]["marks"] == 4
    assert questions[0]["parts"] == [{"label": "a", "marks": 2}, {"label": "b", "marks": 3}]


def test_fallback_copies_paper_wording_rather_than_writing_any():
    paper = [(1, "QUESTION ONE: SAMPLE\n(a) 2 marks\nDescribe the motion.")]
    questions = _fallback_questions(paper, [(1, "ONE  (a)  Any answer.")], 91171, 2017, set())
    assert questions[0]["question_text"].startswith("QUESTION ONE: SAMPLE")
    assert "Describe the motion." in questions[0]["question_text"]


def test_fallback_returns_nothing_without_headings():
    assert _fallback_questions([(1, "No headings here.")], [(1, "ONE")], 91171, 2017, set()) == []
