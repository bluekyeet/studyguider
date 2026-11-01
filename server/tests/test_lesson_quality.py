import json

import pytest

from lesson_quality import review_and_revise, contamination_issues, formula_issues


def test_rejected_lesson_is_rewritten_then_rechecked():
    replies = iter([json.dumps({"pass": False, "issues": ["Wrong unit"]}), "Corrected lesson", json.dumps({"pass": True, "issues": []})])
    calls = []
    def reply(model, messages, task):
        calls.append(task)
        return next(replies)
    lesson, review, status = review_and_revise("Draft", {}, reply)
    assert lesson == "Corrected lesson" and status == "passed"
    assert calls == ["lesson-review", "lesson-revise", "lesson-review"]


def test_provider_failure_preserves_draft_without_passing():
    def fail(*args, **kwargs): raise RuntimeError("Unavailable")
    assert review_and_revise("Keep my work", {}, fail) == ("Keep my work", None, "unavailable")


def test_coding_boilerplate_cannot_pass_even_if_reviewer_approves():
    bad = '```rust\n// minimalist core\n```\nskipped: [tests], add when [bugs appear].\nponytail: none.'
    assert contamination_issues(bad)
    assert not contamination_issues("Carbon atoms form covalent bonds. Calculate the charge in C.")
    def reply(model, messages, task):
        return json.dumps({"pass": True, "issues": []}) if task == "lesson-review" else bad
    lesson, review, status = review_and_revise(bad, {}, reply)
    assert status == "flagged"
    assert 'coding-assistant' in review


@pytest.mark.parametrize("text", [
    r"Frequency $f = \frac{8}{20} = 0.40\text{ Hz}$.",
    r"$$\ce{H2 + O2 -> H2O}$$ and $x_{1}^{2}$.",
    r"Escaped braces $\{x\}$; escaped dollar $\text{\$5}$.",
    "Ordinary science prose, no formulas.",
])
def test_valid_formula_structure(text):
    assert not formula_issues(text)


@pytest.mark.parametrize("text", [
    r"$\frac{8}{20$", r"$x} + {y$", "$x", "$$x$", "$ $",
    r"\(f = 0.4\)", r"\[x\]",
])
def test_invalid_formula_structure(text):
    assert formula_issues(text)


def test_formula_failure_overrides_reviewer_and_requests_rewrite():
    def reply(model, messages, task):
        if task == "lesson-review":
            return json.dumps({"pass": True, "issues": []})
        assert "Unbalanced braces" in messages[-1]["content"]
        return r"Frequency $f = \frac{8}{20}$"

    lesson, review, status = review_and_revise(r"Frequency $f = \frac{8}{20$", {}, reply)
    assert status == "passed"
    assert not formula_issues(lesson)


def test_persistently_broken_formula_stays_flagged():
    broken = r"$\frac{8}{20$"

    def reply(model, messages, task):
        return json.dumps({"pass": True, "issues": []}) if task == "lesson-review" else broken

    lesson, review, status = review_and_revise(broken, {}, reply)
    assert lesson == broken and status == "flagged"
    assert "Unbalanced braces" in review


@pytest.mark.parametrize("formula", [r"$\frac{1}$", r"$\unknowncommand{x}$", r"$\sqrt[$"])
def test_katex_rejects_commands_beyond_brace_checks(formula):
    assert any("LaTeX rendering error" in issue for issue in formula_issues(formula))


def test_unavailable_formula_validator_never_passes_lesson(monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("node unavailable")
    monkeypatch.setattr("lesson_quality.subprocess.run", unavailable)
    lesson, review, status = review_and_revise("Frequency $f=1/T$", {},
        lambda *args, **kwargs: '{"pass":true,"issues":[]}')
    assert status == "unavailable"
