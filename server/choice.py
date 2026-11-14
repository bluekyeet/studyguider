"""Multiple-choice questions: the options a learner sees, the answer key the server keeps, and marking against it.

A multiple-choice question is one more answer form (answer_forms.py): {"kind": "choice", "options": [...], "multiple": bool,
"shuffle": bool, ...}. The key (which options are right, why each option is right or wrong, and any negative marking) never
goes into the form; it is stored beside the question (exam_questions.choice_key, review_questions.choice_key) and used only
to mark. Marking against a key is deterministic and needs no model.

The answer stays one piece of text (answer_media.py): the choice is its first line, "Choice: B" or "Choice: A, C", and any
working follows. A bare letter ("B", "(b)", "b.") is read as a choice too, so a client that ignores the form still works.
The contract is written up for the clients in docs/api/multiple-choice.md.
"""
import hashlib
import random
import re

KEYS = "ABCDEFGHIJ"
MAX_OPTIONS = len(KEYS)
SOURCES = ("official", "ai")
# Options that refer to the others ("All of the above", "Both A and B") only make sense in their printed place.
_FIXED = re.compile(r"\b(?:all|none|both|neither|either)\b.{0,20}\b(?:above|below|of these|options?|answers?)\b"
                    r"|\b(?:both|neither|either|only)\s+\(?[a-j]\)?\s*(?:and|or|nor|,)\s*\(?[a-j]\)?\b"
                    r"|^\(?[a-j]\)?\s*(?:and|or|&)\s*\(?[a-j]\)?$", re.I)
_CHOICE_LINE = re.compile(r"^\s*choices?\s*[:\-]\s*(.*)$", re.I)
_BARE = re.compile(r"^\s*\(?\s*([a-j])\s*\)?\s*[.)]?\s*$", re.I)
_TRUE_FALSE = {"true", "false"}


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ""


def _key_list(value, keys):
    """Option keys from a list or "A, C" string, upper-case, only those that exist, in alphabetical order."""
    if isinstance(value, str):
        value = re.findall(r"\b[A-Ja-j]\b", value)
    if not isinstance(value, (list, tuple)):
        return []
    found = {str(v).strip().strip("().").upper() for v in value if isinstance(v, (str, int))}
    return sorted(k for k in found if k in keys)


def normalise_form(item):
    """A choice form from a model or importer, checked and trimmed; None when it is not usable. Keys are re-lettered A, B, C
    in the given order when they are missing or not letters, so the key that goes with it must be normalised with key_map."""
    if not isinstance(item, dict):
        return None
    raw = item.get("options")
    if not isinstance(raw, list):
        return None
    options = []
    for index, option in enumerate(raw[:MAX_OPTIONS]):
        if isinstance(option, str):
            option = {"text": option}
        if not isinstance(option, dict):
            continue
        text = _text(option.get("text"), 2000)
        image = option.get("image") if isinstance(option.get("image"), str) and option["image"].startswith("/") else ""
        if not text and not image:
            continue
        entry = {"key": KEYS[len(options)], "text": text}
        if image:
            entry["image"] = image[:500]
        entry["_given"] = str(option.get("key") or KEYS[index]).strip().strip("().").upper()[:3]
        options.append(entry)
    if len(options) < 2:
        return None
    texts = {o["text"].strip(" .").lower() for o in options}
    true_false = len(options) == 2 and texts == _TRUE_FALSE
    multiple = bool(item.get("multiple")) and not true_false
    shuffle = item.get("shuffle", True) is not False and not true_false and not any(_FIXED.search(o["text"]) for o in options)
    penalty = item.get("penalty")
    penalty = float(penalty) if isinstance(penalty, (int, float)) and not isinstance(penalty, bool) and 0 < penalty <= 10 else 0
    instructions = _text(item.get("instructions"), 200) or (
        "Choose true or false." if true_false else "Select all that apply." if multiple else "Choose one answer.")
    return {"kind": "choice", "options": options, "multiple": multiple, "shuffle": shuffle,
            "instructions": instructions, "group": _text(item.get("group"), 80), "penalty": penalty}


def key_map(form):
    """{key as given by the source: key as stored} for a normalised form, so a key written against the source's own letters
    ("(c)", "3") still names the right option."""
    mapping = {}
    for index, option in enumerate(form["options"]):
        mapping.setdefault(option.get("_given", option["key"]), option["key"])
        mapping.setdefault(str(index + 1), option["key"])
    return mapping


def normalise_key(value, form, source="ai"):
    """The stored answer key for a form: {"correct": [...], "explanations": {key: text}, "partial": bool, "source": ...}.
    None when no option is named correct (the question is then marked by the AI marker)."""
    if not isinstance(value, dict) or form is None:
        return None
    mapping = key_map(form)
    keys = [o["key"] for o in form["options"]]
    named = value.get("correct", value.get("answer", value.get("correct_keys")))
    if isinstance(named, str):
        named = re.findall(r"\b[A-Ja-j1-9]\b", named) if re.fullmatch(r"[\sA-Ja-j1-9,;/&()and.]*", named) else [named]
    if not isinstance(named, (list, tuple)):
        named = [named] if isinstance(named, (int, str)) else []
    # A key may name an option by its wording instead of its letter ("RAM", "True").
    by_text = {re.sub(r"\W+", " ", o["text"]).strip().lower(): o["key"] for o in form["options"] if o["text"]}
    correct = sorted({mapping.get(str(v).strip().strip("().").upper()) or by_text.get(re.sub(r"\W+", " ", str(v)).strip().lower(), "")
                      for v in named} - {""})
    correct = [k for k in correct if k in keys]
    if not correct or (not form["multiple"] and len(correct) != 1):
        return None
    explanations = {}
    raw = value.get("explanations") if isinstance(value.get("explanations"), dict) else {}
    for given, text in raw.items():
        key = mapping.get(str(given).strip().strip("().").upper())
        if key and isinstance(text, str) and text.strip():
            explanations[key] = text.strip()[:2000]
    return {"correct": correct, "explanations": explanations, "partial": bool(value.get("partial")) and form["multiple"],
            "source": source if source in SOURCES else "ai"}


def public(form):
    """The form as a client sees it: no hidden fields and never the key."""
    clean = {k: v for k, v in form.items() if not k.startswith("_")}
    clean["options"] = [{k: v for k, v in o.items() if not k.startswith("_")} for o in form["options"]]
    return clean


def with_order(form, seed):
    """The form with display_order set for one attempt: shuffled when allowed, the same order for the same seed."""
    keys = [o["key"] for o in form["options"]]
    if form.get("shuffle"):
        rng = random.Random(int(hashlib.sha256(str(seed).encode()).hexdigest()[:12], 16))
        order = keys[:]
        for _ in range(3):      # a shuffle that leaves every option in place is no shuffle
            rng.shuffle(order)
            if order != keys:
                break
        keys = order
    return {**public(form), "display_order": keys}


def chosen(answer, form):
    """The option keys an answer picked, from its "Choice:" line or a bare letter; [] when it picked none."""
    keys = [o["key"] for o in form["options"]] if form else list(KEYS)
    text = (answer or "").strip()
    if not text:
        return []
    first = text.splitlines()[0]
    line = _CHOICE_LINE.match(first)
    if line:
        picked = _key_list(line.group(1), keys)
        if not picked and form:
            # "Choice: True" or the option's own words.
            words = line.group(1).strip(" .").lower()
            picked = [o["key"] for o in form["options"] if o["text"].strip(" .").lower() == words]
        return picked if form is None or form["multiple"] else picked[:1]
    bare = _BARE.match(text)
    if bare and bare.group(1).upper() in keys:
        return [bare.group(1).upper()]
    if form and text.strip(" .").lower() in _TRUE_FALSE:
        return [o["key"] for o in form["options"] if o["text"].strip(" .").lower() == text.strip(" .").lower()][:1]
    return []


def answer_text(keys, working=""):
    """The answer text for a selection (what the clients send)."""
    line = "Choice: " + ", ".join(sorted(keys))
    return line + ("\n\n" + working.strip() if working and working.strip() else "")


def mark(form, key, answer, marks=1):
    """Mark one answer against the key. marks is what the question is worth (a number; 2.5 is fine).

    Returns choice_result (docs/api/multiple-choice.md): exact means exactly the right set was chosen. Select all that apply
    gets part marks only when the key says the paper allows them: (right picks - wrong picks) / number right, never below 0.
    Negative marking takes the form's penalty off a wrong or partly wrong answer; a blank answer loses nothing."""
    picked = chosen(answer, form)
    correct = key["correct"]
    exact = sorted(picked) == sorted(correct)
    if exact:
        fraction = 1.0
    elif form["multiple"] and key.get("partial") and picked:
        right = len(set(picked) & set(correct))
        wrong = len(set(picked) - set(correct))
        fraction = max(0.0, (right - wrong) / len(correct))
    else:
        fraction = 0.0
    awarded = round(marks * fraction, 2)
    penalty = round(form.get("penalty") or 0, 2) if picked and not exact else 0
    options = []
    for option in form["options"]:
        options.append({**{k: v for k, v in option.items() if not k.startswith("_")},
                        "correct": option["key"] in correct, "chosen": option["key"] in picked,
                        "explanation": key.get("explanations", {}).get(option["key"], "")})
    return {"chosen": picked, "correct_keys": correct, "options": options, "exact": exact,
            "marks_awarded": awarded, "marks_available": marks, "penalty_applied": penalty,
            "net_marks": round(awarded - penalty, 2), "marked_by": "answer-key", "key_source": key.get("source", "ai")}


def _option_name(option):
    return option["text"].rstrip(" .") or "the option shown as a picture"


def feedback(result):
    """Plain-language feedback for a marked choice, naming options by their words (letters change when options are shuffled)."""
    by_key = {o["key"]: o for o in result["options"]}
    right = [by_key[k] for k in result["correct_keys"]]
    picked = [by_key[k] for k in result["chosen"]]
    right_names = "; ".join(_option_name(o) for o in right)
    lines = []
    if not picked:
        lines.append(f"No option was chosen. The answer is: {right_names}.")
    elif result["exact"]:
        lines.append(f"Correct: {right_names}.")
    else:
        lines.append(f"Not quite. The answer is: {right_names}. You chose: {'; '.join(_option_name(o) for o in picked)}.")
    for option in right:
        if option["explanation"]:
            lines.append(f"Why {_option_name(option)} is right: {option['explanation']}")
    for option in picked:
        if not option["correct"] and option["explanation"]:
            lines.append(f"Why {_option_name(option)} is wrong: {option['explanation']}")
    missed = [o for o in right if not o["chosen"]] if picked else []
    if result["options"] and missed and len(right) > 1:
        lines.append("You also needed: " + "; ".join(_option_name(o) for o in missed) + ".")
    if result["penalty_applied"]:
        lines.append(f"This paper takes {result['penalty_applied']:g} marks off for a wrong answer.")
    if result.get("key_source") == "ai":
        lines.append("The answer key was written by AI, not taken from the paper's marking guide; check it if it looks wrong.")
    return "\n\n".join(lines)


def key_text(form, key):
    """The key written out for a marker or a review's expected answer."""
    by_key = {o["key"]: o for o in form["options"]}
    lines = ["Correct option" + ("s" if len(key["correct"]) > 1 else "") + ": " +
             "; ".join(f"{k}. {_option_name(by_key[k])}" for k in key["correct"])]
    for option in form["options"]:
        why = key.get("explanations", {}).get(option["key"])
        if why:
            lines.append(f"{option['key']}. {_option_name(option)}: {why}")
    return "\n".join(lines)


def forms_with_order(forms, seed):
    """A list of answer forms with every choice form given its display order for this attempt."""
    if not isinstance(forms, list):
        return forms
    return [with_order(f, seed) if isinstance(f, dict) and f.get("kind") == "choice" else f for f in forms]


def find(forms):
    """The choice form in a list of forms, or None."""
    return next((f for f in forms or [] if isinstance(f, dict) and f.get("kind") == "choice"), None)


# For prompts that write practice questions: when to use multiple choice, and its JSON shape.
PROMPT = ("When the instructions say to include multiple-choice questions, write those as: question (the stem only, without the "
          "options), answer_forms [{\"kind\": \"choice\", \"options\": [{\"key\": \"A\", \"text\": ...}, ...], \"multiple\": false "
          "for one best answer or true for select all that apply, \"shuffle\": false only when an option refers to the others}, "
          "{\"kind\": \"text\"}], and choice_key {\"correct\": [\"B\"], \"explanations\": {\"A\": why A is wrong, \"B\": why B is "
          "right, ...}}. Give four or five options (two for true/false), one clearly best answer, and distractors that are "
          "plausible because each one matches a common mistake or misconception, which its explanation names. Options are "
          "similar in length and style; avoid \"all of the above\". Use $...$ LaTeX in options where needed.")


def format_instruction(question_format):
    """What a practice generator is told about multiple choice, from how the paper is assessed (curriculum.question_format).
    Empty for a paper assessed by written answers: its practice stays written."""
    if question_format == "multiple_choice":
        return (" This paper is assessed by multiple choice, so write every question as a multiple-choice question worth 1 or 2 "
                "marks. " + PROMPT)
    if question_format == "mixed":
        return (" This paper is assessed partly by multiple choice, so write about half of the questions as multiple-choice "
                "questions worth 1 or 2 marks and the rest as written questions. " + PROMPT)
    return ""
