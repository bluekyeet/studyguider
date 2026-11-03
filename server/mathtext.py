"""Maths for paper questions that the PDF text layer lost.

The text extracted from a past paper has no subscripts, superscripts or equations: "3x4 + px3", "z3 + 8m27i = 0",
and equations such as "( ) kx x k 2 = -" that are missing altogether. A vision model reads the question's page image
and rewrites the same wording with the maths in LaTeX. The original text is never replaced; the LaTeX version is stored
beside it in exam_questions.math_display and shown instead where it exists. A rewrite is used only if its ordinary words
match the original's (nothing added, dropped or solved), so a bad reply leaves the learner with the original text.
"""
import contextvars
import io
import json
import logging
import re
import threading
import time

import userspace
from splitting import _words, grounded

log = logging.getLogger("uvicorn.error")

MATHS_SYSTEM = (
    "You restore mathematics in text taken from an NCEA exam paper. The text came from the PDF's text layer, which loses "
    "subscripts, superscripts, fractions, roots, Greek letters, moduli and whole equations. The page image shows the real "
    "question. Reply with one block per key you were given, in exactly this form and nothing else:\n"
    "=== key ===\n"
    "the rewritten text\n"
    "Rules:\n"
    "1. Copy every ordinary word exactly. Never rewrite, solve, simplify, correct, summarise or add words, answers or hints.\n"
    "2. Write every mathematical expression, equation, chemical formula, number with units and exponent in LaTeX between "
    "single dollar signs, for example $3x^4 + px^3 - 4x + 5$, $\\text{CH}_3\\text{CH}_2\\text{OH}$, $-1370\\text{ kJ mol}^{-1}$. "
    "Use the page image to recover what the text lost, such as an equation shown only as symbols or spaces.\n"
    "3. Do not put ordinary sentences inside dollar signs. Use \\text{...} only for units and chemical symbols.\n"
    "4. Keep the original line breaks. When equations are stacked on the page, for example a pair of simultaneous equations, "
    "put each equation on its own line, each in its own dollar signs.\n"
    "5. If you cannot read an expression on the page, leave that stretch of text as it was; do not guess."
)

BLOCK = re.compile(r"(?ms)^=== (\w+) ===[ \t]*\n(.*?)(?=^=== \w+ ===|\Z)")
MAX_PAGES = 3
MAX_UNITS = 25


def stripped(text):
    return re.sub(r"\$[^$]*\$", " ", text)


def acceptable(new, old):
    """A LaTeX rewrite must keep the original's ordinary words and add none of its own."""
    if not isinstance(new, str) or not new.strip() or new.count("$") % 2:
        return False
    plain_new = [w for w in _words(stripped(new)) if w.isalpha() and len(w) > 2]
    plain_old = [w for w in _words(old) if w.isalpha() and len(w) > 3]
    in_old = set(_words(old))
    in_new = set(_words(new))
    added = sum(1 for w in plain_new if w not in in_old)
    kept = sum(1 for w in plain_old if w in in_new)
    # Every number the text layer had must survive: a model that "reads" a different exponent or coefficient is caught here
    # (the text layer says 8m27i, the model wrote 8m^3 i). Such a unit stays as the original text.
    numbers_kept = set(re.findall(r"\d+", old)) <= set(re.findall(r"\d+", new))
    return numbers_kept and (not plain_new or added / len(plain_new) <= 0.1) and (not plain_old or kept / len(plain_old) >= 0.85)


def units_of(question_text, parts):
    units = {"q": question_text or ""}
    for index, part in enumerate(parts if isinstance(parts, list) else []):
        if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip():
            units[f"p{index}"] = part["text"]
    return {key: text for key, text in units.items() if text.strip()}


def render_pages(resource_id, pages):
    """The question's pages stacked into one PNG for the vision model."""
    import pymupdf
    from PIL import Image
    images = []
    with pymupdf.open(userspace.upload_root() / str(resource_id)) as document:
        for number in pages[:MAX_PAGES]:
            if 1 <= number <= len(document):
                images.append(Image.open(io.BytesIO(document[number - 1].get_pixmap(dpi=170).tobytes("png"))).convert("RGB"))
    if not images:
        raise ValueError("no pages to read")
    width = max(i.width for i in images)
    sheet = Image.new("RGB", (width, sum(i.height for i in images)), "white")
    y = 0
    for image in images:
        sheet.paste(image, (0, y))
        y += image.height
    out = io.BytesIO()
    sheet.save(out, format="PNG", optimize=True)
    return out.getvalue()


def restore_one(vision_reply, row):
    """The accepted LaTeX rewrites for one question row as {"q": ..., "p": [...]}, or raises."""
    question_id, resource_id, page, figures, question_text, parts = row
    pages = [p for p in (figures if isinstance(figures, list) else []) if isinstance(p, int)][:MAX_PAGES] or ([page] if page else [])
    units = units_of(question_text, parts)
    if not units or not resource_id or not pages or len(units) > MAX_UNITS:
        return None
    image = render_pages(resource_id, pages)
    prompt = MATHS_SYSTEM + "\n\nTEXTS:\n" + "\n".join(f"=== {key} ===\n{text}" for key, text in units.items())
    reply = vision_reply("education", prompt, image, task="exam-maths")
    texts = {m.group(1): m.group(2).strip() for m in BLOCK.finditer(reply if isinstance(reply, str) else "")}
    if not texts:
        raise ValueError("the reply was not in the requested form")
    accepted = {key: texts[key] for key in units if acceptable(texts.get(key), units[key])}
    if not accepted:
        raise ValueError("no rewritten text kept the original wording")
    count = len(parts) if isinstance(parts, list) else 0
    return {"q": accepted.get("q"), "p": [accepted.get(f"p{i}") for i in range(count)]}


def pending(db, topic_id=None, limit=300, ids=None):
    return db.execute("""SELECT id, paper_resource_id, paper_page, figure_pages, question_text, parts FROM exam_questions
        WHERE source <> 'ai' AND math_state = '' AND paper_resource_id IS NOT NULL AND length(trim(question_text)) > 0
          AND (%s::bigint IS NULL OR topic_id = %s) AND (%s::bigint[] IS NULL OR id = ANY(%s)) ORDER BY id LIMIT %s""",
                      (topic_id, topic_id, ids, ids, limit)).fetchall()


_running = set()
_lock = threading.Lock()


def process(connect, vision_reply, topic_id=None, workers=2, ids=None):
    from concurrent.futures import ThreadPoolExecutor
    with connect() as db:
        rows = pending(db, topic_id, ids=ids)
    counts = {"done": 0, "failed": 0, "retry": 0}

    def attempt(row):
        error = None
        for tries in range(3):
            try:
                return restore_one(vision_reply, row), None
            except Exception as caught:     # noqa: BLE001 - network, unreadable PDF, or a rewrite that failed the wording check
                error = caught
                if isinstance(caught, ValueError) and tries:
                    break                   # the model answered twice and neither rewrite was usable
                time.sleep(4 * (tries + 1))   # the gateway answers 503 when it is busy; wait and try again
        return None, error

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="maths") as pool:
        contexts = [contextvars.copy_context() for _ in rows]
        for row, (display, error) in zip(rows, pool.map(lambda pair: pair[1].run(attempt, pair[0]), zip(rows, contexts))):
            with connect() as db:
                if display is not None:
                    db.execute("UPDATE exam_questions SET math_display = %s::jsonb, math_state = 'done' WHERE id = %s", (json.dumps(display), row[0]))
                    counts["done"] += 1
                elif isinstance(error, ValueError):
                    db.execute("UPDATE exam_questions SET math_state = 'failed' WHERE id = %s", (row[0],))
                    counts["failed"] += 1
                elif error is None:
                    db.execute("UPDATE exam_questions SET math_state = 'single' WHERE id = %s", (row[0],))   # nothing to read
                else:
                    counts["retry"] += 1    # the gateway failed: leave it waiting for a later run
    return counts


def kick(connect, vision_reply, topic_id=None, ids=None):
    """Run process() in the background, one run at a time per account. Returns whether it started."""
    key = userspace.current_user.get()
    with _lock:
        if key in _running:
            return False
        _running.add(key)

    def run():
        try:
            log.info("Maths restore finished: %s", process(connect, vision_reply, topic_id, ids=ids))
        except Exception as error:      # noqa: BLE001 - background work must never take the caller down
            log.warning("Maths restore failed: %s", getattr(error, "detail", error))
        finally:
            with _lock:
                _running.discard(key)
    userspace.spawn(run)
    return True


def overlay(db, items, id_key="question_id"):
    """Swap in the LaTeX wording on learner-facing question dicts that have one. Original text stays in the database."""
    ids = [item[id_key] for item in items if item.get(id_key)]
    if not ids:
        return items
    found = {r[0]: r[1] for r in db.execute("SELECT id, math_display FROM exam_questions WHERE id = ANY(%s) AND math_state = 'done'", (ids,)).fetchall()}
    for item in items:
        display = found.get(item.get(id_key))
        if not display:
            continue
        item["maths_restored"] = True
        if isinstance(display.get("q"), str) and display["q"].strip():
            item["question_text"] = display["q"]
        parts = item.get("parts")
        if isinstance(parts, list):
            replaced = []
            for index, part in enumerate(parts):
                new = (display.get("p") or [None] * len(parts))[index] if index < len(display.get("p") or []) else None
                replaced.append({**part, "text": new} if isinstance(part, dict) and isinstance(new, str) and new.strip() else part)
            item["parts"] = replaced
    return items


def display_label(label):
    """'b(i)' as '(b)(i)', the way the paper prints it."""
    return "(" + label.replace("(", ")(") + ("" if label.endswith(")") else ")")


CONTEXT_ONLY = re.compile(r"^\s*question\s+\w+\s*$", re.I)


def review_parts(db, question_id):
    """[(label, text)] for a question with two or more labelled parts, each with its restored maths, so a review question can
    be one part. Shared opening text, and a sub-part's parent wording, are added to each; a bare "QUESTION ONE" heading is not. [] when it has no parts."""
    row = db.execute("SELECT parts, math_display, math_state FROM exam_questions WHERE id = %s", (question_id,)).fetchone()
    if not row or not isinstance(row[0], list):
        return []
    parts, display, state = row
    shown = display.get("p") if state == "done" and isinstance(display, dict) else None
    shown = shown or []
    context, labelled = "", []
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            continue
        new = shown[index] if index < len(shown) else None
        text = (new if isinstance(new, str) and new.strip() else part.get("text") or "").strip()
        label = part.get("label")
        if not text or not isinstance(label, str) or not label:
            continue
        if label == "context":
            context = "" if CONTEXT_ONLY.match(text) else text
        else:
            labelled.append((label, text))
    texts = dict(labelled)
    children = {label.split("(")[0] for label, _ in labelled if "(" in label}
    asked = []
    for label, text in labelled:
        if label in children:
            continue    # a part that only introduces its sub-parts is not asked on its own
        parent = texts.get(label.split("(")[0]) if "(" in label else None
        asked.append((label, "\n\n".join(piece for piece in (context, parent, text) if piece)))
    return asked if len(labelled) > 1 else []


def restored_text(db, question_id, original):
    """The question as the learner saw it with its equations restored, for copies stored elsewhere (review questions).
    Falls back to the original text when nothing was restored."""
    row = db.execute("SELECT math_display, parts FROM exam_questions WHERE id = %s AND math_state = 'done'", (question_id,)).fetchone()
    if not row or not row[0]:
        return original
    display, parts = row
    if isinstance(display.get("q"), str) and display["q"].strip():
        return display["q"]
    shown = display.get("p") or []
    pieces, changed = [], False
    for index, part in enumerate(parts if isinstance(parts, list) else []):
        new = shown[index] if index < len(shown) else None
        changed = changed or isinstance(new, str)
        text = new if isinstance(new, str) else (part.get("text") if isinstance(part, dict) else "")
        if text and text.strip():
            pieces.append(text.strip())
    return "\n\n".join(pieces) if changed and pieces else original
