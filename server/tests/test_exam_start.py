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
