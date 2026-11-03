"""Rapid session logic that needs no database. The session behaviour itself is in rapid_check.py."""
import pytest
from fastapi import HTTPException

import rapid_state
from rapid import RapidMove, RapidStart, order_of_sources
from pydantic import ValidationError


def test_source_order_per_mode():
    assert order_of_sources("past", 0) == ["bank"]
    assert order_of_sources("revision", 5) == ["revision"]
    assert order_of_sources("ai", 0) == ["ai", "bank"]          # real questions cover while the first batch is written
    assert [order_of_sources("mix", n)[0] for n in range(6)] == ["bank", "ai", "bank", "ai", "bank", "ai"]
    assert order_of_sources("mix", 1) == ["ai", "bank"]          # and each falls back to the other


def test_start_and_move_validation():
    assert RapidStart(topic_id=3).source == "mix" and RapidStart(topic_id=3).count is None
    for bad in ({"topic_id": 0}, {"topic_id": 1, "count": 0}, {"topic_id": 1, "count": 201}, {"topic_id": 1, "source": "all"}):
        with pytest.raises(ValidationError):
            RapidStart(**bad)
    assert RapidMove().answer == "" and RapidMove(skip=True).skip
    with pytest.raises(ValidationError):
        RapidMove(answer="x" * 100001)


class Rows:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Db:
    def __init__(self, open_session):
        self.open_session = open_session

    def execute(self, sql, params=()):
        assert "rapid_sessions" in sql
        return Rows((1,) if self.open_session else None)


def test_blindfold_applies_to_open_sessions_only_and_not_to_the_marking_thread():
    with pytest.raises(HTTPException) as refused:
        rapid_state.refuse_if_blind(Db(True), 5)
    assert refused.value.status_code == 409
    rapid_state.refuse_if_blind(Db(False), 5)           # an ordinary or ended exam
    rapid_state.bypass.on = True
    try:
        rapid_state.refuse_if_blind(Db(True), 5)        # the background marker may read results
    finally:
        rapid_state.bypass.on = False
