"""LaTeX restoration of past-paper question text (vision reply stubbed; no model or PDF)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mathtext

OLD = "When the polynomial 3x4 + px3 – 4x + 5 is divided by x – 2, the remainder is 21. Find the value of p."
NEW = "When the polynomial $3x^4 + px^3 - 4x + 5$ is divided by $x - 2$, the remainder is $21$. Find the value of $p$."


def test_rewrite_that_keeps_the_wording_is_accepted():
    assert mathtext.acceptable(NEW, OLD)


def test_added_or_dropped_words_are_rejected():
    assert not mathtext.acceptable(NEW + " Hint: use the factor theorem to solve it.", OLD)
    assert not mathtext.acceptable("Find the value of $p$.", OLD)
    assert not mathtext.acceptable("When the polynomial $3x^4 is divided", OLD)      # unbalanced dollar signs
    assert not mathtext.acceptable("", OLD)


def test_units_cover_the_question_and_its_parts():
    assert mathtext.units_of("Intro", [{"label": "a", "text": "Part a"}, {"label": "b", "text": " "}]) == {"q": "Intro", "p0": "Part a"}


@pytest.fixture
def pages(monkeypatch):
    monkeypatch.setattr(mathtext, "render_pages", lambda resource, page_numbers: b"png")


def test_restore_one_returns_only_accepted_units_and_keeps_backslashes(pages):
    reply = "=== q ===\nIntro $\\frac{x}{2}$\n=== p0 ===\nSomething completely different and invented here\n"
    row = (1, "res", 2, [2, 3], "Intro x2", [{"label": "a", "text": "Part a original wording"}])
    assert mathtext.restore_one(lambda *a, **k: reply, row) == {"q": "Intro $\\frac{x}{2}$", "p": [None]}


def test_a_reply_that_changes_everything_raises(pages):
    row = (1, "res", 2, [], OLD, [])
    with pytest.raises(ValueError):
        mathtext.restore_one(lambda *a, **k: "=== q ===\nTotally unrelated words about something else", row)


def test_a_reply_in_the_wrong_form_raises(pages):
    row = (1, "res", 2, [], OLD, [])
    with pytest.raises(ValueError):
        mathtext.restore_one(lambda *a, **k: "Sorry, I cannot read that image.", row)


def test_overlay_swaps_text_and_parts_but_leaves_other_questions():
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [(5, {"q": NEW, "p": [None, "Part b $y^2$"]})]
    items = [{"question_id": 5, "question_text": OLD, "parts": [{"label": "a", "text": "Part a"}, {"label": "b", "text": "Part b y2"}]},
             {"question_id": 6, "question_text": "Other", "parts": []}]
    out = mathtext.overlay(db, items)
    assert out[0]["question_text"] == NEW
    assert [p["text"] for p in out[0]["parts"]] == ["Part a", "Part b $y^2$"]
    assert out[1]["question_text"] == "Other"


def test_a_misread_exponent_is_rejected():
    old = "Solve the equation z3 + 8m27i = 0, where m is a positive real constant."
    assert mathtext.acceptable("Solve the equation $z^3 + 8m^{27}\text{i} = 0$, where $m$ is a positive real constant.", old)
    assert not mathtext.acceptable("Solve the equation $z^3 + 8m^3\text{i} = 0$, where $m$ is a positive real constant.", old)
