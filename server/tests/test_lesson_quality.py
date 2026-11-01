import json

from lesson_quality import review_and_revise, contamination_issues


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
