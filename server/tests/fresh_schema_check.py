"""Verify actual lifespan migrations on an empty isolated PostgreSQL schema.

Run with current source mounted: python - < server/tests/fresh_schema_check.py
Background workers are stubbed, not started. Public study tables are untouched.
"""
import asyncio
from threading import Event
from uuid import uuid4

from psycopg import sql
import app

schema = 'startup_check_' + uuid4().hex
original = app.connect
original_scheduler, original_worker = app.start_scheduler, app.start_worker


def isolated():
    db = original()
    db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
    return db


class StoppedThread:
    def join(self, timeout): pass


async def check():
    async with app.lifespan(app.app):
        with isolated() as db:
            for table in ('subjects', 'topics', 'topic_style_profiles', 'lessons', 'exams', 'review_questions'):
                assert db.execute('SELECT to_regclass(%s)', (schema + '.' + table,)).fetchone()[0], table
    print('PASS: actual migrations initialise empty schema without starting background workers')


try:
    with original() as db:
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    app.connect = isolated
    app.start_scheduler = app.start_worker = lambda *args, **kwargs: (Event(), StoppedThread())
    asyncio.run(check())
finally:
    app.connect = original
    app.start_scheduler, app.start_worker = original_scheduler, original_worker
    with original() as db:
        tables = db.execute('SELECT tablename FROM pg_tables WHERE schemaname=%s', (schema,)).fetchall()
        for (table,) in tables:
            db.execute(sql.SQL('DROP TABLE {}.{} CASCADE').format(sql.Identifier(schema), sql.Identifier(table)))
        db.execute(sql.SQL('DROP SCHEMA {}').format(sql.Identifier(schema)))
    print('CLEANUP: unique startup-check schema removed')
