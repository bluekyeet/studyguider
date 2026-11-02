"""Opt-in three uncached marks using actual marking route and rollback-only data.

Get-Content server/tests/live_mark_consistency_check.py -Raw |
  docker compose exec -T -e RUN_LIVE_MARK_CHECK=yes api python -
Uses an explicitly unofficial synthetic rubric; gateway usage records remain.
"""
import json
import os
from contextlib import contextmanager

from app import connect, model_reply
from marking import marking_router

assert os.environ.get("RUN_LIVE_MARK_CHECK") == "yes"
db = connect()


@contextmanager
def connection():
    yield db


calls = []


def model(name, messages, task):
    calls.append(task)
    return model_reply(name, messages, task="acceptance-" + task)


try:
    subject = db.execute("INSERT INTO subjects(name,level) VALUES ('Disposable marking check',2) RETURNING id").fetchone()[0]
    topic = db.execute("INSERT INTO topics(subject_id,name) VALUES (%s,'Synthetic frequency') RETURNING id", (subject,)).fetchone()[0]
    rubric = "Award 1 mark for frequency 0.40 Hz (or 0.4 Hz) with units. Award 0 marks for any other answer."
    question = db.execute("""INSERT INTO exam_questions(topic_id,standard_number,year,question_number,paper_page,schedule_page,marks,question_text,schedule_text,source)
        VALUES (%s,91170,2026,'1',1,1,1,'Eight complete waves pass in twenty seconds. Calculate frequency including units.',%s,'ai') RETURNING id""", (topic, rubric)).fetchone()[0]
    exam = db.execute("INSERT INTO exams(subject_id) VALUES (%s) RETURNING id", (subject,)).fetchone()[0]
    db.execute("INSERT INTO exam_items(exam_id,question_id,position,answer) VALUES (%s,%s,1,'0.4 Hz')", (exam, question))
    router = marking_router(connection, lambda: None, model)
    mark = next(r.endpoint for r in router.routes if r.path == '/exams/{exam_id}/answers/{question_id}/feedback' and 'POST' in r.methods)
    results = []
    for attempt in range(3):
        # Only disposable attempt rows; force fresh generation, never touch user cache.
        db.execute('DELETE FROM markings WHERE exam_id=%s', (exam,))
        result = mark(exam, question)
        assert result['cached'] is False
        assert result['evidence'], 'Positive mark must cite rubric'
        results.append((result['marks_awarded'], result['marks_available'], result['outcome']))
        print('FRESH_MARK', attempt + 1, results[-1], flush=True)
    assert len(set(results)) == 1 and results[0][:2] == (1, 1), results
    assert calls.count('exam-mark') >= 3, calls
    print('PASS: three fresh marks agree on this synthetic full-credit answer; not official NZQA accuracy or proof gateway has no upstream cache')
finally:
    db.rollback()
    db.close()
    print('ROLLBACK: synthetic study records discarded; sequence gaps may remain')
