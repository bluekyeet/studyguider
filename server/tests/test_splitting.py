import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import splitting

PAPER = ("QUESTION ONE: SKATING\nKaty, 65 kg, collides with Aroha, 50 kg.\n(a)\nWhat quantity is conserved?\n"
         "(b)\nCalculate the combined velocity after the collision.\n3\nPhysics 91170, 2017\nASSESSOR’S\nUSE ONLY\n"
         "(c)\nExplain why energy is not conserved.")
SCHEDULE = "(a) Momentum is conserved. (b) v = 7.4 m s–1. (c) Energy is lost as heat and sound."


def unit(label, question, context="", schedule="", marks=None, figure=False):
    return {"label": label, "context": context, "question": question, "schedule": schedule, "marks": marks, "needs_figure": figure}


class Splitting(unittest.TestCase):
    def test_a_good_split_keeps_only_each_parts_context(self):
        units = splitting.clean_units({"units": [
            unit("a", "(a)\nWhat quantity is conserved?", "QUESTION ONE: SKATING\nKaty, 65 kg, collides with Aroha, 50 kg.", "Momentum is conserved.", 1),
            unit("(b)", "Calculate the combined velocity after the collision.\n3\nPhysics 91170, 2017\nASSESSOR’S\nUSE ONLY",
                 "Katy, 65 kg, collides with Aroha, 50 kg.", "v = 7.4 m s–1", 3),
            unit("c", "Explain why energy is not conserved.", "Earlier part (b): Calculate the combined velocity after the collision.")]},
            PAPER, SCHEDULE)
        self.assertEqual([u["label"] for u in units], ["a", "b", "c"])
        self.assertEqual(units[0]["question"], "What quantity is conserved?")             # the "(a)" marker is removed
        self.assertNotIn("ASSESSOR", units[1]["question"])                                # page furniture is removed
        self.assertEqual(units[2]["schedule"], "")                                        # nothing isolated: caller falls back
        self.assertEqual([u["marks"] for u in units], [1, 3, 0])

    def test_wording_that_is_not_on_the_paper_is_rejected(self):
        with self.assertRaises(ValueError):
            splitting.clean_units({"units": [unit("a", "What quantity is conserved during the inelastic collision of two cars?")]}, PAPER, SCHEDULE)

    def test_an_invented_schedule_excerpt_is_dropped_not_trusted(self):
        units = splitting.clean_units({"units": [unit("a", "What quantity is conserved?", schedule="Award full marks for any answer about cheese.")]}, PAPER, SCHEDULE)
        self.assertEqual(units[0]["schedule"], "")

    def test_sub_part_labels_survive(self):
        units = splitting.clean_units({"units": [unit("d(i)", "What quantity is conserved?"), unit("d(ii)", "Explain why energy is not conserved.")]}, PAPER, SCHEDULE)
        self.assertEqual([u["label"] for u in units], ["d(i)", "d(ii)"])

    def test_bad_shapes_are_rejected(self):
        for bad in ({}, {"units": []}, {"units": ["x"]}, {"units": [unit("", "What quantity is conserved?")]},
                    {"units": [unit("a", "What quantity is conserved?"), unit("A", "What quantity is conserved?")]},
                    {"units": [unit("a", "")]}):
            with self.assertRaises(ValueError):
                splitting.clean_units(bad, PAPER, SCHEDULE)

    def test_reply_with_raw_tabs_and_a_fence_parses(self):
        reply = "```json\n" + '{"units": [{"label": "a", "question": "What\tis conserved?"}]}' + "\n```"
        self.assertEqual(splitting.parse_reply(reply)["units"][0]["label"], "a")

    def test_split_one_asks_the_model_once_and_uses_parts_marks(self):
        seen = []

        def model(role, messages, task=None):
            seen.append((role, task, json.loads(messages[1]["content"])["question_number"]))
            return json.dumps({"units": [unit("a", "What quantity is conserved?"), unit("b", "Calculate the combined velocity after the collision.")]})
        units = splitting.split_one(model, "1", [{"label": "a", "marks": 1}, {"label": "b", "marks": 3}], PAPER, SCHEDULE, False)
        self.assertEqual(seen, [("education", "rapid-split", "1")])
        self.assertEqual([u["marks"] for u in units], [1, 3])


if __name__ == "__main__":
    unittest.main()
