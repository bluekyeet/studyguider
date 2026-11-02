"""Opt-in real bounded teacher/reviewer loop; no lessons saved.

Get-Content server/tests/live_revision_check.py -Raw |
  docker compose exec -T -e RUN_LIVE_REVISION_CHECK=yes api python -
Up to five real calls retained in normal usage accounting.
"""
import json
import os

from app import model_reply
from lesson_quality import formula_issues, review_and_revise
from reviews import _clean_json

assert os.environ.get("RUN_LIVE_REVISION_CHECK") == "yes"
source = "Frequency is number of complete cycles divided by elapsed time: f=N/t, in Hz (cycles per second). Eight waves in twenty seconds gives 0.40 Hz. Twelve waves in six seconds gives 2 Hz. Six waves in three seconds gives 2 Hz. Ten waves in five seconds gives 2 Hz."
evidence = {"sources": [{"resource_id": "synthetic-frequency", "page": 1, "content": source}], "standards": []}
draft = """# Learning goal
Calculate frequency from complete waves and elapsed time.
# Prior knowledge
Count waves and measure seconds.
# Explanation
Frequency is time divided by waves, in metres. [synthetic-frequency p. 1]
# Worked example
Eight waves in twenty seconds gives 2.5 m. [synthetic-frequency p. 1]
### Your Turn 1
Twelve complete waves pass in six seconds. Calculate frequency and include units.
### Your Turn 2
Six complete waves pass in three seconds. Calculate frequency and include units.
### Your Turn 3
Ten complete waves pass in five seconds. Calculate frequency and include units.
# Summary
Use time divided by waves to find frequency. [synthetic-frequency p. 1]
"""
calls = []
first_verdict = None


def model(name, messages, task):
    global first_verdict
    calls.append((name, task))
    result = model_reply(name, messages, task="acceptance-" + task)
    if task == "lesson-review" and first_verdict is None:
        first_verdict = _clean_json(result)
    return result


lesson, review, status = review_and_revise(draft, evidence, model)
print("CALLS", calls)
print("FIRST_REVIEW", json.dumps(first_verdict, ensure_ascii=True))
print("FINAL_STATUS", status, "FINAL_REVIEW", review)
print("FINAL_DRAFT", lesson)
assert first_verdict and first_verdict["pass"] is False, "Initial seeded error was not rejected"
assert any(task == "lesson-revise" for _, task in calls), "Teacher revision never ran"
assert status == "passed", "Bounded live correction did not pass; inspect recorded output"
assert not formula_issues(lesson)
assert "Hz" in lesson and ("0.4" in lesson or "0.40" in lesson), "Expected corrected value/units absent"
print("PASS: real reviewer rejected seeded error, teacher revised, final review and formula checks passed; not human verification")
