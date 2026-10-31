"""A model-call accounting failure must never break the learner's request."""
import sys
from pathlib import Path
from unittest.mock import patch

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usage import log_run


def test_log_run_swallows_database_errors():
    with patch("usage.psycopg.connect", side_effect=psycopg.OperationalError("down")):
        log_run("lesson", "education", 10, 20, "ok")


def test_log_run_records_the_outcome_it_is_given():
    recorded = {}

    class FakeDb:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params):
            recorded["sql"] = sql
            recorded["params"] = params

    with patch("usage.psycopg.connect", return_value=FakeDb()):
        log_run("exam-parse", "education-reviewer", 100, 50, "ok", None, 11, 22)
    assert "INSERT INTO ai_runs" in recorded["sql"]
    assert recorded["params"][:5] == ("exam-parse", "education-reviewer", 100, 50, "ok")
    assert recorded["params"][6:] == (11, 22)
