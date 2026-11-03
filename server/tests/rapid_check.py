"""Real PostgreSQL checks for rapid sessions: blindness, locking, skipping, marking, misses and revision.

Run with the current source mounted (no gateway calls, no study data touched):
  docker compose run --rm -T -v "$PWD/server:/app" -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/app api python tests/rapid_check.py
Everything lives in one uniquely named schema that is dropped at the end. Model calls are stubbed (the real
marking route, validation and review hand-off run), so this proves session behaviour, not question quality.
"""
import asyncio
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

from fastapi import HTTPException
from psycopg import sql

import app
import rapid
import splitting
from exams import exam_router
from marking import marking_router
from rapid import RapidMove, RapidStart, rapid_router
from reviews import ReviewAnswer, review_router
from revision import PackStart, revision_router

SCHEMA = os.environ.get("RAPID_CHECK_SCHEMA") or "rapid_check_" + uuid4().hex
ORIGINAL = app.connect
RUBRIC = "Award 1 mark for the correct answer."


def isolated():
    db = ORIGINAL()
    db.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(SCHEMA)))
    return db


class StoppedThread:
    def join(self, timeout):
        pass


generated = []
pack_inputs = []


def model(name, messages, task="general"):
    """Stub gateway: marks by keyword, writes AI questions, and fails any question containing BAD."""
    if task in ("exam-mark", "exam-second-mark"):
        payload = json.loads(messages[1]["content"])
        right = "RIGHT" in payload["answer"]
        return json.dumps({"marks_awarded": 1 if right else 0, "marks_available": 1, "outcome": "achieved" if right else "not_achieved",
                           "feedback": "Checked against the schedule.", "evidence": [{"quote": RUBRIC, "explanation": "Criterion.", "marks": 1}] if right else [],
                           "missing": [] if right else ["The correct answer."], "confidence": 0.9})
    if task == "rapid-generate":
        count = json.loads(messages[1]["content"])["count"]
        items = []
        for i in range(count):
            n = len(generated) + 1
            generated.append(n)
            items.append({"question": f"{'BAD ' if n == 2 else ''}AI practice question number {n}: calculate the force on a 2.0 kg trolley.",
                          "rubric": "Achievement: F = ma. Merit: 6.0 N. Excellence: units and reasoning.", "marks": 4})
        return json.dumps(items)
    if task == "revision-pack":
        seen = json.loads(messages[1]["content"])
        pack_inputs.append(seen)
        return json.dumps({"sections": [{"concept": "Newton's second law", "why": "You skipped the force question.", "teaching": "Force is $F = ma$.",
            "questions": [{"question": f"A {m}.0 kg trolley accelerates at 2.0 m s-2; find the force.", "expected_answer": f"F = ma = {2 * m}.0 N"} for m in (1, 2, 3)]}]})
    if task == "revision-review":
        return json.dumps({"fail": [{"section": 0, "question": 2, "reason": "check"}]})
    if task == "review-mark":
        return json.dumps({"correct": "RIGHT" in json.loads(messages[1]["content"])["answer"], "feedback": "Marked.", "concept": "Newton's second law"})
    if task == "rapid-split":
        return json.dumps({"units": [
            {"label": "a", "context": "A trolley of mass 2.0 kg is pushed.", "question": "Find the force on the trolley.", "marks": 2, "schedule": "", "needs_figure": False},
            {"label": "b", "context": "A trolley of mass 2.0 kg is pushed.", "question": "State what happens when the push stops.", "marks": 1, "schedule": "", "needs_figure": False}]})
    if task == "rapid-review":
        question = json.loads(messages[1]["content"])["question"]
        return json.dumps({"pass": "BAD" not in question, "issues": ["ambiguous"] if "BAD" in question else []})
    raise AssertionError(task)


def search(topic_id, query):
    return [{"resource_id": "synthetic", "page": 1, "content": "Newton's second law."}]


def seed():
    with isolated() as db:
        subject = db.execute("INSERT INTO subjects(name, level) VALUES ('Check', 2) RETURNING id").fetchone()[0]
        topic = db.execute("INSERT INTO topics(subject_id, name) VALUES (%s, 'Forces') RETURNING id", (subject,)).fetchone()[0]
        db.execute("INSERT INTO standards(number, title) VALUES (99901, 'Synthetic standard') ON CONFLICT DO NOTHING")
        db.execute("INSERT INTO topic_standards(topic_id, standard_number) VALUES (%s, 99901)", (topic,))
        questions = []
        for n in range(1, 5):
            questions.append(db.execute("""INSERT INTO exam_questions (topic_id, standard_number, year, question_number, paper_page, schedule_page,
                marks, question_text, schedule_text, source) VALUES (%s, 99901, %s, %s, 1, 1, 1, %s, %s, 'pdf-layout') RETURNING id""",
                (topic, 2020 + n, str(n), f"Bank question {n}: find the acceleration.", RUBRIC)).fetchone()[0])
        db.execute("UPDATE exam_questions SET split_state = 'single' WHERE source = 'pdf-layout'")
        db.execute("""INSERT INTO exam_questions (topic_id, standard_number, year, question_number, paper_page, schedule_page,
            marks, parts, question_text, schedule_text, source) VALUES (%s, 99901, 2030, '9', 1, 1, 3, %s::jsonb, %s, %s, 'pdf-layout')""",
                   (topic, json.dumps([{"label": "a", "marks": 2}, {"label": "b", "marks": 1}]),
                    "QUESTION NINE\nA trolley of mass 2.0 kg is pushed.\n(a)\nFind the force on the trolley.\n(b)\nState what happens when the push stops.\n"
                    "3\nPhysics 91170, 2030\nASSESSOR’S\nUSE ONLY", RUBRIC))
    return topic, questions


def wait(condition, what, timeout=45):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return
        time.sleep(0.3)
    raise AssertionError(f"timed out waiting for {what}")


def endpoint(router, path, method):
    return next(r.endpoint for r in router.routes if r.path == path and method in r.methods)


async def main():
    with isolated() as schema_db:
        app.init_schema(schema_db)
    if True:
        topic, bank = seed()
        marking = marking_router(isolated, lambda: None, model)
        mark_answer = endpoint(marking, "/exams/{exam_id}/answers/{question_id}/feedback", "POST")
        get_feedback = endpoint(marking, "/exams/{exam_id}/answers/{question_id}/feedback", "GET")
        exams = exam_router(isolated, lambda: None, model, search)
        view_exam = endpoint(exams, "/exams/{exam_id}", "GET")
        list_exams = endpoint(exams, "/exams", "GET")
        put_answer = endpoint(exams, "/exams/{exam_id}/answers/{question_id}", "PUT")
        router = rapid_router(isolated, lambda: None, model, search, mark_answer)
        start = endpoint(router, "/rapid", "POST")
        nxt = endpoint(router, "/rapid/{exam_id}/next", "POST")
        end = endpoint(router, "/rapid/{exam_id}/end", "POST")
        results = endpoint(router, "/rapid/{exam_id}/results", "GET")
        active = endpoint(router, "/rapid/active", "GET")
        revision = endpoint(router, "/exam-revision", "GET")

        def results_done(exam_id):
            data = results(exam_id)
            return data if data["pending"] == 0 else None

        def refuses(call, label):
            try:
                call()
            except HTTPException as error:
                assert error.status_code == 409, (label, error.status_code)
                return
            raise AssertionError(f"{label}: should have been refused while the session is open")

        # 1. Blind while open, nothing leaked in the question, and locked answers stay locked.
        first = start(RapidStart(topic_id=topic, source="past", count=2))
        sid, q1 = first["id"], first["question"]
        assert not ({"schedule_text", "schedule_page", "rubric", "marks_awarded"} & set(q1)), q1.keys()
        assert q1["source"] == "past" and q1["position"] == 1 and first["target_count"] == 2
        refuses(lambda: view_exam(sid), "GET /exams/{id}")
        refuses(lambda: get_feedback(sid, q1["question_id"]), "GET feedback")
        refuses(lambda: put_answer(sid, q1["question_id"], type("B", (), {"answer": "x", "revision": 0, "scan_revision": 0})()), "PUT answer")
        assert sid not in [e["id"] for e in list_exams()], "rapid session must not appear in the exam list"
        assert active()["active"]["id"] == sid and active()["active"]["question"]["question_id"] == q1["question_id"]
        print("PASS blind while open; no schedule in the question; hidden from the exam list; resumable")

        second = nxt(sid, RapidMove(question_id=q1["question_id"], answer="RIGHT answer", seconds=12))
        q2 = second["question"]
        assert q2["position"] == 2 and q2["question_id"] != q1["question_id"]
        retry = nxt(sid, RapidMove(question_id=q1["question_id"], answer="changed my mind"))   # a retried request
        assert retry["question"]["question_id"] == q2["question_id"], "retry must return the question now on screen"
        with isolated() as db:
            assert db.execute("SELECT answer FROM exam_items WHERE exam_id=%s AND question_id=%s", (sid, q1["question_id"])).fetchone()[0] == "RIGHT answer"
        print("PASS answer locked after Next; a retried Next cannot overwrite it")

        done = nxt(sid, RapidMove(question_id=q2["question_id"], answer="wrong answer", seconds=9))
        assert done == {"finished": True}, done
        summary = end(sid)
        assert summary["ended"] and summary["answered"] == 2 and summary["skipped"] == 0
        data = wait_result = None
        wait(lambda: results_done(sid), "marking")
        data = results(sid)
        grades = [i["outcome"] for i in data["items"]]
        assert grades[0] in ("achieved", "merit", "excellence") and grades[1] == "not_achieved", grades   # the marking route derives the grade from marks
        b = data["breakdown"]
        assert b["achieved"] + b["merit"] + b["excellence"] == 1 and b["not_achieved"] == 1 and data["revision_added"] == 1
        with isolated() as db:
            assert db.execute("SELECT count(*) FROM exam_revision WHERE resolved_at IS NULL").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM review_questions WHERE exam_origin=%s", (f"{sid}:{q2['question_id']}",)).fetchone()[0] == 1
        print("PASS marked in the background after the end; breakdown correct; the miss reached revision and the lesson review queue")

        # 2. Skips count as misses; ending on an untouched question drops it.
        s2 = start(RapidStart(topic_id=topic, source="past", count=None))
        a = s2["question"]
        b = nxt(s2["id"], RapidMove(question_id=a["question_id"], skip=True))["question"]
        c = nxt(s2["id"], RapidMove(question_id=b["question_id"], answer="RIGHT again"))["question"]
        end(s2["id"], RapidMove(question_id=c["question_id"]))     # untouched final question
        wait(lambda: results_done(s2["id"]), "marking 2")
        d = results(s2["id"])
        assert [i["status"] for i in d["items"]] == ["skipped", "marked"] and d["questions"] == 2 and d["breakdown"]["skipped"] == 1, d["breakdown"]
        with isolated() as db:
            assert db.execute("SELECT count(*) FROM exam_revision WHERE question_id=%s AND resolved_at IS NULL", (a["question_id"],)).fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM review_questions WHERE exam_origin=%s", (f"{s2['id']}:{a['question_id']}",)).fetchone()[0] == 1
        print("PASS skip = miss (revision + review question); an untouched final question is dropped, not counted")

        # 3. Two simultaneous Nexts never serve the same question twice.
        s3 = start(RapidStart(topic_id=topic, source="past", count=None))
        a = s3["question"]["question_id"]
        with ThreadPoolExecutor(2) as pool:
            replies = list(pool.map(lambda _: nxt(s3["id"], RapidMove(question_id=a, answer="RIGHT")), range(2)))
        served = {r["question"]["question_id"] for r in replies}
        assert len(served) == 1, served
        with isolated() as db:
            assert db.execute("SELECT count(DISTINCT question_id) = count(*) FROM exam_items WHERE exam_id=%s", (s3["id"],)).fetchone()[0]
        end(s3["id"])
        print("PASS concurrent Next calls serve one question")

        # 4. Mixed sessions alternate real and AI questions; a question that fails review is never served.
        s4 = start(RapidStart(topic_id=topic, source="mix", count=None))
        wait(lambda: len(generated) >= 3, "generation")
        with isolated() as db:
            wait(lambda: db.execute("SELECT count(*) FROM rapid_queue WHERE exam_id=%s", (s4["id"],)).fetchone()[0] >= 2, "queue")
        sources = [s4["question"]["source"]]
        current = s4["question"]
        for _ in range(3):
            current = nxt(s4["id"], RapidMove(question_id=current["question_id"], answer="RIGHT"))["question"]
            sources.append(current["source"])
        assert sources == ["past", "ai", "past", "ai"], sources
        with isolated() as db:
            texts = [r[0] for r in db.execute("SELECT question_text FROM exam_questions WHERE source='ai'").fetchall()]
        assert texts and not any("BAD" in t for t in texts), texts
        assert current["year"] is None and current["paper_resource_id"] is None
        end(s4["id"])
        print("PASS mix alternates past/AI; AI questions prepared ahead; the failed one was dropped before serving; labelled AI")

        # 5. Revision sessions serve only unresolved misses and resolve them when you get them right.
        with isolated() as db:
            outstanding = [r[0] for r in db.execute("SELECT question_id FROM exam_revision WHERE resolved_at IS NULL").fetchall()]
        assert outstanding, "expected misses from earlier sessions"
        listed = revision(topic_id=topic)
        assert {r["question_id"] for r in listed} == set(outstanding) and all(r["your_answer"] is not None for r in listed)
        s5 = start(RapidStart(topic_id=topic, source="revision", count=None))
        cur = s5["question"]
        assert cur["question_id"] in outstanding
        end(s5["id"], RapidMove(question_id=cur["question_id"], answer="RIGHT now"))
        wait(lambda: results_done(s5["id"]), "marking revision")
        with isolated() as db:
            assert db.execute("SELECT resolved_at IS NOT NULL FROM exam_revision WHERE question_id=%s", (cur["question_id"],)).fetchone()[0]
        print("PASS revision redo serves only outstanding misses and clears one when answered correctly")

        # 7. A miss is neither recorded in Exam revision nor queued for lessons until the session ends.
        s7 = start(RapidStart(topic_id=topic, source="past", count=None))
        first7 = s7["question"]["question_id"]
        nxt(s7["id"], RapidMove(question_id=first7, answer="a wrong answer"))
        with isolated() as db:
            wait(lambda: db.execute("SELECT count(*) FROM markings WHERE exam_id=%s", (s7["id"],)).fetchone()[0] >= 1, "mid-session marking")
            assert db.execute("SELECT count(*) FROM exam_revision WHERE last_exam_id=%s", (s7["id"],)).fetchone()[0] == 0, "revision leaked mid-session"
            assert db.execute("SELECT count(*) FROM review_questions WHERE exam_origin=%s", (f"{s7['id']}:{first7}",)).fetchone()[0] == 0, "review queued mid-session"
            assert db.execute("SELECT count(*) FROM rapid_pending_reviews WHERE exam_id=%s", (s7["id"],)).fetchone()[0] == 1
        end(s7["id"])
        with isolated() as db:
            assert db.execute("SELECT count(*) FROM exam_revision WHERE last_exam_id=%s AND resolved_at IS NULL", (s7["id"],)).fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM review_questions WHERE exam_origin=%s", (f"{s7['id']}:{first7}",)).fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM rapid_pending_reviews WHERE exam_id=%s", (s7["id"],)).fetchone()[0] == 0
        print("PASS misses stay unrecorded (no revision entry, no lesson review) until End session, then both appear")

        # 6. Results are refused for an open session.
        s6 = start(RapidStart(topic_id=topic, source="past", count=3))
        refuses(lambda: results(s6["id"]), "results while open")
        end(s6["id"])
        print("PASS results refused until the session ends")

        # 8. A multi-part paper question is served one part at a time, each with its own context; the whole question is not.
        # Starting any session already queued the split in the background; wait for it, then run it again by hand.
        def split_done():
            with isolated() as db:
                return db.execute("SELECT split_state FROM exam_questions WHERE question_number = '9' AND parent_id IS NULL").fetchone()[0] == "done"
        wait(split_done, "the background split")
        with isolated() as db:
            parent = db.execute("SELECT id, split_state FROM exam_questions WHERE question_number = '9' AND parent_id IS NULL").fetchone()
            kids = db.execute("SELECT question_number, question_text, marks, year, source, verified_at FROM exam_questions WHERE parent_id = %s ORDER BY id", (parent[0],)).fetchall()
            assert parent[1] == "done" and [k[0] for k in kids] == ["9 a", "9 b"], (parent, kids)
            assert kids[0][1] == "A trolley of mass 2.0 kg is pushed.\n\nFind the force on the trolley." and kids[0][2] == 2 and kids[0][3] == 2030 and kids[0][4] == "part" and kids[0][5] is None
            assert "ASSESSOR" not in kids[1][1] and "Find the force" not in kids[1][1]          # part b shows only its own question
            assert splitting.split_pending(isolated, model, topic)["checked"] == 0                 # nothing left, and a rerun adds nothing
            assert db.execute("SELECT count(*) FROM exam_questions WHERE parent_id = %s", (parent[0],)).fetchone()[0] == 2
            papers = endpoint(exams, "/exam-papers", "GET")(topic)
            assert sum(p["question_count"] for p in papers) == 5, papers                           # four singles + the whole question 9; no parts
        s8 = start(RapidStart(topic_id=topic, source="past", count=None))
        seen, labels, current = [], [], s8["question"]
        while current:
            seen.append(current["question_id"])
            labels.append(current.get("label"))
            reply = nxt(s8["id"], RapidMove(question_id=current["question_id"], answer="RIGHT"))
            current = reply.get("question")
            if not current:
                break
        assert parent[0] not in seen, "the whole split question must not be served"
        assert sorted(l for l in labels if l) == ["9 a", "9 b"], labels
        assert len(seen) == 6, seen                      # 4 single questions + 2 parts
        end(s8["id"])
        # 9. Exam revision: a pack is built from the topic's mistakes and its questions are answered through the review marking.
        packs = revision_router(isolated, lambda: None, model, search)
        reviews = review_router(isolated, lambda: None, model)
        topics_route = endpoint(packs, "/revision/topics", "GET")
        start_pack = endpoint(packs, "/revision/packs", "POST")
        get_pack = endpoint(packs, "/revision/packs/{pack_id}", "GET")
        answer_review = endpoint(reviews, "/review-questions/{question_id}/answers", "POST")
        row = next(t for t in topics_route() if t["topic_id"] == topic)
        assert row["mistakes"] > 0, row
        started = start_pack(PackStart(topic_id=topic))
        again = start_pack(PackStart(topic_id=topic)) if started["status"] == "generating" else started
        assert again["id"] == started["id"], (started, again)               # a second press joins the running pack
        wait(lambda: get_pack(started["id"])["status"] != "generating", "the pack")
        pack = get_pack(started["id"])
        assert pack["status"] == "ready", pack
        assert len(pack["sections"]) == 1 and len(pack["sections"][0]["questions"]) == 2, pack      # the reviewer's failure was dropped
        assert any(m["from"].startswith("rapid exam") for m in pack["mistakes"]), pack["mistakes"]
        assert pack_inputs and pack_inputs[-1]["mistakes"] and pack_inputs[-1]["sources"], pack_inputs
        q1, q2 = pack["sections"][0]["questions"]
        assert "result" not in q1, "the expected answer must stay hidden until it is answered"
        with isolated() as db:
            made = db.execute("SELECT exam_origin, due_date > CURRENT_DATE + 1000 FROM review_questions WHERE id = ANY(%s)", ([q1["id"], q2["id"]],)).fetchall()
            assert all(o.startswith(f"pack:{started['id']}:") and far for o, far in made), made      # not in the daily review until answered
        wrong = answer_review(q1["id"], ReviewAnswer(answer="no idea", confidence=3))
        right = answer_review(q2["id"], ReviewAnswer(answer="RIGHT 6.0 N", confidence=3))
        assert wrong["correct"] is False and right["correct"] is True and wrong["interval_days"] == 1, (wrong, right)
        pack = get_pack(started["id"])
        assert pack["answered"] == 2 and pack["correct"] == 1 and pack["sections"][0]["questions"][0]["result"]["expected_answer"].startswith("F = ma"), pack
        refused = None
        try:
            start_pack(PackStart(topic_id=topic + 1000))
        except HTTPException as error:
            refused = error.status_code
        assert refused == 404, refused
        print("PASS revision pack: built from the topic's mistakes, failed question dropped, hidden until answered, marked through review")
        print("PASS a split question is served as its parts (own context, label, marks); the whole question and a rerun add nothing")


try:
    with ORIGINAL() as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(SCHEMA)))
    app.connect = isolated
    app.start_scheduler = app.start_worker = lambda *args, **kwargs: (Event(), StoppedThread())
    asyncio.run(main())
    print("ALL RAPID CHECKS PASSED")
finally:
    app.connect = ORIGINAL
    time.sleep(1)
    with ORIGINAL() as db:
        for (table,) in db.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s", (SCHEMA,)).fetchall():
            db.execute(sql.SQL("DROP TABLE {}.{} CASCADE").format(sql.Identifier(SCHEMA), sql.Identifier(table)))
        db.execute(sql.SQL("DROP SCHEMA IF EXISTS {}").format(sql.Identifier(SCHEMA)))
    print("CLEANUP: disposable schema removed")
