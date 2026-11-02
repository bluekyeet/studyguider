"""Opt-in real gateway check; no lesson records created.

PowerShell: Get-Content server/tests/live_reviewer_check.py -Raw |
  docker compose exec -T -e RUN_LIVE_REVIEW_CHECK=yes api python -
Two billed reviewer calls are recorded in normal usage accounting.
"""
import json
import os

from app import model_reply
from lesson_quality import review_and_revise
from reviews import _clean_json

assert os.environ.get("RUN_LIVE_REVIEW_CHECK") == "yes", "Explicit live-call opt-in required"

cases = [
    ("frequency", "Frequency is waves divided by elapsed time. Eight waves in twenty seconds is 0.40 Hz, not 2.5 Hz or metres.",
     "Frequency is time divided by waves. Eight waves in twenty seconds gives 2.5 m."),
    ("concentration", "At fixed temperature, increasing concentration increases collision frequency, not particle kinetic energy or the fraction exceeding activation energy.",
     "Increasing concentration at constant temperature makes each particle move faster and raises its kinetic energy. The fraction exceeding activation energy increases."),
    ("wavespeed", "Wave speed v equals frequency f times wavelength lambda, v = f lambda. A 5.0 Hz wave of wavelength 0.20 m travels at 1.0 m/s.",
     "Wave speed is v = f / lambda. A 5.0 Hz wave of wavelength 0.20 m travels at 25 m/s."),
    ("unit", "Kinetic energy is KE = (1/2) m v^2, measured in joules. A 2.0 kg trolley at 3.0 m/s has 9.0 J of kinetic energy.",
     "Kinetic energy is KE = (1/2) m v^2. A 2.0 kg trolley at 3.0 m/s has 9.0 N of kinetic energy."),
    ("moles", "Amount of substance n = m / M, in mol. 18 g of water (M = 18 g/mol) is 1.0 mol.",
     "Amount of substance n = M / m. 18 g of water (M = 18 g/mol) is 1.0 mol."),
]

for label, source, error in cases:
    captured = []

    def reviewer_only(model, messages, task):
        if task != "lesson-review":
            # Deliberately stop before teacher revision: measure original error detection.
            raise RuntimeError("Revision disabled in reviewer acceptance probe")
        reply = model_reply(model, messages, task="acceptance-seeded-review")
        captured.append(_clean_json(reply))
        return reply

    lesson = ("# Learning goal\nExplain " + label + ".\n# Explanation\n" + error +
              "\n# Worked example\n" + error +
              "\n### Your Turn 1\nExplain the definition in your own words."
              "\n### Your Turn 2\nExplain the relationship and state the relevant units."
              "\n### Your Turn 3\nDescribe a situation demonstrating this relationship."
              "\n# Summary\n" + error)
    evidence = {"sources": [{"resource_id": "synthetic-check", "page": 1, "content": source}]}
    review_and_revise(lesson, evidence, reviewer_only)
    assert len(captured) == 1, f"{label}: reviewer did not return parseable JSON"
    verdict = captured[0]
    print(label.upper(), json.dumps(verdict, ensure_ascii=True), flush=True)
    assert verdict.get("pass") is False and verdict.get("issues"), f"{label}: seeded error was not rejected"

print("PASS: both seeded drafts rejected. Inspect issues for scientific error detection, not merely structural complaints.")
