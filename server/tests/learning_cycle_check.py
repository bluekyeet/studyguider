"""Run: docker compose exec -T api python - < server/tests/learning_cycle_check.py

Real PostgreSQL, rollback-only synthetic records, no gateway calls. Never changes
existing study rows. This validates plumbing, not model teaching/marking quality.
"""
import json
import uuid
import app as application
from datetime import datetime, timezone
from contextlib import contextmanager
from zoneinfo import ZoneInfo

from app import connect
from lessons import LessonGeneration, lesson_router
from marking import queue_exam_review, marking_router
from reviews import ReviewAnswer, review_router
from exams import ExamAnswer, exam_router
from fastapi import HTTPException
from scheduler import run_due


db = connect()


@contextmanager
def transaction_connection():
    # Route contexts must not commit/close this rollback-only transaction.
    yield db


def endpoint(router, path):
    return next(route.endpoint for route in router.routes if route.path == path and "POST" in route.methods)


def draft(explanation, questions):
    return (f"## Learning goal\n{explanation}\n\n## Prior knowledge check\nRecall the meaning of the quantities.\n\n"
            f"## Explanation\n{explanation}\n\n## Worked Example\n{explanation}\n\n" +
            '\n\n'.join(f'### Your Turn {i}\n{question}' for i, question in enumerate(questions, 1)) +
            f"\n\n## Common mistakes\nCheck the units carefully.\n\n## Summary\n{explanation}")


frequency_draft = draft('Frequency is waves divided by time. Review the previous frequency mistake.', [
    'Eight waves pass in 20 seconds. Calculate the frequency in Hz. Relevant formulae: $f=N/t$, where $f$ is frequency in Hz, $N$ is wave count and $t$ is time in seconds.',
    'Explain what frequency measures for a repeating wave.',
    'Explain why a wave count alone is insufficient to calculate frequency.'])
chemistry_draft = draft('At fixed temperature, concentration changes collision frequency, not average kinetic energy.', [
    'Explain how increasing concentration affects collision frequency at fixed temperature.',
    'Explain whether increasing concentration at fixed temperature changes average kinetic energy.',
    'Explain why collision frequency and average kinetic energy are different quantities.'])


try:
    subject = db.execute("INSERT INTO subjects(name,level) VALUES ('Disposable cycle check',2) RETURNING id").fetchone()[0]
    topic = db.execute("INSERT INTO topics(subject_id,name) VALUES (%s,'Synthetic frequency') RETURNING id", (subject,)).fetchone()[0]
    note = db.execute("INSERT INTO notes(topic_id,content) VALUES (%s,'Original synthetic note') RETURNING id", (topic,)).fetchone()[0]
    original_connect = application.connect
    application.connect = transaction_connection
    try:
        first = application.edit_note(topic, note, application.NoteEdit(content='Client A saved note', original_content='Original synthetic note'))
        assert first['content'] == 'Client A saved note'
        try:
            application.edit_note(topic, note, application.NoteEdit(content='Client B stale note', original_content='Original synthetic note'))
            raise AssertionError('Stale note update must fail')
        except HTTPException as exc:
            assert exc.status_code == 409
        assert db.execute('SELECT content FROM notes WHERE id=%s', (note,)).fetchone()[0] == 'Client A saved note'
        db.execute('DELETE FROM notes WHERE id=%s', (note,))
        try:
            application.edit_note(topic, note, application.NoteEdit(content='Client B retry', original_content='Client A saved note'))
            raise AssertionError('Deleted note update must fail')
        except HTTPException as exc:
            assert exc.status_code == 404
    finally:
        application.connect = original_connect
    print('PASS: real note edit rejects stale content with 409, preserves newer content and reports deleted note as 404')
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
    strength_question = db.execute("""INSERT INTO review_questions(topic_id,question,due_date,concept)
        VALUES (%s,'State the unit of frequency.',CURRENT_DATE,'Frequency units') RETURNING id""", (topic,)).fetchone()[0]
    for _ in range(3):
        db.execute("""INSERT INTO review_answers(question_id,answer,confidence,correct)
            VALUES (%s,'Hz',4,true)""", (strength_question,))

    def model(name, messages, task):
        if task == 'review-mark':
            return json.dumps({"correct": False, "feedback": "Divide waves by seconds.", "concept": "Frequency"})
        if task == 'lesson-generate':
            payload = json.loads(messages[-1]['content'])
            assert any(item['concept'] == 'Frequency' for item in payload['review_focus'])
            assert payload['evidence']['sources'][0]['resource_id'] == str(resource)
            assert payload['learner_strengths'] == [{'concept': 'Frequency units', 'correct_answers': 3}]
            return frequency_draft
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
    assert any(item['concept'] == 'Frequency' for item in generated['review_focus'])
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
            assert payload['learner_strengths'] == []
            assert payload['evidence']['sources'][0]['resource_id'] == str(chemistry_resource)
            assert [item['number'] for item in payload['evidence']['standards']] == [91166]
            return chemistry_draft
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
    # Identical concept labels in a different topic must not suppress Physics strength.
    other_concept = db.execute("""INSERT INTO review_questions(topic_id,question,due_date,concept)
        VALUES (%s,'Synthetic other-topic check.',CURRENT_DATE,'Frequency units') RETURNING id""", (chemistry_topic,)).fetchone()[0]
    db.execute("INSERT INTO review_answers(question_id,answer,confidence,correct) VALUES (%s,'Wrong',4,false)", (other_concept,))
    physics_again = endpoint(router, '/topics/{topic_id}/lessons')(topic, LessonGeneration(query='Frequency'))
    assert physics_again['review_status'] == 'passed'

    db.execute("INSERT INTO review_answers(question_id,answer,confidence,correct) VALUES (%s,'Metres',4,false)", (strength_question,))
    strength_checked = []

    def recently_wrong_model(name, messages, task):
        if task == 'lesson-generate':
            payload = json.loads(messages[-1]['content'])
            assert payload['learner_strengths'] == []
            strength_checked.append(True)
            return frequency_draft
        return '{"pass":true,"issues":[]}'

    exclusion_router = lesson_router(transaction_connection, lambda: None, recently_wrong_model,
        lambda *args: [{"resource_id": str(resource), "filename": 'synthetic.txt', "page": 1, "content": rubric}],
        lambda *args: [{"number": 91170, "title": 'Waves', "description": 'Synthetic check'}])
    endpoint(exclusion_router, '/topics/{topic_id}/lessons')(topic, LessonGeneration(query='Frequency'))
    assert strength_checked == [True]
    print('PASS: three correct answers create a strength, other-topic mistakes do not suppress it, recent same-topic mistake excludes it')
    assert any(item['concept'] == 'Frequency' for item in db.execute('SELECT review_focus FROM lessons WHERE id=%s', (generated['id'],)).fetchone()[0])
    print('PASS: Physics/Chemistry lesson prompts and saved review focus remain isolated, including standards, evidence and learner-answer history')
    # Shadow scheduling tables for this connection only. Never disable or claim
    # existing users' schedules, even transiently inside the rollback transaction.
    for table in ('lesson_schedules', 'lesson_schedule_runs', 'courses'):
        db.execute(f'CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP')
    db.execute("""INSERT INTO lesson_schedules(topic_id,query,hour_utc,enabled,timezone)
        VALUES (%s,'Frequency',2,true,'Pacific/Auckland'),
               (%s,'Concentration',2,true,'Pacific/Auckland')""", (topic, chemistry_topic))
    scheduled_topics = []

    def scheduled_generate(topic_id, body):
        scheduled_topics.append(topic_id)
        if topic_id == topic:
            assert body.query == 'Frequency'
            return {'id': generated['id']}
        assert topic_id == chemistry_topic and body.query == 'Concentration'
        return {'id': chemistry['id']}

    # 13:00 UTC is 02:00 next day during NZ daylight saving.
    instant = datetime(2026, 11, 2, 13, tzinfo=timezone.utc)
    run_due(transaction_connection, scheduled_generate, instant.replace(hour=12))
    assert scheduled_topics == []
    run_due(transaction_connection, scheduled_generate, instant)
    run_due(transaction_connection, scheduled_generate, instant)
    assert sorted(scheduled_topics) == sorted([topic, chemistry_topic])
    runs = db.execute('SELECT topic_id,run_date,status,lesson_id FROM lesson_schedule_runs ORDER BY topic_id').fetchall()
    assert len(runs) == 2
    assert all(str(run[1]) == '2026-11-03' and run[2] == 'completed' for run in runs)
    assert {run[0]: run[3] for run in runs} == {topic: generated['id'], chemistry_topic: chemistry['id']}
    print('PASS: actual scheduler waits until Auckland 02:00, records next local date, links both subjects correctly and does not duplicate claims')
    # Each route connection gets a savepoint so persistence faults roll back just
    # that route, while all synthetic state remains in the outer rollback-only DB.
    for fault in ('none', 'before_link', 'commit_ack_lost', 'response_lost', 'provider_lost', 'claim_only'):
        db.execute('DELETE FROM lesson_schedule_runs')
        db.execute('UPDATE lesson_schedules SET enabled=(topic_id=%s)', (topic,))
        before = db.execute('SELECT count(*) FROM lessons WHERE topic_id=%s', (topic,)).fetchone()[0]
        calls = []

        class FaultDatabase:
            def execute(self, sql, params=()):
                if fault == 'before_link' and "SET status = 'completed'" in sql:
                    raise RuntimeError('Injected failure after lesson insert, before linkage')
                return db.execute(sql, params)

        @contextmanager
        def route_connection():
            db.execute('SAVEPOINT scheduled_route')
            try:
                yield FaultDatabase()
            except BaseException:
                db.execute('ROLLBACK TO SAVEPOINT scheduled_route')
                raise
            finally:
                db.execute('RELEASE SAVEPOINT scheduled_route')
            if fault == 'commit_ack_lost' and db.execute('SELECT status FROM lesson_schedule_runs WHERE topic_id=%s', (topic,)).fetchone()[0] == 'completed':
                # Simulate a commit accepted by the DB with its acknowledgement
                # lost to the caller; the outer transaction still rolls back.
                raise RuntimeError('Persistence commit acknowledgement lost')

        def fault_model(name, messages, task):
            if task == 'lesson-generate':
                calls.append(task)
                if fault == 'provider_lost':
                    raise RuntimeError('Provider response outcome unknown')
                return frequency_draft
            assert task == 'lesson-review'
            return '{"pass":true,"issues":[]}'

        fault_router = lesson_router(route_connection, lambda: None, fault_model,
            lambda *args: [{"resource_id": str(resource), "filename": 'synthetic.txt', "page": 1, "content": rubric}],
            lambda *args: [])

        def fault_generate(topic_id, body):
            saved = endpoint(fault_router, '/topics/{topic_id}/lessons')(topic_id, body)
            if fault == 'response_lost':
                raise RuntimeError('Persistence succeeded but response was lost')
            return saved

        if fault == 'claim_only':
            db.execute("""INSERT INTO lesson_schedule_runs(topic_id,run_date,query,status)
                VALUES (%s,%s,'Frequency','running')""", (topic, instant.astimezone(ZoneInfo('Pacific/Auckland')).date()))
        run_due(transaction_connection, fault_generate, instant)
        run_due(transaction_connection, fault_generate, instant)
        state = db.execute('SELECT status,lesson_id FROM lesson_schedule_runs WHERE topic_id=%s', (topic,)).fetchone()
        after = db.execute('SELECT count(*) FROM lessons WHERE topic_id=%s', (topic,)).fetchone()[0]
        if fault in ('none', 'commit_ack_lost', 'response_lost'):
            assert state[0] == 'completed' and state[1] is not None and after == before + 1, (fault, state)
        else:
            assert state == ('running' if fault == 'claim_only' else 'failed', None) and after == before, (fault, state)
        assert len(calls) == (0 if fault == 'claim_only' else 1), (fault, calls)
    print('PASS: real lesson insertion/run completion atomic; insert/link fault rolls back; lost persistence/provider responses and old running claims never trigger a second provider call')
    db.execute("""INSERT INTO exam_answer_scans(exam_id,question_id,image,transcription,confirmed)
        VALUES (%s,%s,%s,'55 Hz',true)""", (exam, question, b'synthetic image bytes'))
    db.execute("""INSERT INTO markings(exam_id,question_id,answer_hash,kind,result,model)
        VALUES (%s,%s,'synthetic-hash','first',%s::jsonb,'stub')""", (exam, question, json.dumps(mark)))
    db.execute('UPDATE markings SET answer_text=%s,scan_revision=1 WHERE exam_id=%s', ('55 Hz', exam))
    marking = marking_router(transaction_connection, lambda: None, None)
    read_feedback = next(r.endpoint for r in marking.routes if r.path == '/exams/{exam_id}/answers/{question_id}/feedback' and 'GET' in r.methods)
    assert read_feedback(exam, question)['marks'][0]['marks_awarded'] == 0
    db.execute('UPDATE exam_answer_scans SET confirmed=false WHERE exam_id=%s AND question_id=%s', (exam, question))
    try:
        read_feedback(exam, question)
        raise AssertionError('Unconfirmed scan feedback must be withheld')
    except HTTPException as exc:
        assert exc.status_code == 404
    db.execute('UPDATE exam_answer_scans SET confirmed=true,revision=2 WHERE exam_id=%s AND question_id=%s', (exam, question))
    try:
        read_feedback(exam, question)
        raise AssertionError('Old scan feedback must be withheld even when answer text is unchanged')
    except HTTPException as exc:
        assert exc.status_code == 404
    db.execute('UPDATE exam_answer_scans SET revision=1 WHERE exam_id=%s AND question_id=%s', (exam, question))
    print('PASS: saved feedback withheld for unconfirmed/replaced scans even with unchanged answer text')
    db.execute("""INSERT INTO marking_overrides(exam_id,question_id,outcome,note)
        VALUES (%s,%s,'not_achieved','Synthetic override')""", (exam, question))
    router = exam_router(transaction_connection, lambda: None)
    save = next(route.endpoint for route in router.routes if route.path == '/exams/{exam_id}/answers/{question_id}' and 'PUT' in route.methods)
    assert save(exam, question, ExamAnswer(answer='Client A answer', revision=0, scan_revision=1))['revision'] == 1
    try:
        read_feedback(exam, question)
        raise AssertionError('Previous answer feedback must be withheld')
    except HTTPException as exc:
        assert exc.status_code == 404
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
