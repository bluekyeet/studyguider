import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import revision


def section(concept="Momentum", n=3):
    return {"concept": concept, "why": "You added the speeds instead of using momentum.", "teaching": "Momentum is $p = mv$ and it is conserved in a closed system.",
            "questions": [{"question": f"A 2.0 kg trolley moves at {v}.0 m s-1; find its momentum.", "expected_answer": f"p = mv = {2 * v}.0 kg m s-1"} for v in range(1, n + 1)]}


class Packs(unittest.TestCase):
    def test_a_good_pack_parses(self):
        sections = revision.parse_pack(json.dumps({"sections": [section(), section("Collisions", 2)]}))
        self.assertEqual([s["concept"] for s in sections], ["Momentum", "Collisions"])
        self.assertEqual(len(sections[0]["questions"]), 3)

    def test_latex_with_single_backslashes_and_a_fence_is_repaired(self):
        reply = "```json\n" + json.dumps({"sections": [section()]}).replace("$p = mv$", "$p = m\\vec{v}$").replace("\\\\vec", "\\vec") + "\n```"
        self.assertIn("vec", revision.parse_pack(reply)[0]["teaching"])

    def test_bad_packs_are_rejected(self):
        thin = section(n=1)
        for bad in ("not json", json.dumps({}), json.dumps({"sections": []}), json.dumps({"sections": [thin]}),
                    json.dumps({"sections": [{**section(), "teaching": ""}]}), json.dumps({"sections": [section()] * 6}),
                    json.dumps({"sections": [{**section(), "questions": [{"question": "short", "expected_answer": "x"}] * 2}]})):
            with self.assertRaises(ValueError, msg=bad[:40]):
                revision.parse_pack(bad)

    def test_questions_the_reviewer_fails_are_dropped_and_thin_sections_go(self):
        sections = revision.parse_pack(json.dumps({"sections": [section(n=4), section("Collisions", 2)]}))
        kept = revision.drop_failed(sections, {"fail": [{"section": 0, "question": 1, "reason": "x"}, {"section": 1, "question": 0, "reason": "y"}]})
        self.assertEqual([s["concept"] for s in kept], ["Momentum"])      # Collisions is left with one question, so it goes
        self.assertEqual(len(kept[0]["questions"]), 3)
        self.assertEqual(len(revision.drop_failed(sections, {})), 2)      # nothing failed
        self.assertEqual(len(revision.drop_failed(sections, "garbage")), 2)


if __name__ == "__main__":
    unittest.main()
