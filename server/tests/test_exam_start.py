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
