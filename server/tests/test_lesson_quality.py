import json

import pytest

from lesson_quality import review_and_revise, contamination_issues, formula_issues, teaching_structure_issues


def practice_sections(count=3):
    return "\n".join(f"### Your Turn {i}\nExplain what frequency measures." for i in range(1, count + 1))


def synthetic_lesson(explanation="Frequency is the number of cycles per second."):
    return "# Learning goal\nExplain frequency.\n## Explanation\n" + explanation + "\n## Worked example\nEight cycles in twenty seconds means 0.4 cycles per second.\n" + practice_sections()


@pytest.mark.parametrize("count", [3, 4, 5])
def test_practice_page_structure(count):
    assert not teaching_structure_issues("# Learning goal\nUnderstand waves.\n" + practice_sections(count))


@pytest.mark.parametrize("text", [
    "Draft", practice_sections(2), practice_sections(6),
    practice_sections().replace("### Your Turn 2", "## Your Turn 2"),
    practice_sections().replace("### Your Turn 2", "### Your Turn 1"),
    practice_sections().replace("### Your Turn 2", "### Your Turn 4"),
    practice_sections().replace("### Your Turn 2", "### Your Turn 2: Waves"),
    practice_sections().replace("### Your Turn 2\nExplain what frequency measures.", "### Your Turn 2\n---"),
    practice_sections().replace("### Your Turn 2\n", "### Your Turn 2\n## Other section\n"),
    "```markdown\n" + practice_sections() + "\n```",
    "~~~~markdown\n" + practice_sections() + "\n~~~~",
    practice_sections().replace("###", "####"),
])
def test_malformed_practice_page_structure(text):
    assert teaching_structure_issues(text)


def test_structural_check_does_not_claim_semantic_validation():
    # Intentional ceiling: meaning/solutions still require independent review.
    assert not teaching_structure_issues(practice_sections().replace("Explain what frequency measures.", "Answer: 42."))


def test_code_fence_does_not_supply_a_question_body():
    text = practice_sections().replace("### Your Turn 2\nExplain what frequency measures.",
                                      "### Your Turn 2\n```\nNot a question\n``` ")
    assert any("empty" in issue for issue in teaching_structure_issues(text))


def test_rejected_lesson_is_rewritten_then_rechecked():
    corrected = synthetic_lesson()
    replies = iter([json.dumps({"pass": False, "issues": ["Wrong unit"]}), corrected, json.dumps({"pass": True, "issues": []})])
    calls = []
    def reply(model, messages, task):
        calls.append(task)
        return next(replies)
    lesson, review, status = review_and_revise(synthetic_lesson("Frequency is measured in metres."), {}, reply)
    assert lesson == corrected and status == "passed"
    assert calls == ["lesson-review", "lesson-revise", "lesson-review"]


@pytest.mark.parametrize("draft", [
    "Draft", synthetic_lesson().replace("### Your Turn 2", "## Your Turn 2"),
    synthetic_lesson().replace("### Your Turn 2\nExplain what frequency measures.", "### Your Turn 2\n"),
])
def test_structure_failure_overrides_approval_and_stays_flagged(draft):
    calls = []

    def reply(model, messages, task):
        calls.append(task)
        return '{"pass":true,"issues":[]}' if task == "lesson-review" else draft

    lesson, review, status = review_and_revise(draft, {}, reply)
    assert lesson == draft and status == "flagged"
    assert json.loads(review)["pass"] is False
    assert all(issue in json.loads(review)["issues"] for issue in teaching_structure_issues(draft))
    assert calls == ["lesson-review", "lesson-revise", "lesson-review", "lesson-revise", "lesson-review"]


def test_structure_failure_can_be_rewritten_and_promoted():
    corrected = synthetic_lesson()

    def reply(model, messages, task):
        if task == "lesson-review":
            return '{"pass":true,"issues":[]}'
        assert "3–5 Your Turn sections" in messages[-1]["content"]
        return corrected

    lesson, review, status = review_and_revise("Draft", {}, reply)
    assert (lesson, json.loads(review), status) == (corrected, {"pass": True, "issues": []}, "passed")


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
        return synthetic_lesson(r"Frequency $f = \frac{8}{20}$")

    lesson, review, status = review_and_revise(synthetic_lesson(r"Frequency $f = \frac{8}{20$"), {}, reply)
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
