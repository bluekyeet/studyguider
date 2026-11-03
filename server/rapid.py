"""Rapid exam questions: one-way, blind sessions with background marking and an exam revision list.

A session is an ordinary `exams` row with kind 'rapid' that grows as the learner presses Next, so
answers, scans, marking and the wrong-answer review hand-off all reuse the existing exam code. While a
session is open the server refuses every route that would reveal marks, schedules or feedback for it
(see rapid_state.py), so no client can leak results early. Answers lock when the learner moves on.
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import rapid_state
import userspace
import splitting
from exams import PRACTICE_SYSTEM, parse_practice_paper

log = logging.getLogger("uvicorn.error")

BUFFER_TARGET = 6       # AI questions kept ready ahead of the learner
REFILL_BELOW = 4        # start refilling when fewer than this are ready
BATCH = 3               # questions per generation call
MARK_RETRIES = 3

MARKERS = ThreadPoolExecutor(max_workers=3, thread_name_prefix="rapid-mark")
GENERATORS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="rapid-gen")
SPLITTERS = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rapid-split")
_splitting = set()      # topic ids (0 = all) with a split run going
_lock = threading.Lock()
_inflight = set()       # (exam_id, question_id) being marked
_attempts = {}          # (exam_id, question_id) -> failed marking attempts
_generating = set()     # exam ids with a generator running

OUTCOMES = ("not_achieved", "achieved", "merit", "excellence")
REVIEW_SYSTEM = ("You are an independent NCEA examiner checking an AI-written practice question and its rubric. "
                 "Return only a JSON object {\"pass\": boolean, \"issues\": [strings]}. Fail it if the question is ambiguous, "
                 "lacks a given it needs (values, units, context), cannot be answered from what is stated, tests content "
                 "outside the topic, or if the worked answer in the rubric is scientifically or numerically wrong. "
                 "Use New Zealand English.")


class RapidStart(BaseModel):
    topic_id: int = Field(gt=0)
    source: Literal["past", "ai", "mix", "revision"] = "mix"
    count: int | None = Field(default=None, ge=1, le=200)   # None means unlimited


class RapidMove(BaseModel):
    question_id: int | None = None
    answer: str = Field(default="", max_length=100000)
    scan_revision: int = Field(default=0, ge=0)
    seconds: int | None = Field(default=None, ge=0, le=86400)
    skip: bool = False


def create_rapid_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS rapid_sessions (
        exam_id bigint PRIMARY KEY REFERENCES exams(id) ON DELETE CASCADE,
        topic_id bigint NOT NULL REFERENCES topics(id),
        source text NOT NULL CHECK (source IN ('past', 'ai', 'mix', 'revision')),
        target_count integer CHECK (target_count IS NULL OR target_count BETWEEN 1 AND 200),
        started_at timestamptz NOT NULL DEFAULT now(),
        ended_at timestamptz)""")
    db.execute("""CREATE TABLE IF NOT EXISTS rapid_items (
        exam_id bigint NOT NULL, question_id bigint NOT NULL,
        presented_at timestamptz NOT NULL DEFAULT now(), answered_at timestamptz,
        skipped boolean NOT NULL DEFAULT false, seconds_spent integer,
        PRIMARY KEY (exam_id, question_id),
        FOREIGN KEY (exam_id, question_id) REFERENCES exam_items(exam_id, question_id) ON DELETE CASCADE)""")
    db.execute("""CREATE TABLE IF NOT EXISTS rapid_queue (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        exam_id bigint NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
        question_id bigint NOT NULL REFERENCES exam_questions(id) ON DELETE CASCADE,
        served boolean NOT NULL DEFAULT false)""")
    db.execute("CREATE INDEX IF NOT EXISTS rapid_queue_open_idx ON rapid_queue (exam_id) WHERE NOT served")
    db.execute("""CREATE TABLE IF NOT EXISTS rapid_pending_reviews (
        exam_id bigint NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
        question_id bigint NOT NULL,
        review jsonb NOT NULL,
        PRIMARY KEY (exam_id, question_id))""")
    db.execute("""CREATE TABLE IF NOT EXISTS exam_revision (
        question_id bigint PRIMARY KEY REFERENCES exam_questions(id) ON DELETE CASCADE,
        topic_id bigint NOT NULL REFERENCES topics(id),
        first_missed_at timestamptz NOT NULL DEFAULT now(),
        last_attempt_at timestamptz NOT NULL DEFAULT now(),
        attempts integer NOT NULL DEFAULT 1,
        last_exam_id bigint,
        resolved_at timestamptz)""")


def _text_sql(alias="q"):
    return f"COALESCE(NULLIF(trim({alias}.question_text), ''), page.content, '')"


def _payload(db, exam_id, question_id):
    """What the learner may see while answering: no schedule, rubric or marks."""
    row = db.execute(f"""SELECT q.id, i.position, q.source, q.standard_number, q.year, q.parts, {_text_sql()},
            q.figure_pages, q.paper_resource_id, q.paper_page, q.parent_id, q.question_number
        FROM exam_items i JOIN exam_questions q ON q.id = i.question_id
        LEFT JOIN resource_pages page ON page.resource_id = q.paper_resource_id AND page.page = q.paper_page
        WHERE i.exam_id = %s AND i.question_id = %s""", (exam_id, question_id)).fetchone()
    if not row:
        raise HTTPException(404, "Question not found")
    ai = row[2] == "ai"
    return {"question_id": row[0], "position": row[1], "source": "ai" if ai else "past",
            "standard_number": row[3], "year": None if ai else row[4], "parts": row[5],
            "question_text": row[6][:30000], "figure_pages": row[7],
            "paper_resource_id": None if ai or not row[8] else str(row[8]), "paper_page": None if ai else row[9],
            "label": row[11] if row[10] else None}


def _current(db, exam_id):
    return db.execute("""SELECT question_id, presented_at FROM rapid_items
        WHERE exam_id = %s AND answered_at IS NULL ORDER BY presented_at DESC, question_id DESC LIMIT 1""", (exam_id,)).fetchone()


def _bank_pick(db, exam_id, topic_id):
    # One part at a time: lettered parts of a split question, or a question that has no parts. A question that is still
    # waiting to be split is skipped, and so is the whole of one that was split (its parts stand in for it).
    # Least recently seen first; the order inside that is stable for a session but differs between sessions.
    row = db.execute("""SELECT q.id FROM exam_questions q WHERE q.topic_id = %s AND q.source <> 'ai'
        AND (q.parent_id IS NOT NULL OR q.split_state IN ('single', 'failed'))
        AND NOT EXISTS (SELECT 1 FROM exam_items i WHERE i.exam_id = %s AND i.question_id = q.id)
        ORDER BY COALESCE((SELECT max(i.exam_id) FROM exam_items i WHERE i.question_id = q.id), 0), md5(q.id::text || %s::text)
        LIMIT 1""", (topic_id, exam_id, str(exam_id))).fetchone()
    return row[0] if row else None


def _ai_pick(db, exam_id):
    row = db.execute("""SELECT id, question_id FROM rapid_queue WHERE exam_id = %s AND NOT served
        ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED""", (exam_id,)).fetchone()
    if not row:
        return None
    db.execute("UPDATE rapid_queue SET served = true WHERE id = %s", (row[0],))
    return row[1]


def _revision_pick(db, exam_id, topic_id):
    row = db.execute("""SELECT r.question_id FROM exam_revision r WHERE r.topic_id = %s AND r.resolved_at IS NULL
        AND NOT EXISTS (SELECT 1 FROM exam_items i WHERE i.exam_id = %s AND i.question_id = r.question_id)
        ORDER BY r.last_attempt_at, r.question_id LIMIT 1""", (topic_id, exam_id)).fetchone()
    return row[0] if row else None


def order_of_sources(source, served):
    """Which pools to try, in order. A mix alternates real and AI questions and falls back to whichever has any."""
    if source == "past":
        return ["bank"]
    if source == "ai":
        return ["ai", "bank"]          # real questions cover for AI while the first batch is being written
    if source == "revision":
        return ["revision"]
    return ["bank", "ai"] if served % 2 == 0 else ["ai", "bank"]


def _advance(db, exam_id, topic_id, source, target):
    """Present the next question. Returns its id, or the strings 'finished' or 'exhausted'."""
    served = db.execute("SELECT count(*) FROM rapid_items WHERE exam_id = %s", (exam_id,)).fetchone()[0]
    if target is not None and served >= target:
        return "finished"
    for pool in order_of_sources(source, served):
        question_id = (_bank_pick(db, exam_id, topic_id) if pool == "bank" else _ai_pick(db, exam_id) if pool == "ai"
                       else _revision_pick(db, exam_id, topic_id))
        if question_id:
            position = db.execute("SELECT COALESCE(max(position), 0) + 1 FROM exam_items WHERE exam_id = %s", (exam_id,)).fetchone()[0]
            db.execute("INSERT INTO exam_items (exam_id, question_id, position, answer) VALUES (%s, %s, %s, '')", (exam_id, question_id, position))
            db.execute("INSERT INTO rapid_items (exam_id, question_id) VALUES (%s, %s)", (exam_id, question_id))
            return question_id
    return "exhausted"


def _upsert_revision(db, exam_id, question_id, topic_id):
    db.execute("""INSERT INTO exam_revision (question_id, topic_id, last_exam_id) VALUES (%s, %s, %s)
        ON CONFLICT (question_id) DO UPDATE SET
            attempts = CASE WHEN exam_revision.last_exam_id = EXCLUDED.last_exam_id THEN exam_revision.attempts ELSE exam_revision.attempts + 1 END,
            last_attempt_at = now(), last_exam_id = EXCLUDED.last_exam_id, resolved_at = NULL""", (question_id, topic_id, exam_id))


def _queue_skipped_review(db, exam_id, question_id):
    """A skipped question is a miss like any other: queue the same grounded review question a wrong answer would."""
    row = db.execute(f"""SELECT q.topic_id, q.standard_number, q.question_number, q.schedule_text, q.schedule_resource_id,
            q.schedule_page, q.paper_resource_id, {_text_sql()}
        FROM exam_questions q LEFT JOIN resource_pages page ON page.resource_id = q.paper_resource_id AND page.page = q.paper_page
        WHERE q.id = %s""", (question_id,)).fetchone()
    if not row or not row[3].strip() or not row[7].strip() or len(row[7]) > 20000 or len(row[3]) > 20000:
        return
    source = [{"resource_id": str(row[4]) if row[4] else None, "page": row[5], "content": row[3], "exam_id": exam_id,
               "question_id": question_id, "rubric_type": "official schedule" if row[6] else "unofficial AI practice rubric"}]
    db.execute("""INSERT INTO review_questions (topic_id, question, due_date, expected_answer, source, standard_number, concept, exam_origin)
        VALUES (%s, %s, (CURRENT_TIMESTAMP AT TIME ZONE 'Pacific/Auckland')::date, %s, %s::jsonb, %s, %s, %s)
        ON CONFLICT (exam_origin) DO NOTHING""",
               (row[0], row[7], row[3], json.dumps(source), row[1], f"Exam question {row[2]}", f"{exam_id}:{question_id}"))


def rapid_router(connect, authorised, model_reply=None, search_resources=None, mark_answer=None):
    router = APIRouter(dependencies=[Depends(authorised)])

    # ---- marking in the background -------------------------------------------------------------
    def apply_revision(db, exam_id, only=None):
        """Record this session's misses in Exam revision and clear ones now answered. Idempotent; only after the session ends."""
        marks = db.execute("""SELECT DISTINCT ON (m.question_id) m.question_id, m.result->>'outcome', q.topic_id FROM markings m
            JOIN exam_questions q ON q.id = m.question_id WHERE m.exam_id = %s AND m.kind = 'first' AND (%s::bigint IS NULL OR m.question_id = %s)
            ORDER BY m.question_id, m.id DESC""", (exam_id, only, only)).fetchall()
        for question_id, outcome, topic_id in marks:
            if outcome == "not_achieved":
                _upsert_revision(db, exam_id, question_id, topic_id)
            elif outcome in ("achieved", "merit", "excellence"):
                db.execute("UPDATE exam_revision SET resolved_at = now(), last_attempt_at = now() WHERE question_id = %s AND resolved_at IS NULL", (question_id,))

    def flush_pending_reviews(db, exam_id):
        for (review,) in db.execute("SELECT review FROM rapid_pending_reviews WHERE exam_id = %s", (exam_id,)).fetchall():
            db.execute("""INSERT INTO review_questions (topic_id, question, due_date, expected_answer, source, standard_number, concept, exam_origin)
                VALUES (%s, %s, (CURRENT_TIMESTAMP AT TIME ZONE 'Pacific/Auckland')::date, %s, %s::jsonb, %s, %s, %s)
                ON CONFLICT (exam_origin) DO NOTHING""", review)
        db.execute("DELETE FROM rapid_pending_reviews WHERE exam_id = %s", (exam_id,))

    def after_mark(exam_id, question_id):
        with connect() as db:
            if rapid_state.is_open(db, exam_id):
                return          # nothing is recorded, or shown, until the session ends
            apply_revision(db, exam_id, question_id)

    def mark(key):
        exam_id, question_id = key
        rapid_state.bypass.on = True          # this thread is allowed to read results; requests are not
        try:
            mark_answer(exam_id, question_id)
            after_mark(exam_id, question_id)
        except Exception as error:    # includes HTTPException from the marking route
            with _lock:
                _attempts[key] = _attempts.get(key, 0) + 1
            log.warning("Rapid marking failed for %s (attempt %s): %s", key, _attempts[key], getattr(error, "detail", error))
        finally:
            rapid_state.bypass.on = False
            with _lock:
                _inflight.discard(key)

    def queue_mark(exam_id, question_id):
        if mark_answer is None:
            return
        key = (exam_id, question_id)
        with _lock:
            if key in _inflight or _attempts.get(key, 0) >= MARK_RETRIES:
                return
            _inflight.add(key)
        userspace.submit(MARKERS, mark, key)

    # ---- AI questions prepared ahead ----------------------------------------------------------
    def generate_batch(exam_id, topic_id, topic_name, want):
        with connect() as db:
            standard = db.execute("SELECT standard_number FROM topic_standards WHERE topic_id = %s ORDER BY standard_number LIMIT 1", (topic_id,)).fetchone()
            recent = [r[0] for r in db.execute("SELECT left(question_text, 100) FROM exam_questions WHERE topic_id = %s AND source = 'ai' ORDER BY id DESC LIMIT 12", (topic_id,)).fetchall()]
        if not standard:
            return
        sources = search_resources(topic_id, topic_name)[:5]
        if not sources:
            return
        messages = [{"role": "system", "content": PRACTICE_SYSTEM},
                    {"role": "user", "content": json.dumps({"topic": topic_name, "count": want, "sources": sources,
                        "variety": "Cover different sub-topics and question styles. Do not repeat or closely resemble any question in avoid.",
                        "avoid": recent}, default=str)}]
        paper = parse_practice_paper(model_reply("education", messages, task="rapid-generate"), want)
        for item in paper:
            verdict = model_reply("education-reviewer", [
                {"role": "system", "content": REVIEW_SYSTEM},
                {"role": "user", "content": json.dumps({"topic": topic_name, "question": item["question"], "rubric": item["rubric"], "marks": item["marks"]})}],
                task="rapid-review")
            try:
                from reviews import _clean_json
                verdict = _clean_json(verdict)
            except Exception:
                continue
            if not isinstance(verdict, dict) or verdict.get("pass") is not True:
                continue    # a failed check drops the question; it is never served
            with connect() as db:
                if db.execute("SELECT 1 FROM rapid_sessions WHERE exam_id = %s AND ended_at IS NULL", (exam_id,)).fetchone() is None:
                    return
                qid = db.execute("""INSERT INTO exam_questions (topic_id, standard_number, year, question_number, paper_page, schedule_page,
                        marks, question_text, schedule_text, source)
                    VALUES (%s, %s, EXTRACT(YEAR FROM now()), 'AI', 1, 1, %s, %s, %s, 'ai') RETURNING id""",
                                 (topic_id, standard[0], item["marks"], item["question"], item["rubric"])).fetchone()[0]
                db.execute("INSERT INTO rapid_queue (exam_id, question_id) VALUES (%s, %s)", (exam_id, qid))

    def fill_buffer(exam_id):
        try:
            for _ in range(4):
                with connect() as db:
                    sess = db.execute("SELECT s.topic_id, s.source, s.ended_at, t.name FROM rapid_sessions s JOIN topics t ON t.id = s.topic_id WHERE s.exam_id = %s", (exam_id,)).fetchone()
                    ready = db.execute("SELECT count(*) FROM rapid_queue WHERE exam_id = %s AND NOT served", (exam_id,)).fetchone()[0]
                if not sess or sess[2] or sess[1] not in ("ai", "mix") or ready >= BUFFER_TARGET:
                    return
                generate_batch(exam_id, sess[0], sess[3], min(BATCH, BUFFER_TARGET - ready))
        except Exception as error:
            log.warning("Rapid question generation failed for session %s: %s", exam_id, getattr(error, "detail", error))
        finally:
            with _lock:
                _generating.discard(exam_id)

    def ensure_buffer(exam_id):
        if model_reply is None or search_resources is None:
            return
        with connect() as db:
            sess = db.execute("SELECT source, ended_at FROM rapid_sessions WHERE exam_id = %s", (exam_id,)).fetchone()
            ready = db.execute("SELECT count(*) FROM rapid_queue WHERE exam_id = %s AND NOT served", (exam_id,)).fetchone()[0]
        if not sess or sess[1] or sess[0] not in ("ai", "mix") or ready >= REFILL_BELOW:
            return
        with _lock:
            if exam_id in _generating:
                return
            _generating.add(exam_id)
        userspace.submit(GENERATORS, fill_buffer, exam_id)

    # ---- locking an answer ---------------------------------------------------------------------
    def lock_current(db, exam_id, body, final=False):
        """Save and lock the question on screen. Returns (question_id, skipped) or None if there is nothing to lock."""
        current = _current(db, exam_id)
        if not current or (body.question_id is not None and body.question_id != current[0]):
            return None
        question_id = current[0]
        answer = body.answer.strip()
        if not answer and final and not body.skip:
            # Ending on a question you have not touched drops it rather than counting it as a miss.
            db.execute("DELETE FROM exam_items WHERE exam_id = %s AND question_id = %s", (exam_id, question_id))
            return None
        if body.skip or not answer:
            db.execute("UPDATE rapid_items SET skipped = true, answered_at = now(), seconds_spent = %s WHERE exam_id = %s AND question_id = %s",
                       (body.seconds, exam_id, question_id))
            return question_id, True
        scan = db.execute("SELECT revision FROM exam_answer_scans WHERE exam_id = %s AND question_id = %s FOR UPDATE", (exam_id, question_id)).fetchone()
        if scan and scan[0] != body.scan_revision:
            raise HTTPException(409, "The uploaded pages changed. Check the latest transcription before moving on.")
        db.execute("UPDATE exam_items SET answer = %s, answer_revision = answer_revision + 1 WHERE exam_id = %s AND question_id = %s",
                   (body.answer, exam_id, question_id))
        if scan:
            db.execute("UPDATE exam_answer_scans SET confirmed = true WHERE exam_id = %s AND question_id = %s AND revision = %s", (exam_id, question_id, body.scan_revision))
        db.execute("UPDATE rapid_items SET answered_at = now(), seconds_spent = %s WHERE exam_id = %s AND question_id = %s", (body.seconds, exam_id, question_id))
        return question_id, False

    def session(db, exam_id):
        row = db.execute("SELECT topic_id, source, target_count, ended_at FROM rapid_sessions WHERE exam_id = %s FOR UPDATE", (exam_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Rapid session not found")
        return row

    # ---- sessions ------------------------------------------------------------------------------
    def kick_split(topic_id=None):
        """Split paper questions into parts in the background; one run per topic at a time."""
        if model_reply is None:
            return False
        key = topic_id or 0
        with _lock:
            if key in _splitting or 0 in _splitting:
                return False
            _splitting.add(key)

        def run():
            try:
                log.info("Rapid split finished: %s", splitting.split_pending(connect, model_reply, topic_id))
            except Exception as error:
                log.warning("Rapid split failed: %s", getattr(error, "detail", error))
            finally:
                with _lock:
                    _splitting.discard(key)
        userspace.submit(SPLITTERS, run)
        return True

    @router.post("/rapid/split", status_code=202)
    def split_questions(topic_id: int | None = None):
        """Split past-paper questions into their lettered parts (all topics, or one). Runs in the background."""
        with connect() as db:
            waiting = len(splitting.pending(db, topic_id, 100000))
        return {"waiting": waiting, "started": kick_split(topic_id) if waiting else False}

    @router.get("/rapid/split")
    def split_status():
        with connect() as db:
            rows = db.execute("""SELECT split_state, count(*) FROM exam_questions WHERE parent_id IS NULL AND source <> 'ai' GROUP BY 1""").fetchall()
            parts = db.execute("SELECT count(*) FROM exam_questions WHERE parent_id IS NOT NULL").fetchone()[0]
        names = {"": "waiting", "done": "split", "single": "single", "failed": "failed"}
        return {**{names.get(r[0], r[0]): r[1] for r in rows}, "parts": parts, "running": bool(_splitting)}

    @router.post("/rapid", status_code=201)
    def start(body: RapidStart):
        with connect() as db:
            topic = db.execute("SELECT subject_id FROM topics WHERE id = %s", (body.topic_id,)).fetchone()
            if not topic:
                raise HTTPException(404, "Topic not found")
            if body.source in ("ai", "mix") and not db.execute("SELECT 1 FROM topic_standards WHERE topic_id = %s", (body.topic_id,)).fetchone() and body.source == "ai":
                raise HTTPException(422, "Link an achievement standard to this topic before using AI questions")
            exam_id = db.execute("INSERT INTO exams (subject_id, kind, total_marks) VALUES (%s, 'rapid', 0) RETURNING id", (topic[0],)).fetchone()[0]
            db.execute("INSERT INTO rapid_sessions (exam_id, topic_id, source, target_count) VALUES (%s, %s, %s, %s)", (exam_id, body.topic_id, body.source, body.count))
            if body.source in ("ai", "mix"):
                # Reuse AI questions written earlier that nobody has been given yet.
                db.execute("""INSERT INTO rapid_queue (exam_id, question_id)
                    SELECT %s, q.id FROM exam_questions q WHERE q.source = 'ai' AND q.topic_id = %s
                      AND NOT EXISTS (SELECT 1 FROM exam_items i WHERE i.question_id = q.id)
                      AND NOT EXISTS (SELECT 1 FROM rapid_queue r WHERE r.question_id = q.id)
                    ORDER BY q.id LIMIT %s""", (exam_id, body.topic_id, BUFFER_TARGET))
            first = _advance(db, exam_id, body.topic_id, body.source, body.count)
            if body.source != "ai":
                kick_split(body.topic_id)     # questions added since the last run become available shortly
            if isinstance(first, str):
                raise HTTPException(409, "There are no questions for this topic yet" if body.source != "revision" else "Nothing to revise for this topic")
            question = _payload(db, exam_id, first)
        ensure_buffer(exam_id)
        return {"id": exam_id, "source": body.source, "target_count": body.count, "question": question}

    @router.get("/rapid/active")
    def active():
        with connect() as db:
            row = db.execute("""SELECT s.exam_id, s.topic_id, s.source, s.target_count, t.name FROM rapid_sessions s JOIN topics t ON t.id = s.topic_id
                WHERE s.ended_at IS NULL ORDER BY s.exam_id DESC LIMIT 1""").fetchone()
            if not row:
                return {"active": None}
            current = _current(db, row[0])
            answered = db.execute("SELECT count(*) FROM rapid_items WHERE exam_id = %s AND answered_at IS NOT NULL", (row[0],)).fetchone()[0]
            return {"active": {"id": row[0], "topic_id": row[1], "source": row[2], "target_count": row[3], "topic": row[4], "answered": answered,
                               "question": _payload(db, row[0], current[0]) if current else None}}

    @router.post("/rapid/{exam_id}/next")
    def next_question(exam_id: int, body: RapidMove = RapidMove()):
        locked = None
        with connect() as db:
            sess = session(db, exam_id)
            if sess[3]:
                raise HTTPException(409, "This session has ended")
            locked = lock_current(db, exam_id, body)
            if locked is None:
                current = _current(db, exam_id)
                if current:    # a retried request: the learner is already on the next question
                    return {"question": _payload(db, exam_id, current[0])}
            nxt = _advance(db, exam_id, sess[0], sess[1], sess[2])
            response = {nxt: True} if isinstance(nxt, str) else {"question": _payload(db, exam_id, nxt)}
        if locked and not locked[1]:
            queue_mark(exam_id, locked[0])
        ensure_buffer(exam_id)
        return response

    @router.post("/rapid/{exam_id}/end")
    def end(exam_id: int, body: RapidMove = RapidMove()):
        with connect() as db:
            sess = session(db, exam_id)
            if not sess[3]:
                lock_current(db, exam_id, body, final=True)
                db.execute("UPDATE rapid_sessions SET ended_at = now() WHERE exam_id = %s", (exam_id,))
                for (question_id,) in db.execute("SELECT question_id FROM rapid_items WHERE exam_id = %s AND skipped", (exam_id,)).fetchall():
                    _upsert_revision(db, exam_id, question_id, sess[0])
                    _queue_skipped_review(db, exam_id, question_id)
                apply_revision(db, exam_id)
                flush_pending_reviews(db, exam_id)
            counts = db.execute("""SELECT count(*) FILTER (WHERE NOT skipped AND answered_at IS NOT NULL), count(*) FILTER (WHERE skipped)
                FROM rapid_items WHERE exam_id = %s""", (exam_id,)).fetchone()
            unmarked = db.execute("""SELECT r.question_id FROM rapid_items r WHERE r.exam_id = %s AND NOT r.skipped AND r.answered_at IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM markings m WHERE m.exam_id = r.exam_id AND m.question_id = r.question_id AND m.kind = 'first')""", (exam_id,)).fetchall()
        for (question_id,) in unmarked:
            queue_mark(exam_id, question_id)
        return {"ended": True, "answered": counts[0], "skipped": counts[1]}

    @router.get("/rapid/{exam_id}/current")
    def current_question(exam_id: int):
        with connect() as db:
            sess = db.execute("SELECT ended_at FROM rapid_sessions WHERE exam_id = %s", (exam_id,)).fetchone()
            if not sess:
                raise HTTPException(404, "Rapid session not found")
            if sess[0]:
                raise HTTPException(409, "This session has ended")
            current = _current(db, exam_id)
            return {"question": _payload(db, exam_id, current[0]) if current else None}

    # ---- results -------------------------------------------------------------------------------
    def ensure_marking(exam_id):
        with connect() as db:
            rows = db.execute("""SELECT r.question_id FROM rapid_items r WHERE r.exam_id = %s AND NOT r.skipped AND r.answered_at IS NOT NULL
                AND NOT EXISTS (SELECT 1 FROM markings m WHERE m.exam_id = r.exam_id AND m.question_id = r.question_id AND m.kind = 'first')""", (exam_id,)).fetchall()
        for (question_id,) in rows:
            queue_mark(exam_id, question_id)

    def build_results(exam_id):
        with connect() as db:
            sess = db.execute("SELECT s.ended_at, s.topic_id, s.source, t.name, s.started_at FROM rapid_sessions s JOIN topics t ON t.id = s.topic_id WHERE s.exam_id = %s", (exam_id,)).fetchone()
            if not sess:
                raise HTTPException(404, "Rapid session not found")
            if not sess[0]:
                raise HTTPException(409, "Results are hidden until you end the session")
            rows = db.execute(f"""SELECT i.position, q.id, q.source, q.standard_number, q.year, q.parts, {_text_sql()}, q.figure_pages,
                    q.paper_resource_id, q.paper_page, q.schedule_resource_id, q.schedule_page, q.schedule_text, i.answer,
                    r.skipped, r.seconds_spent, q.parent_id, q.question_number
                FROM rapid_items r JOIN exam_items i ON i.exam_id = r.exam_id AND i.question_id = r.question_id
                JOIN exam_questions q ON q.id = r.question_id
                LEFT JOIN resource_pages page ON page.resource_id = q.paper_resource_id AND page.page = q.paper_page
                WHERE r.exam_id = %s ORDER BY i.position""", (exam_id,)).fetchall()
            marks = {r[0]: r[1] for r in db.execute("""SELECT DISTINCT ON (question_id) question_id, result FROM markings
                WHERE exam_id = %s AND kind = 'first' ORDER BY question_id, id DESC""", (exam_id,)).fetchall()}
            second = {r[0]: r[1] for r in db.execute("""SELECT DISTINCT ON (question_id) question_id, result FROM markings
                WHERE exam_id = %s AND kind = 'second' ORDER BY question_id, id DESC""", (exam_id,)).fetchall()}
            added = db.execute("SELECT count(*) FROM exam_revision WHERE last_exam_id = %s AND resolved_at IS NULL", (exam_id,)).fetchone()[0]
        items = []
        breakdown = {"not_achieved": 0, "achieved": 0, "merit": 0, "excellence": 0, "unclear": 0, "skipped": 0, "pending": 0, "failed": 0}
        for row in rows:
            ai = row[2] == "ai"
            item = {"position": row[0], "question_id": row[1], "source": "ai" if ai else "past", "standard_number": row[3],
                    "year": None if ai else row[4], "parts": row[5], "question_text": row[6][:30000], "figure_pages": row[7],
                    "paper_resource_id": None if ai or not row[8] else str(row[8]), "paper_page": None if ai else row[9],
                    "schedule_resource_id": None if ai or not row[10] else str(row[10]), "schedule_page": None if ai else row[11],
                    "schedule_text": row[12][:6000], "rubric_type": "AI-written rubric, unofficial" if ai else "registered schedule (machine-extracted)",
                    "answer": row[13] or "", "seconds": row[15], "label": row[17] if row[16] else None}
            result = marks.get(row[1])
            if row[14]:
                item.update(status="skipped", outcome="not_achieved", missed=True); breakdown["skipped"] += 1
            elif result:
                outcome = result.get("outcome")
                item.update(status="marked", outcome=outcome, marks_awarded=result.get("marks_awarded"), marks_available=result.get("marks_available"),
                            feedback=result.get("feedback", ""), evidence=result.get("evidence", []), missing=result.get("missing", []),
                            missed=outcome == "not_achieved")
                if second.get(row[1]) and second[row[1]].get("outcome") != outcome:
                    item["second_review_disagrees"] = True
                breakdown[outcome if outcome in OUTCOMES else "unclear"] += 1
            else:
                key = (exam_id, row[1])
                failed = _attempts.get(key, 0) >= MARK_RETRIES and key not in _inflight
                item.update(status="failed" if failed else "pending", outcome=None, missed=False)
                breakdown["failed" if failed else "pending"] += 1
            items.append(item)
        return {"id": exam_id, "topic": sess[3], "source": sess[2], "started_at": sess[4], "ended_at": sess[0],
                "questions": len(items), "answered": sum(1 for i in items if i["status"] != "skipped"),
                "seconds": sum(i["seconds"] or 0 for i in items), "breakdown": breakdown, "revision_added": added,
                "pending": breakdown["pending"], "items": items,
                "notice": "AI grades are unofficial study feedback, not NZQA results. Check the originals."}

    @router.get("/rapid/{exam_id}/results")
    def results(exam_id: int):
        data = build_results(exam_id)
        if data["pending"] or data["breakdown"]["failed"] == 0:
            ensure_marking(exam_id)
        return data

    @router.post("/rapid/{exam_id}/remark")
    def remark(exam_id: int):
        with _lock:
            for key in [k for k in _attempts if k[0] == exam_id]:
                _attempts.pop(key, None)
        ensure_marking(exam_id)
        return {"queued": True}

    @router.get("/rapid")
    def history(limit: int = 20):
        with connect() as db:
            rows = db.execute("""SELECT s.exam_id, t.name, s.source, s.started_at, s.ended_at,
                    count(r.*) FILTER (WHERE r.answered_at IS NOT NULL AND NOT r.skipped), count(r.*) FILTER (WHERE r.skipped)
                FROM rapid_sessions s JOIN topics t ON t.id = s.topic_id LEFT JOIN rapid_items r ON r.exam_id = s.exam_id
                WHERE s.ended_at IS NOT NULL GROUP BY s.exam_id, t.name ORDER BY s.exam_id DESC LIMIT %s""", (max(1, min(limit, 100)),)).fetchall()
        return [dict(zip(("id", "topic", "source", "started_at", "ended_at", "answered", "skipped"), row)) for row in rows]

    # ---- exam revision -------------------------------------------------------------------------
    @router.get("/exam-revision")
    def revision(topic_id: int | None = None, include_resolved: bool = False):
        with connect() as db:
            rows = db.execute(f"""SELECT r.question_id, r.topic_id, t.name, s.name, q.standard_number, q.year, q.source, {_text_sql()}, q.parts,
                    r.attempts, r.first_missed_at, r.last_attempt_at, r.resolved_at, i.answer, q.schedule_text, q.schedule_resource_id, q.schedule_page,
                    q.paper_resource_id, q.paper_page, (SELECT m.result->>'feedback' FROM markings m WHERE m.exam_id = r.last_exam_id
                        AND m.question_id = r.question_id AND m.kind = 'first' ORDER BY m.id DESC LIMIT 1),
                    q.parent_id, q.question_number
                FROM exam_revision r JOIN exam_questions q ON q.id = r.question_id JOIN topics t ON t.id = r.topic_id JOIN subjects s ON s.id = t.subject_id
                LEFT JOIN resource_pages page ON page.resource_id = q.paper_resource_id AND page.page = q.paper_page
                LEFT JOIN exam_items i ON i.exam_id = r.last_exam_id AND i.question_id = r.question_id
                WHERE (%s::bigint IS NULL OR r.topic_id = %s) AND (%s OR r.resolved_at IS NULL)
                ORDER BY r.resolved_at IS NOT NULL, r.last_attempt_at DESC""", (topic_id, topic_id, include_resolved)).fetchall()
        keys = ("question_id", "topic_id", "topic", "subject", "standard_number", "year", "source", "question_text", "parts", "attempts",
                "first_missed_at", "last_attempt_at", "resolved_at", "your_answer", "schedule_text", "schedule_resource_id", "schedule_page",
                "paper_resource_id", "paper_page", "feedback", "parent_id", "question_number")
        out = []
        for row in rows:
            item = dict(zip(keys, row))
            ai = item["source"] == "ai"
            item["label"] = item.pop("question_number") if item.pop("parent_id") else None
            item.update(source="ai" if ai else "past", year=None if ai else item["year"], question_text=(item["question_text"] or "")[:30000],
                        schedule_text=(item["schedule_text"] or "")[:6000], your_answer=item["your_answer"] or "",
                        schedule_resource_id=None if ai or not item["schedule_resource_id"] else str(item["schedule_resource_id"]),
                        paper_resource_id=None if ai or not item["paper_resource_id"] else str(item["paper_resource_id"]),
                        rubric_type="AI-written rubric, unofficial" if ai else "registered schedule (machine-extracted)")
            out.append(item)
        return out

    @router.get("/exam-revision/summary")
    def revision_summary():
        with connect() as db:
            rows = db.execute("""SELECT r.topic_id, t.name, s.name, count(*) FROM exam_revision r JOIN topics t ON t.id = r.topic_id
                JOIN subjects s ON s.id = t.subject_id WHERE r.resolved_at IS NULL GROUP BY r.topic_id, t.name, s.name ORDER BY s.name, t.name""").fetchall()
        return {"total": sum(r[3] for r in rows), "topics": [{"topic_id": r[0], "topic": r[1], "subject": r[2], "outstanding": r[3]} for r in rows]}

    return router
