"""Actual answer route on independent connections; uniquely scoped test tables.

Get-Content server/tests/concurrent_exam_check.py -Raw | docker compose exec -T api python -
No user exam modified. Simulates lost response by discarding a committed result,
not by dropping a real network connection.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier
from uuid import uuid4

from fastapi import HTTPException
from psycopg import sql

from app import connect
from exams import ExamAnswer, exam_router

schema = 'exam_check_' + uuid4().hex
barrier = Barrier(2, timeout=15)
competing = True


@contextmanager
def isolated_connection():
    with connect() as db:
        db.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        db.execute("SET LOCAL lock_timeout='10s'")
        if competing:
            barrier.wait()
        yield db


router = exam_router(isolated_connection, lambda: None)
save = next(r.endpoint for r in router.routes if r.path == '/exams/{exam_id}/answers/{question_id}' and 'PUT' in r.methods)


def edit(answer, revision=0):
    try:
        result = save(7, 2, ExamAnswer(answer=answer, revision=revision, scan_revision=0))
        return 200, result['answer'], result['revision']
    except HTTPException as exc:
        return exc.status_code, answer, None


try:
    with connect() as db:
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        for table in ('exam_items', 'exam_answer_scans', 'rapid_sessions'):
            db.execute(sql.SQL('CREATE TABLE {}.{} (LIKE public.{} INCLUDING ALL)').format(sql.Identifier(schema), sql.Identifier(table), sql.Identifier(table)))
        db.execute(sql.SQL("INSERT INTO {}.exam_items(exam_id,question_id,position,answer) VALUES (7,2,1,'Original')").format(sql.Identifier(schema)))
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(edit, answer) for answer in ('Client A', 'Client B')]
        results = [future.result(timeout=30) for future in futures]
    assert sorted(row[0] for row in results) == [200, 409], results
    winner = next(row[1] for row in results if row[0] == 200)
    competing = False
    with isolated_connection() as db:
        assert db.execute('SELECT answer,answer_revision FROM exam_items WHERE exam_id=7 AND question_id=2').fetchone() == (winner, 1)
    # Treat winning response as lost: client still has revision 0 and retries.
    assert edit(winner, revision=0)[0] == 409
    with isolated_connection() as db:
        assert db.execute('SELECT answer,answer_revision FROM exam_items WHERE exam_id=7 AND question_id=2').fetchone() == (winner, 1)
    assert edit('Recovered after reload', revision=1) == (200, 'Recovered after reload', 2)
    print('PASS: competing exam saves yield one success/one 409; lost-result retry cannot double-save; reloaded revision succeeds', results)
finally:
    with connect() as db:
        for table in ('exam_answer_scans', 'exam_items', 'rapid_sessions'):
            db.execute(sql.SQL('DROP TABLE IF EXISTS {}.{}').format(sql.Identifier(schema), sql.Identifier(table)))
        db.execute(sql.SQL('DROP SCHEMA IF EXISTS {}').format(sql.Identifier(schema)))
    print('CLEANUP: disposable exam tables/schema removed')
