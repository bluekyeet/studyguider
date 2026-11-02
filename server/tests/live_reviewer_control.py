"""Opt-in live control: correct drafts the reviewer should NOT reject for science.

PowerShell: Get-Content server/tests/live_reviewer_control.py -Raw |
  docker compose exec -T -e RUN_LIVE_REVIEW_CHECK=yes api python -
Five billed reviewer calls. Prints each verdict; the point is the false-positive rate on
scientific grounds, so read the issues rather than relying on pass/fail alone.
"""
import json
import os

from app import model_reply
from lesson_quality import review_and_revise
from reviews import _clean_json

assert os.environ.get("RUN_LIVE_REVIEW_CHECK") == "yes", "Explicit live-call opt-in required"

cases = [
    ("frequency", "Frequency is waves divided by elapsed time. Eight waves in twenty seconds is 0.40 Hz.",
     "Frequency is waves divided by elapsed time. Eight waves in twenty seconds gives 0.40 Hz."),
    ("concentration", "At fixed temperature, increasing concentration increases collision frequency, not particle kinetic energy.",
     "Increasing concentration at constant temperature raises collision frequency. Particle kinetic energy is unchanged."),
    ("wavespeed", "Wave speed v equals frequency f times wavelength lambda. A 5.0 Hz wave of wavelength 0.20 m travels at 1.0 m/s.",
     "Wave speed is v = f lambda. A 5.0 Hz wave of wavelength 0.20 m travels at 1.0 m/s."),
    ("unit", "Kinetic energy is KE = (1/2) m v^2, measured in joules. A 2.0 kg trolley at 3.0 m/s has 9.0 J.",
     "Kinetic energy is KE = (1/2) m v^2, in joules. A 2.0 kg trolley at 3.0 m/s has 9.0 J of kinetic energy."),
    ("moles", "Amount of substance n = m / M, in mol. 18 g of water (M = 18 g/mol) is 1.0 mol.",
     "Amount of substance n = m / M. 18 g of water (M = 18 g/mol) is 1.0 mol."),
]

rejected = 0
for label, source, text in cases:
    captured = []

    def reviewer_only(model, messages, task):
        if task != "lesson-review":
            raise RuntimeError("Revision disabled in control probe")
        reply = model_reply(model, messages, task="acceptance-control-review")
        captured.append(_clean_json(reply))
        return reply

    lesson = ("# Learning goal\nExplain " + label + ".\n# Explanation\n" + text +
              "\n# Worked example\n" + text +
              "\n### Your Turn 1\nExplain the definition in your own words."
              "\n### Your Turn 2\nExplain the relationship and state the relevant units."
              "\n### Your Turn 3\nDescribe a situation demonstrating this relationship."
              "\n# Summary\n" + text)
    evidence = {"sources": [{"resource_id": "synthetic-check", "page": 1, "content": source}]}
    try:
        review_and_revise(lesson, evidence, reviewer_only)
    except RuntimeError:
        pass
    assert captured, f"{label}: reviewer returned no parseable JSON"
    print(label.upper(), json.dumps(captured[0], ensure_ascii=True), flush=True)
    rejected += captured[0].get("pass") is not True
print(f"DONE: {rejected} of {len(cases)} correct drafts were rejected; read the issues to see whether any are scientific.")
