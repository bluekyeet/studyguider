"""Approval endpoints: nothing enters the bank twice, and nothing un-reviewed enters it."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parsing import parsing_router

ROW = (2, 91171, 2017, "paper-id", "schedule-id", "1", 15, "[]", 2, 1, "text", "schedule", "[]", "reviewed")


class FakeDb:
    def __init__(self, parsed_row, duplicate):
        self.parsed_row = parsed_row
        self.duplicate = duplicate
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        result = MagicMock()
        if "FROM parsed_questions WHERE id = %s FOR UPDATE" in sql:
            result.fetchone.return_value = self.parsed_row
        elif "FROM exam_questions WHERE standard_number" in sql:
            result.fetchone.return_value = (1,) if self.duplicate else None
        else:
            result.fetchone.return_value = (99, "2026-01-01T00:00:00+00:00")
        return result


@pytest.fixture
def approve():
    def build(db):
        router = parsing_router(lambda: db, lambda: None, lambda *args, **kwargs: "")
        return next(route for route in router.routes
                    if route.path == "/parsed-questions/{question_id}/approve").endpoint
    return build


def test_a_question_already_in_the_bank_is_rejected(approve):
    db = FakeDb(ROW, duplicate=True)
    with pytest.raises(HTTPException) as error:
        approve(db)(1)
    assert error.value.status_code == 409
    assert not any("INSERT INTO exam_questions" in sql for sql, _ in db.executed)


def test_an_approved_question_is_rejected(approve):
    db = FakeDb(ROW[:-1] + ("approved",), duplicate=False)
    with pytest.raises(HTTPException) as error:
        approve(db)(1)
    assert error.value.status_code == 409


def test_a_new_reviewed_question_enters_the_bank_once(approve):
    db = FakeDb(ROW, duplicate=False)
    result = approve(db)(1)
    assert result["id"] == 99
    assert len([sql for sql, _ in db.executed if "INSERT INTO exam_questions" in sql]) == 1
