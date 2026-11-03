import pytest
from pydantic import ValidationError

from exams import ScheduleBoundaries, StartExam


def test_start_exam_validates_mode_topic_and_count():
    assert StartExam(topic_id=2, mode="ai").question_count == 3
    for values in ({"topic_id": 0, "mode": "mixed"}, {"topic_id": 2, "mode": "official-ai"}, {"topic_id": 2, "mode": "ai", "question_count": 100}):
        with pytest.raises(ValidationError):
            StartExam(**values)


def test_boundaries_require_original_review_and_order():
    values = dict(standard_number=91171, year=2024, schedule_resource_id="00000000-0000-0000-0000-000000000001", page=1,
                  achieved=8, merit=14, excellence=20, total=24, quote="Assistant-written sample boundary evidence", reviewed_against_original=True)
    assert ScheduleBoundaries(**values).total == 24
    for change in ({"reviewed_against_original": False}, {"excellence": 25}, {"merit": 8}):
        with pytest.raises(ValidationError):
            ScheduleBoundaries(**(values | change))


def _paper(count, **override):
    import json
    item = {"question": "A trolley of mass 2.0 kg accelerates at 3.0 m s^-2. Calculate the force.", "rubric": "Achievement: F = ma. Merit: 6.0 N. Excellence: units.", "marks": 4}
    return json.dumps([{**item, **override} for _ in range(count)])


def test_practice_paper_parser_accepts_harmless_variations():
    import json
    from exams import parse_practice_paper
    assert len(parse_practice_paper(_paper(3), 3)) == 3
    assert len(parse_practice_paper("```json\n" + _paper(2) + "\n```\nextra chatter", 2)) == 2
    assert len(parse_practice_paper(json.dumps({"questions": json.loads(_paper(3))}), 3)) == 3
    assert len(parse_practice_paper(_paper(5), 3)) == 3          # extras are dropped, never padded
    assert parse_practice_paper(_paper(1, marks="6"), 1)[0]["marks"] == 6


def test_practice_paper_parser_rejects_bad_papers_and_says_why():
    import pytest
    from exams import parse_practice_paper
    for reply, fragment in ((_paper(2), "2 questions, 3"), ("not json at all", "not valid JSON"), (_paper(3, marks=20), "marks outside"),
                            (_paper(3, rubric="x"), "usable rubric"), (_paper(3, question=None), "usable question"), ('{"a": 1}', "not a list")):
        with pytest.raises(ValueError, match=fragment):
            parse_practice_paper(reply, 3)


def test_practice_paper_parser_lays_out_structured_rubrics_and_alias_keys():
    import json
    from exams import parse_practice_paper
    base = {"question": "A trolley of mass 2.0 kg accelerates at 3.0 m s^-2. Calculate the force.", "marks": 4}
    nested = {**base, "rubric": {"Achievement": "Uses F = ma.", "Merit": "Gets 6.0 N.", "Excellence": ["Gives units", "Explains why"]}}
    paper = parse_practice_paper(json.dumps([nested]), 1)
    assert paper[0]["rubric"].splitlines()[0] == "Achievement: Uses F = ma." and "Gives units" in paper[0]["rubric"]
    listed = {**base, "mark_scheme": ["Achievement: Uses F = ma.", "Merit: Gets 6.0 N."]}
    assert "Merit: Gets 6.0 N." in parse_practice_paper(json.dumps([listed]), 1)[0]["rubric"]


def test_practice_paper_parser_repairs_single_backslash_latex_but_leaves_valid_escapes():
    import json
    from exams import parse_practice_paper, _repair_latex_escapes
    bs = chr(92)
    question = "Which bond is C" + bs + "equiv C in alkynes? State the bond type and name one example."
    reply = '[{"question": "' + question + '", "rubric": "Achievement: alkyne. Merit: triple bond. Excellence: example.", "marks": 4}]'
    assert parse_practice_paper(reply, 1)[0]["question"] == question
    valid = '{"a": "line' + bs + 'nbreak ' + bs + bs + 'text", "b": "q' + bs + '"x"}'
    assert _repair_latex_escapes(valid) == valid and json.loads(valid)
