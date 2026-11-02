"""Two actual route calls/connections in an isolated disposable schema.

Get-Content server/tests/concurrent_note_check.py -Raw | docker compose exec -T api python -
Only the script's uniquely named schema/table are created and removed.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier
from uuid import uuid4

from fastapi import HTTPException
from psycopg import sql

import app

schema = "note_check_" + uuid4().hex
original_connect = app.connect
barrier = Barrier(2, timeout=15)


@contextmanager
def isolated_connection():
    with original_connect() as db:
        db.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        db.execute("SET LOCAL lock_timeout='10s'")
        barrier.wait()
        yield db


def edit(content):
    try:
        result = app.edit_note(2, 42, app.NoteEdit(content=content, original_content='Original'))
        return 200, result['content']
    except HTTPException as exc:
        return exc.status_code, content


try:
    with original_connect() as db:
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        db.execute(sql.SQL('CREATE TABLE {}.notes (id bigint PRIMARY KEY, topic_id bigint NOT NULL, content text NOT NULL, created_at timestamptz NOT NULL DEFAULT now())').format(sql.Identifier(schema)))
        db.execute(sql.SQL("INSERT INTO {}.notes(id,topic_id,content) VALUES (42,2,'Original')").format(sql.Identifier(schema)))
    app.connect = isolated_connection
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(edit, content) for content in ('Client A', 'Client B')]
        results = [future.result(timeout=30) for future in futures]
    assert sorted(status for status, _ in results) == [200, 409], results
    winner = next(content for status, content in results if status == 200)
    with original_connect() as db:
        saved = db.execute(sql.SQL('SELECT content FROM {}.notes WHERE id=42').format(sql.Identifier(schema))).fetchone()[0]
    assert saved == winner, (saved, results)
    print('PASS: concurrent separate-connection note edits yield one success, one 409, winner preserved', results)
finally:
    app.connect = original_connect
    with original_connect() as db:
        db.execute(sql.SQL('DROP TABLE IF EXISTS {}.notes').format(sql.Identifier(schema)))
        db.execute(sql.SQL('DROP SCHEMA IF EXISTS {}').format(sql.Identifier(schema)))
    print('CLEANUP: only disposable note-check table/schema removed')
