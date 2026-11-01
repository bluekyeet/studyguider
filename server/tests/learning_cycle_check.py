"""Run: docker compose exec -T api python - < server/tests/learning_cycle_check.py

Real PostgreSQL, rollback-only synthetic records, no gateway calls. Never changes
existing study rows. This validates plumbing, not model teaching/marking quality.
"""
import json
import uuid
from contextlib import contextmanager

from app import connect
from lessons import LessonGeneration, lesson_router
from marking import queue_exam_review
from reviews import ReviewAnswer, review_router


db = connect()


@contextmanager
def transaction_connection():
    # Route contexts must not commit/close this rollback-only transaction.
    yield db


def endpoint(router, path):
    return next(route.endpoint for route in router.routes if route.path == path and "POST" in route.methods)


try:
    subject = db.execute("INSERT INTO subjects(name,level) VALUES ('Disposable cycle check',2) RETURNING id").fetchone()[0]
    topic = db.execute("INSERT INTO topics(subject_id,name) VALUES (%s,'Synthetic frequency') RETURNING id", (subject,)).fetchone()[0]
    resource = uuid.uuid4()
    db.execute("INSERT INTO resources(id,topic_id,filename,size,status) VALUES (%s,%s,'synthetic.txt',40,'extracted')", (resource, topic))
    exam = db.execute("INSERT INTO exams(subject_id) VALUES (%s) RETURNING id", (subject,)).fetchone()[0]
    question = db.execute("""INSERT INTO exam_questions(topic_id,standard_number,year,question_number,paper_page,schedule_page,marks,question_text,schedule_text,source)
        VALUES (%s,91170,2026,'1',1,1,1,'Calculate frequency for 8 waves in 20 seconds.','Frequency is waves divided by time: 0.4 Hz.','ai') RETURNING id""", (topic,)).fetchone()[0]
    db.execute("INSERT INTO exam_items(exam_id,question_id,position,answer) VALUES (%s,%s,1,'55 Hz')", (exam, question))
    rubric = "Frequency is waves divided by time: 0.4 Hz."
    row = ('55 Hz', '1', 91170, 2026, 1, 'Calculate frequency for 8 waves in 20 seconds.', rubric,
           None, 1, '', None, 1, '', '', 'Synthetic frequency', 'Disposable cycle check', topic)
    mark = {"marks_awarded": 0, "marks_available": 1, "outcome": "not_achieved", "confidence": 1,
            "missing": ["Frequency is waves divided by time"]}
    for _ in range(2):
        queue_exam_review(transaction_connection, exam, question, row, mark, rubric)
    reviews = db.execute("SELECT id,expected_answer,source FROM review_questions WHERE topic_id=%s", (topic,)).fetchall()
    assert len(reviews) == 1 and reviews[0][1] == rubric
    assert reviews[0][2][0]['rubric_type'] == 'unofficial AI practice rubric'

    def model(name, messages, task):
        if task == 'review-mark':
            return json.dumps({"correct": False, "feedback": "Divide waves by seconds.", "concept": "Frequency"})
        if task == 'lesson-generate':
            payload = json.loads(messages[-1]['content'])
            assert any(item['concept'] == 'Frequency' for item in payload['review_focus'])
            assert payload['evidence']['sources'][0]['resource_id'] == str(resource)
            return 'Frequency is waves divided by time. Review the previous frequency mistake.'
        if task == 'lesson-review':
            return '{"pass":true,"issues":[]}'
        raise AssertionError(task)

    review = endpoint(review_router(transaction_connection, lambda: None, model), '/review-questions/{question_id}/answers')
    review(reviews[0][0], ReviewAnswer(answer='55 Hz', confidence=5))
    scheduled = db.execute("SELECT interval_days,mastery FROM review_questions WHERE id=%s", (reviews[0][0],)).fetchone()
    assert scheduled[0] == 1
    router = lesson_router(transaction_connection, lambda: None, model,
        lambda *args: [{"resource_id": str(resource), "filename": 'synthetic.txt', "page": 1, "content": rubric}],
        lambda *args: [{"number": 91170, "title": 'Waves', "description": 'Synthetic check'}])
    generated = endpoint(router, '/topics/{topic_id}/lessons')(topic, LessonGeneration(query='Frequency'))
    assert generated['review_status'] == 'passed'
    assert generated['review_focus'][0]['concept'] == 'Frequency'
    print('PASS: exam mistake deduplicated -> wrong review scheduled for one day -> next lesson receives weakness and isolated evidence')
finally:
    db.rollback()
    db.close()
    print('ROLLBACK: synthetic records discarded; identity sequence gaps may remain')
