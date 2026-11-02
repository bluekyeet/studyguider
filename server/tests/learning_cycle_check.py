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
from exams import ExamAnswer, exam_router
from fastapi import HTTPException


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
    # A second subject must not inherit the Physics review or learner answers.
    db.execute("UPDATE lessons SET completed_at=now() WHERE id=%s", (generated['id'],))
    db.execute("INSERT INTO lesson_answers(lesson_id,question_key,question,answer,feedback) VALUES (%s,'synthetic-key','Physics-only question','Physics-only answer','Physics-only feedback')", (generated['id'],))
    chemistry_subject = db.execute("INSERT INTO subjects(name,level) VALUES ('Disposable Chemistry check',2) RETURNING id").fetchone()[0]
    chemistry_topic = db.execute("INSERT INTO topics(subject_id,name) VALUES (%s,'Synthetic concentration') RETURNING id", (chemistry_subject,)).fetchone()[0]
    chemistry_resource = uuid.uuid4()
    db.execute("INSERT INTO resources(id,topic_id,filename,size,status) VALUES (%s,%s,'synthetic-chemistry.txt',40,'extracted')", (chemistry_resource, chemistry_topic))
    db.execute("""INSERT INTO review_questions(topic_id,question,due_date,concept)
        VALUES (%s,'Explain concentration and collisions.',CURRENT_DATE,'Collision frequency')""", (chemistry_topic,))

    def chemistry_model(name, messages, task):
        payload = json.loads(messages[-1]['content'])
        if task == 'lesson-generate':
            assert [item['concept'] for item in payload['review_focus']] == ['Collision frequency']
            assert payload['learner_answers'] == [] and payload['completed_lessons'] == []
            assert payload['evidence']['sources'][0]['resource_id'] == str(chemistry_resource)
            assert [item['number'] for item in payload['evidence']['standards']] == [91166]
            return 'At fixed temperature, concentration changes collision frequency, not average kinetic energy.'
        assert task == 'lesson-review'
        assert payload['evidence']['sources'][0]['resource_id'] == str(chemistry_resource)
        return '{"pass":true,"issues":[]}'

    chemistry_router = lesson_router(transaction_connection, lambda: None, chemistry_model,
        lambda *args: [{"resource_id": str(chemistry_resource), "filename": 'synthetic-chemistry.txt', "page": 1,
                       "content": 'At fixed temperature concentration affects collision frequency.'}],
        lambda *args: [{"number": 91166, "title": 'Reactivity', "description": 'Synthetic chemistry check'}])
    chemistry = endpoint(chemistry_router, '/topics/{topic_id}/lessons')(chemistry_topic, LessonGeneration(query='Concentration'))
    assert chemistry['review_status'] == 'passed'
    assert chemistry['topic_id'] == chemistry_topic
    assert chemistry['review_focus'][0]['concept'] == 'Collision frequency'
    assert db.execute('SELECT review_focus FROM lessons WHERE id=%s', (generated['id'],)).fetchone()[0][0]['concept'] == 'Frequency'
    print('PASS: Physics/Chemistry lesson prompts and saved review focus remain isolated, including standards, evidence and learner-answer history')
    db.execute("""INSERT INTO exam_answer_scans(exam_id,question_id,image,transcription,confirmed)
        VALUES (%s,%s,%s,'55 Hz',true)""", (exam, question, b'synthetic image bytes'))
    db.execute("""INSERT INTO markings(exam_id,question_id,answer_hash,kind,result,model)
        VALUES (%s,%s,'synthetic-hash','first',%s::jsonb,'stub')""", (exam, question, json.dumps(mark)))
    db.execute("""INSERT INTO marking_overrides(exam_id,question_id,outcome,note)
        VALUES (%s,%s,'not_achieved','Synthetic override')""", (exam, question))
    router = exam_router(transaction_connection, lambda: None)
    save = next(route.endpoint for route in router.routes if route.path == '/exams/{exam_id}/answers/{question_id}' and 'PUT' in route.methods)
    assert save(exam, question, ExamAnswer(answer='Client A answer', revision=0, scan_revision=1))['revision'] == 1
    # Savepoints model request transaction rollback after expected HTTP conflicts.
    def conflict(body):
        db.execute('SAVEPOINT expected_conflict')
        try:
            save(exam, question, body)
            raise AssertionError('Stale client must not save')
        except HTTPException as exc:
            assert exc.status_code == 409
        finally:
            db.execute('ROLLBACK TO SAVEPOINT expected_conflict')
            db.execute('RELEASE SAVEPOINT expected_conflict')
    conflict(ExamAnswer(answer='Client B stale answer', revision=0, scan_revision=1))
    assert db.execute('SELECT answer,answer_revision FROM exam_items WHERE exam_id=%s AND question_id=%s', (exam, question)).fetchone() == ('Client A answer', 1)
    db.execute("UPDATE exam_answer_scans SET revision=2, confirmed=false, transcription='Replacement scan' WHERE exam_id=%s AND question_id=%s", (exam, question))
    conflict(ExamAnswer(answer='Old transcription', revision=1, scan_revision=1))
    assert db.execute('SELECT confirmed FROM exam_answer_scans WHERE exam_id=%s AND question_id=%s', (exam, question)).fetchone()[0] is False
    assert save(exam, question, ExamAnswer(answer='Checked replacement scan', revision=1, scan_revision=2))['revision'] == 2
    assert db.execute('SELECT confirmed FROM exam_answer_scans WHERE exam_id=%s AND question_id=%s', (exam, question)).fetchone()[0] is True
    print('PASS: stale answer/scan clients rejected with 409; newer answer preserved; checked replacement saves and confirms')
    delete = next(route.endpoint for route in router.routes if route.path == '/exams/{exam_id}' and 'DELETE' in route.methods)
    assert delete(exam).status_code == 204
    for table in ('exam_items', 'exam_answer_scans', 'markings', 'marking_overrides'):
        assert db.execute(f'SELECT count(*) FROM {table} WHERE exam_id=%s', (exam,)).fetchone()[0] == 0, table
    assert db.execute('SELECT 1 FROM exam_questions WHERE id=%s', (question,)).fetchone()
    assert db.execute('SELECT 1 FROM resources WHERE id=%s', (resource,)).fetchone()
    assert db.execute('SELECT 1 FROM review_questions WHERE id=%s', (reviews[0][0],)).fetchone()
    try:
        delete(exam)
        raise AssertionError('Deleting a missing exam must fail')
    except HTTPException as exc:
        assert exc.status_code == 404
    print('PASS: deleting attempt cascades answers/scans/marks/overrides, preserves bank/source/review snapshot, repeated delete returns 404')
finally:
    db.rollback()
    db.close()
    print('ROLLBACK: synthetic records discarded; identity sequence gaps may remain')
