"""Opt-in: mark real registered questions against their real schedules, rollback-only.

Get-Content server/tests/live_schedule_mark_check.py -Raw |
  docker compose exec -T -e RUN_LIVE_MARK_CHECK=yes -e PYTHONPATH=/app api python -
For each sampled question two answers are marked: a non-answer, and the schedule's own full text
(descriptors plus model answers) used as the answer (an upper bracket, not a real student). Expect the second to score higher.
This is a sanity bracket, not agreement with human NCEA markers. Everything is rolled back.
"""
import os
from contextlib import contextmanager

from app import connect, model_reply
from marking import marking_router

assert os.environ.get("RUN_LIVE_MARK_CHECK") == "yes"
db = connect()


@contextmanager
def connection():
    yield db


def model(name, messages, task):
    return model_reply(name, messages, task="acceptance-" + task)


try:
    standards = [int(n) for n in os.environ.get("MARK_STANDARDS", "").split(",") if n] or None
    sample = db.execute("""SELECT DISTINCT ON (standard_number) id, topic_id, standard_number, year, question_number, schedule_text
        FROM exam_questions WHERE schedule_resource_id IS NOT NULL AND paper_resource_id IS NOT NULL
          AND marks > 0 AND length(question_text) > 100 AND length(schedule_text) BETWEEN 1500 AND 8000
          AND (%s::int[] IS NULL OR standard_number = ANY(%s::int[]))
        ORDER BY standard_number, year DESC, id""", (standards, standards)).fetchall()
    router = marking_router(connection, lambda: None, model)
    mark = next(r.endpoint for r in router.routes if r.path == '/exams/{exam_id}/answers/{question_id}/feedback' and 'POST' in r.methods)
    ok = 0
    for qid, topic, standard, year, number, schedule in sample:
        subject = db.execute("SELECT subject_id FROM topics WHERE id=%s", (topic,)).fetchone()[0]
        exam = db.execute("INSERT INTO exams(subject_id) VALUES (%s) RETURNING id", (subject,)).fetchone()[0]
        db.execute("INSERT INTO exam_items(exam_id,question_id,position,answer) VALUES (%s,%s,1,'x')", (exam, qid))
        scores = []
        for label, answer in (("non-answer", "I don't know."), ("schedule-text", schedule[:8000])):
            db.execute("UPDATE exam_items SET answer=%s WHERE exam_id=%s AND question_id=%s", (answer, exam, qid))
            db.execute("DELETE FROM markings WHERE exam_id=%s", (exam,))
            try:
                r = mark(exam, qid)
                scores.append(r['marks_awarded'])
                print(f"AS{standard} {year} Q{number} {label}: FB={r.get('feedback','')[:300]!r} {r['marks_awarded']}/{r['marks_available']} {r['outcome']} conf={r.get('confidence')}", flush=True)
            except Exception as e:
                scores.append(None)
                print(f"AS{standard} {year} Q{number} {label}: ERROR {getattr(e, 'detail', e)}", flush=True)
        good = None not in scores and scores[1] > scores[0]
        ok += good
        print("  ordered correctly" if good else "  NOT ordered / error", flush=True)
    print(f"DONE: {ok} of {len(sample)} questions scored the schedule text above a non-answer")
finally:
    db.rollback()
    db.close()
    print("ROLLBACK: disposable exam rows discarded")
