"""Rollback-only PostgreSQL selection check using connection-local temp tables.

Get-Content server/tests/collated_selection_check.py -Raw | docker compose exec -T api python -
"""
from contextlib import contextmanager
from app import connect
from exams import StartExam, exam_router

import app as application

ACCOUNT = 900002                      # a throwaway account whose empty tables are the template for the temp tables
application.provision_account(ACCOUNT)
db = connect()


@contextmanager
def connection():
    yield db


try:
    for table in ('topics', 'exam_questions', 'exams', 'exam_items'):
        db.execute(f'CREATE TEMP TABLE {table} (LIKE u900002.{table} INCLUDING ALL) ON COMMIT DROP')
    db.execute("INSERT INTO topics(id,subject_id,name) OVERRIDING SYSTEM VALUE VALUES (1,1,'Synthetic selection')")
    for ident in range(1, 5):
        db.execute("""INSERT INTO exam_questions(id,topic_id,standard_number,year,question_number,paper_page,schedule_page,marks,source)
            OVERRIDING SYSTEM VALUE VALUES (%s,1,91170,2024,%s,1,1,1,'pdf-layout')""", (ident, str(ident)))
    start = next(r.endpoint for r in exam_router(connection, lambda: None).routes if r.path == '/exams/start')
    selections = []
    for _ in range(3):
        exam = start(StartExam(topic_id=1, mode='mixed', question_count=2))
        selections.append([r[0] for r in db.execute('SELECT question_id FROM exam_items WHERE exam_id=%s ORDER BY position', (exam['id'],)).fetchall()])
    assert selections == [[1, 2], [3, 4], [1, 2]], selections
    print('PASS: collated selection uses unseen questions before exhaustion, then oldest-used questions', selections)
finally:
    db.rollback()
    db.close()
    with application.connect_account() as account_db:
        account_db.execute(f'DROP SCHEMA IF EXISTS u{ACCOUNT} CASCADE')
    print('ROLLBACK: temporary selection tables removed; sequence gaps possible')
