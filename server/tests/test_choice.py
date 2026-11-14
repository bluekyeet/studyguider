import json

import answer_forms
import choice
import marking


def form(options=("2.0 m/s", "4.0 m/s", "6.0 m/s", "8.0 m/s"), **extra):
    return choice.normalise_form({"options": [{"key": k, "text": t} for k, t in zip("ABCDEFGH", options)], **extra})


def test_a_form_is_relettered_and_keeps_its_source_letters_for_the_key():
    found = choice.normalise_form({"options": [{"key": "(a)", "text": "RAM"}, {"key": "(b)", "text": "HDD"}, {"key": "(c)", "text": "SSD"}]})
    assert [o["key"] for o in found["options"]] == ["A", "B", "C"]
    key = choice.normalise_key({"correct": ["(a)"], "explanations": {"a": "Volatile memory.", "c": "Keeps data without power."}}, found, "official")
    assert key["correct"] == ["A"] and key["source"] == "official"
    assert set(key["explanations"]) == {"A", "C"}
    assert "_given" not in json.dumps(choice.public(found))


def test_unusable_forms_and_keys_are_refused():
    assert choice.normalise_form({"options": [{"text": "Only one"}]}) is None
    assert choice.normalise_form({"options": "A, B"}) is None
    single = form()
    assert choice.normalise_key({"correct": ["A", "B"]}, single) is None        # one best answer cannot have two
    assert choice.normalise_key({"correct": ["Z"]}, single) is None
    assert choice.normalise_key({"correct": "C"}, single)["correct"] == ["C"]


def test_true_false_and_options_that_refer_to_others_are_never_shuffled():
    true_false = form(("True", "False"), multiple=True)
    assert not true_false["shuffle"] and not true_false["multiple"] and true_false["instructions"] == "Choose true or false."
    assert not form(("RAID 0", "RAID 1", "Both A and B", "None of the above"))["shuffle"]
    assert form()["shuffle"]


def test_display_order_is_shuffled_per_attempt_and_stable_for_the_same_attempt():
    found = form(("one", "two", "three", "four", "five"))
    first, again = choice.with_order(found, "exam:1:7:"), choice.with_order(found, "exam:1:7:")
    assert first["display_order"] == again["display_order"]
    assert sorted(first["display_order"]) == ["A", "B", "C", "D", "E"]
    orders = {tuple(choice.with_order(found, f"exam:{n}:7:")["display_order"]) for n in range(12)}
    assert len(orders) > 3 and ("A", "B", "C", "D", "E") not in orders
    fixed = form(("True", "False"))
    assert choice.with_order(fixed, "x")["display_order"] == ["A", "B"]


def test_answers_are_read_from_the_choice_line_or_a_bare_letter():
    single = form()
    assert choice.chosen("Choice: B", single) == ["B"]
    assert choice.chosen("choice: b\n\nworking: 2 x 3 = 1.5 v", single) == ["B"]
    assert choice.chosen("(c)", single) == ["C"]
    assert choice.chosen("D.", single) == ["D"]
    assert choice.chosen("Choice: A, C", single) == ["A"]        # one best answer keeps the first pick
    assert choice.chosen("The answer is B because", single) == []
    assert choice.chosen("", single) == []
    many = form(multiple=True)
    assert choice.chosen("Choice: C, A", many) == ["A", "C"]
    assert choice.chosen("True", form(("True", "False"))) == ["A"]
    assert choice.answer_text(["C", "A"], "because") == "Choice: A, C\n\nbecause"


def test_marking_is_exact_for_one_best_answer_with_feedback_on_the_wrong_option():
    single = form()
    key = choice.normalise_key({"correct": ["B"], "explanations": {"A": "This halves the speed.", "B": "Momentum is conserved."}}, single, "official")
    right = choice.mark(single, key, "Choice: B", 2.5)
    assert right["exact"] and right["marks_awarded"] == 2.5 and right["net_marks"] == 2.5
    wrong = choice.mark(single, key, "Choice: A", 2.5)
    assert not wrong["exact"] and wrong["marks_awarded"] == 0
    text = choice.feedback(wrong)
    assert "4.0 m/s" in text and "This halves the speed." in text and "Momentum is conserved." in text
    assert [o["chosen"] for o in wrong["options"]] == [True, False, False, False]


def test_select_all_gets_part_marks_only_when_the_guide_allows_it():
    many = form(multiple=True)
    strict = choice.normalise_key({"correct": ["A", "C"]}, many)
    assert choice.mark(many, strict, "Choice: A", 2)["marks_awarded"] == 0
    assert choice.mark(many, strict, "Choice: A, C", 2)["exact"]
    partial = choice.normalise_key({"correct": ["A", "C"], "partial": True}, many)
    assert choice.mark(many, partial, "Choice: A", 2)["marks_awarded"] == 1
    assert choice.mark(many, partial, "Choice: A, B", 2)["marks_awarded"] == 0      # one right, one wrong
    assert choice.mark(many, partial, "Choice: A, B, C", 2)["marks_awarded"] == 1


def test_negative_marking_takes_marks_off_a_wrong_answer_but_not_a_blank_one():
    penalised = form(penalty=0.25)
    key = choice.normalise_key({"correct": ["B"]}, penalised)
    assert choice.mark(penalised, key, "Choice: A", 1)["net_marks"] == -0.25
    assert choice.mark(penalised, key, "", 1)["net_marks"] == 0
    assert choice.mark(penalised, key, "Choice: B", 1)["net_marks"] == 1
    assert "takes 0.25 marks off" in choice.feedback(choice.mark(penalised, key, "Choice: A", 1))


def test_an_ai_written_key_says_so_in_the_feedback():
    single = form()
    key = choice.normalise_key({"correct": ["B"]}, single, "ai")
    assert "written by AI" in choice.feedback(choice.mark(single, key, "Choice: B"))


def test_generated_questions_keep_their_key_apart_from_the_form():
    forms, key, text = answer_forms.with_choice(
        [{"kind": "choice", "options": [{"key": "A", "text": "Lower temperature"}, {"key": "B", "text": "Add a catalyst"}]}, {"kind": "text"}],
        {"correct": ["B"], "explanations": {"A": "Fewer successful collisions."}}, text="Which change increases the rate?")
    assert forms[0]["kind"] == "choice" and "correct" not in json.dumps(forms)
    assert key["correct"] == ["B"] and key["source"] == "ai"
    # Without a usable key the options become part of a written question, so it can still be marked.
    forms, key, text = answer_forms.with_choice(
        [{"kind": "choice", "options": [{"text": "Lower temperature"}, {"text": "Add a catalyst"}]}], {"correct": ["Q"]}, text="Which change?")
    assert key is None and not any(f["kind"] == "choice" for f in forms) and "B. Add a catalyst" in text


def test_a_stored_choice_form_survives_normalising_and_merging():
    stored = choice.public(form())
    assert answer_forms.normalise([stored, {"kind": "text"}])[0]["options"] == stored["options"]
    merged = answer_forms.merged({"": [stored, {"kind": "text", "palette": "general"}], "(b)": [{"kind": "drawing", "background": "blank", "purpose": ""}]})
    assert [f["kind"] for f in merged] == ["choice", "text"]


def test_practice_is_told_to_use_multiple_choice_only_when_the_paper_is_assessed_that_way():
    assert choice.format_instruction("written") == ""
    assert "every question" in choice.format_instruction("multiple_choice")
    assert "about half" in choice.format_instruction("mixed")


def test_a_missed_choice_comes_back_as_free_recall_when_the_stem_stands_alone():
    single = form(("RAM", "HDD", "CD", "SSD"))
    key = choice.normalise_key({"correct": ["A"]}, single, "official")
    text, expected, forms, review_key = marking.choice_review("Name the volatile storage in a computer.", single, key)
    assert forms is None and review_key is None and "RAM" in expected
    text, expected, forms, review_key = marking.choice_review("Which of the following statements is FALSE?", single, key)
    assert forms[0]["kind"] == "choice" and review_key == key


def test_part_answers_are_matched_whatever_the_label_spelling():
    answer = json.dumps({"parts": {"(a)": "Choice: B", "(b)(ii)": "Choice: C"}})
    assert marking._part_answers(answer, ["a", "b(ii)"]) == {"a": "Choice: B", "b(ii)": "Choice: C"}
    assert marking._part_answers("Choice: D", [""]) == {"": "Choice: D"}
    assert marking._part_answers("not json", ["a"]) == {"a": ""}


class KeyDB:
    """The one query key_marking makes, for a question of two multiple-choice parts worth 1 and 2 marks."""

    def __init__(self, keys, parts, marks=3, exact=None):
        self.row = (keys, {"a": [choice.public(form())], "b": [choice.public(form(multiple=True))]}, parts, "Q", marks, exact, "Physics")

    def execute(self, sql, params=()):
        class Result:
            def __init__(self, row): self.row = row
            def fetchone(self): return self.row
        return Result(self.row)


def test_an_all_choice_question_is_marked_from_its_keys_without_a_model():
    parts = [{"label": "a", "text": "(a)", "marks": 1}, {"label": "b", "text": "(b)", "marks": 2}]
    keys = {"a": {"correct": ["B"], "explanations": {}, "source": "official"}, "b": {"correct": ["A", "C"], "explanations": {}, "source": "official"}}
    result = marking.key_marking(KeyDB(keys, parts), 9, json.dumps({"parts": {"(a)": "Choice: B", "(b)": "Choice: A"}}))
    assert result["marked_by"] == "answer-key" and result["confidence"] == 1.0
    assert result["choice_results"]["a"]["exact"] and not result["choice_results"]["b"]["exact"]
    assert result["net_marks"] == 1 and result["marks_awarded"] == 1 and result["marks_available"] == 3
    # A part without a key goes to the AI marker instead.
    assert marking.key_marking(KeyDB({"a": keys["a"]}, parts), 9, "{}") is None


def test_fractional_printed_marks_are_kept_in_net_marks():
    db = KeyDB({"": {"correct": ["B"], "explanations": {}, "source": "official"}}, [], marks=3, exact=2.5)
    db.row = (db.row[0], {"": [choice.public(form())]}, *db.row[2:])
    result = marking.key_marking(db, 9, "Choice: B")
    assert result["net_marks"] == 2.5 and result["net_marks_available"] == 2.5 and result["marks_awarded"] == 3


def test_a_key_can_name_the_option_by_its_words():
    found = form(("RAM", "HDD", "SSD"))
    assert choice.normalise_key({"correct": "RAM"}, found)["correct"] == ["A"]
    assert choice.normalise_key({"correct": ["ssd"]}, found)["correct"] == ["C"]
    assert choice.normalise_key({"correct": "B and C"}, form(multiple=True))["correct"] == ["B", "C"]


def test_code_written_as_texttt_outside_maths_becomes_markdown_code():
    assert choice.plain_code(r'Search \texttt{"timetable" site:auckland.ac.nz}') == 'Search `"timetable" site:auckland.ac.nz`'
    assert choice.plain_code(r"Keep $\texttt{x}$ in maths") == r"Keep $\texttt{x}$ in maths"
