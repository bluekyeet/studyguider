"""Split a past-paper question into its lettered parts for rapid practice.

An NCEA question ("Question One") has parts (a), (b), (c)(i), (c)(ii). Some share a set-up, some stand alone.
For rapid practice each part becomes its own row in exam_questions (parent_id points at the whole question)
holding only the context that part needs, so marking, answers, revision and lessons work on it unchanged.

The model only chooses where to cut. Everything it returns must be wording that is in the paper text
(checked word by word); a split that invents or rewrites text is rejected and the whole question is
served as before. The learner is never shown text that is not on the original paper.
"""
import contextvars
import json
import logging
import re
import threading

import userspace

log = logging.getLogger("uvicorn.error")

MAX_UNITS = 20
MIN_GROUNDED_QUESTION = 0.92    # share of a unit's words that must appear in the paper text
MIN_GROUNDED_SCHEDULE = 0.85    # share of a schedule excerpt's words that must appear in the schedule text

SPLIT_SYSTEM = (
    "You split one NCEA exam question into separate rapid-practice units, one per lettered or numbered part "
    "that is answered on its own: (a), (b), (c)(i), (c)(ii) and so on. Return only a JSON object "
    "{\"units\": [{\"label\": string, \"context\": string, \"question\": string, \"marks\": integer|null, "
    "\"schedule\": string, \"needs_figure\": boolean}]}.\n"
    "Rules:\n"
    "1. Copy wording exactly as it appears in question_text. Never rewrite, solve, summarise, correct or add words. "
    "Leave out page furniture: page numbers, paper titles, 'ASSESSOR'S USE ONLY', 'If you need to redraw...' notes, "
    "lines of dots, and text from neighbouring parts.\n"
    "2. 'question' is the part's own instruction (what to calculate, describe, explain) with any data given inside it.\n"
    "3. 'context' is only the set-up this part needs to be answerable on its own: the question's introduction when the "
    "part relies on it, and the lead-in shared by sub-parts such as (i) and (ii). If a part also needs a value, "
    "diagram or result from an earlier part, include that earlier part's wording in 'context' starting 'Earlier part (b): '. "
    "Use an empty string when the part is fully self-contained. Do not include more than the part needs.\n"
    "4. 'schedule' is the section of schedule_text that applies to this part, copied exactly; use an empty string if "
    "you cannot isolate it.\n"
    "5. 'marks' is the part's marks if the paper shows them, else null.\n"
    "6. 'needs_figure' is true when the part refers to a diagram, graph, table, circuit, photograph or labels that exist "
    "only in a figure, and true when unsure and has_figures is true; otherwise false.\n"
    "7. Keep one unit per part in paper order. If the question is a single indivisible task, return one unit."
)


def _words(text):
    return re.findall(r"[a-z0-9]{2,}", str(text).lower())


def grounded(text, source):
    """Share of the words in `text` that occur in `source`. Empty text counts as fully grounded."""
    words = _words(text)
    if not words:
        return 1.0
    have = set(_words(source))
    return sum(1 for w in words if w in have) / len(words)


FOOTER = re.compile(r"(?im)^[ \t]*\d{1,3}[ \t]*\n[ \t]*[A-Za-z ]{3,30}\d{5}, ?\d{4}[ \t]*$|^[ \t]*[A-Za-z ]{3,30}\d{5}, ?\d{4}[ \t]*$|^[ \t]*ASSESSOR.S[ \t]*$|^[ \t]*USE ONLY[ \t]*$")
LABEL_LINE = re.compile(r"(?m)^[ \t]*\([a-zA-Z]{1,4}\)[ \t]*$")


def tidy(text):
    """Remove page furniture and bare '(a)' marker lines the model left in, and collapse the blank lines that leaves."""
    text = FOOTER.sub("", text)
    text = LABEL_LINE.sub("", text)
    text = re.sub(r"(?m)^[ \t]*\([a-zA-Z]{1,4}\)[ \t]+(?=\S)", "", text)       # '(b) Calculate...' on one line
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean_units(raw, question_text, schedule_text, parent_marks_by_label=None):
    """Validate the model's reply. Returns a list of units or raises ValueError with the reason."""
    units = raw.get("units") if isinstance(raw, dict) else None
    if not isinstance(units, list) or not units:
        raise ValueError("no units")
    if len(units) > MAX_UNITS:
        raise ValueError("too many units")
    seen, result = set(), []
    for item in units:
        if not isinstance(item, dict):
            raise ValueError("unit is not an object")
        label = str(item.get("label", "")).strip()
        if label.startswith("(") and label.endswith(")") and "(" not in label[1:]:
            label = label[1:-1].strip()
        context = str(item.get("context") or "").strip()
        question = str(item.get("question") or "").strip()
        schedule = str(item.get("schedule") or "").strip()
        if not label or len(label) > 12 or label.lower() in seen:
            raise ValueError("bad or repeated label")
        if len(question) < 3 or len(question) > 4000 or len(context) > 6000:
            raise ValueError("unit text size")
        seen.add(label.lower())
        # The words the paper really contains: 'Earlier part (b):' is the only wording we allow the model to add.
        body = re.sub(r"(?i)earlier part \(?[a-z0-9()]+\)?:", " ", f"{context} {question}")
        if grounded(body, question_text) < MIN_GROUNDED_QUESTION:
            raise ValueError(f"part {label} has wording that is not on the paper")
        if schedule and (len(schedule) > 8000 or grounded(schedule, schedule_text) < MIN_GROUNDED_SCHEDULE):
            schedule = ""       # not trustworthy: fall back to the whole question's schedule
        marks = item.get("marks")
        marks = marks if isinstance(marks, int) and not isinstance(marks, bool) and 0 <= marks <= 50 else None
        if marks is None and parent_marks_by_label:
            marks = parent_marks_by_label.get(label.lower())
        context, question = tidy(context), tidy(question)
        if len(question) < 3:
            raise ValueError("unit has no question text")
        result.append({"label": label, "context": context, "question": question, "schedule": schedule,
                       "marks": marks or 0, "needs_figure": item.get("needs_figure") is True})
    return result


def parse_reply(reply):
    """JSON from the model, tolerating a code fence and the raw tabs and line breaks it copies out of the paper."""
    text = reply.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    from mathtext import latex_json      # imported here: mathtext imports this module
    return json.loads(latex_json(text), strict=False)


def split_one(model_reply, number, parts, question_text, schedule_text, has_figures):
    messages = [{"role": "system", "content": SPLIT_SYSTEM},
                {"role": "user", "content": json.dumps({"question_number": number, "parts": parts, "question_text": question_text,
                                                         "schedule_text": schedule_text, "has_figures": has_figures})}]
    raw = parse_reply(model_reply("education", messages, task="rapid-split"))
    labels = {str(p.get("label", "")).lower(): p.get("marks") for p in parts if isinstance(p, dict)}
    return clean_units(raw, question_text, schedule_text, {k: v for k, v in labels.items() if isinstance(v, int) and v > 0})


def store_units(db, parent_id, units):
    """Write the parts and mark the parent done. Idempotent: parts already stored are kept."""
    parent = db.execute("""SELECT topic_id, standard_number, year, question_number, paper_resource_id, paper_page,
            schedule_resource_id, schedule_page, schedule_text, figure_pages FROM exam_questions
        WHERE id = %s AND parent_id IS NULL FOR UPDATE""", (parent_id,)).fetchone()
    if not parent:
        return 0
    if len(units) < 2:
        db.execute("UPDATE exam_questions SET split_state = 'single' WHERE id = %s", (parent_id,))
        return 0
    for unit in units:
        text = (unit["context"] + "\n\n" + unit["question"]).strip() if unit["context"] else unit["question"]
        db.execute("""INSERT INTO exam_questions
            (topic_id, standard_number, year, question_number, paper_resource_id, paper_page, schedule_resource_id, schedule_page,
             marks, parts, question_text, schedule_text, figure_pages, source, verified_at, parent_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '[]'::jsonb, %s, %s, %s::jsonb, 'part', NULL, %s)
            ON CONFLICT (parent_id, question_number) WHERE parent_id IS NOT NULL DO NOTHING""",
                   (parent[0], parent[1], parent[2], f"{parent[3]} {unit['label']}", parent[4], parent[5], parent[6], parent[7],
                    unit["marks"], text, unit["schedule"] or parent[8], json.dumps(parent[9] if unit["needs_figure"] else []), parent_id))
    db.execute("UPDATE exam_questions SET split_state = 'done' WHERE id = %s", (parent_id,))
    return len(units)


def pending(db, topic_id=None, limit=500):
    return db.execute("""SELECT id, question_number, parts, question_text, schedule_text, figure_pages FROM exam_questions
        WHERE parent_id IS NULL AND source <> 'ai' AND split_state = '' AND length(trim(question_text)) > 0
          AND (%s::bigint IS NULL OR topic_id = %s) ORDER BY id LIMIT %s""", (topic_id, topic_id, limit)).fetchall()


def _units_for(model_reply, row):
    """(units, error) for one pending row: units is None when two tries both failed, [] when there is nothing to split.
    The error is a ValueError when the model's split was unusable, anything else when the gateway itself failed."""
    question_id, number, parts, text, schedule, figures = row
    parts = parts if isinstance(parts, list) else []
    if len(parts) < 2 and not re.search(r"(?m)^\(?[a-d]\)?\s*$", text):
        return [], None
    error = None
    for _ in range(2):
        try:
            return split_one(model_reply, number, parts, text, schedule, bool(figures)), None
        except Exception as caught:     # network, bad JSON, or a split that failed the wording check
            error = caught
    return None, error


_running = set()
_running_lock = threading.Lock()


def kick(connect, model_reply, topic_id=None):
    """Split a topic's new paper questions in the background, once at a time per account and topic. Returns whether it started."""
    key = (userspace.current_user.get(), topic_id or 0)
    with _running_lock:
        if key in _running or (key[0], 0) in _running:
            return False
        _running.add(key)

    def run():
        try:
            log.info("Rapid split finished: %s", split_pending(connect, model_reply, topic_id))
        except Exception as error:      # noqa: BLE001 - background work must never take the caller down
            log.warning("Rapid split failed: %s", getattr(error, "detail", error))
        finally:
            with _running_lock:
                _running.discard(key)
    userspace.spawn(run)
    return True


def split_pending(connect, model_reply, topic_id=None, limit=500, workers=4):
    """Split every unsplit paper question (of one topic, or all). A question that fails twice is marked 'failed' and
    served whole instead; it never blocks the others. The model calls run in parallel; the database writes do not."""
    from concurrent.futures import ThreadPoolExecutor
    with connect() as db:
        rows = pending(db, topic_id, limit)
    done = failed = single = retry = 0
    reasons = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="split") as pool:
        # each call keeps the caller's account, so the model-usage log lands in the right schema
        contexts = [contextvars.copy_context() for _ in rows]
        for row, (units, error) in zip(rows, pool.map(lambda pair: pair[1].run(_units_for, model_reply, pair[0]), zip(rows, contexts))):
            question_id = row[0]
            with connect() as db:
                if units is None and not isinstance(error, ValueError):
                    retry += 1      # the gateway failed, not the split: leave it waiting so a later run tries again
                    reasons.append(f"{question_id}: {getattr(error, 'detail', error)}")
                elif units is None:
                    db.execute("UPDATE exam_questions SET split_state = 'failed' WHERE id = %s AND split_state = ''", (question_id,))
                    failed += 1
                    reasons.append(f"{question_id}: {error}")
                    log.warning("Splitting question %s failed: %s", question_id, error)
                elif len(units) < 2:
                    db.execute("UPDATE exam_questions SET split_state = 'single' WHERE id = %s AND split_state = ''", (question_id,))
                    single += 1
                else:
                    store_units(db, question_id, units)
                    done += 1
    return {"split": done, "single": single, "failed": failed, "retry_later": retry, "checked": len(rows), "reasons": reasons[:10]}
