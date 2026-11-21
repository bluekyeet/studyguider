"""Upgrading an account schema from the old names (courses, mastery) and many-Standard Topics to the glossary's terms.

Run with current source mounted, against a disposable database only: python - < server/tests/glossary_upgrade_check.py
An old-shape schema is made by building the current one and turning it back; init_schema then runs twice on it.
"""
from uuid import uuid4

from psycopg import sql
import app

schema = 'glossary_check_' + uuid4().hex
original = app.connect


def isolated():
    db = original()
    db.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
    return db


def columns(db, table):
    return {r[0] for r in db.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s",
                                     (schema, table)).fetchall()}


def old_shape(db):
    """Today's tables, renamed back to how an account looked before the glossary, with one Topic holding three Standards."""
    db.execute("DROP INDEX IF EXISTS topic_standards_one_per_topic")
    db.execute("ALTER TABLE learning_topics RENAME TO courses")
    db.execute("ALTER TABLE lessons RENAME COLUMN learning_topic_id TO course_id")
    db.execute("ALTER TABLE topics RENAME COLUMN predicted_recall TO mastery")
    db.execute("ALTER TABLE review_questions RENAME COLUMN predicted_recall TO mastery")
    subject = db.execute("INSERT INTO subjects (name, level) VALUES ('Maths', 1) RETURNING id").fetchone()[0]
    topic = db.execute("INSERT INTO topics (subject_id, name, mastery) VALUES (%s, 'Algebra', 0.4) RETURNING id", (subject,)).fetchone()[0]
    for number in (91027, 91028, 91029):
        db.execute("INSERT INTO standards (number, title) VALUES (%s, %s)", (number, f'Standard {number}'))
        db.execute("INSERT INTO topic_standards VALUES (%s, %s)", (topic, number))
    course = db.execute("INSERT INTO courses (topic_id, goal) VALUES (%s, 'Merit') RETURNING id", (topic,)).fetchone()[0]
    # A read-only copy of a global-library Topic: the library splits its own Topic and the split arrives through the sync.
    copy = db.execute("INSERT INTO topics (subject_id, name, global_id) VALUES (%s, 'Graphs', 777) RETURNING id", (subject,)).fetchone()[0]
    db.execute("INSERT INTO topic_standards VALUES (%s, 91027), (%s, 91029)", (copy, copy))
    db.execute("""INSERT INTO lessons (topic_id, query, lesson, review_status, sources, standards, course_id)
        VALUES (%s, 'q', 'text', 'passed', '[]', '[]', %s)""", (topic, course))
    db.execute("INSERT INTO resources (id, topic_id, filename, size, status) VALUES (%s, %s, 'notes.pdf', 1, 'ready')", (uuid4(), topic))
    db.execute("INSERT INTO review_questions (topic_id, question, due_date, mastery) VALUES (%s, 'Q?', current_date, 0.7)", (topic,))
    return subject, topic, course, copy


def check():
    with isolated() as db:
        app.init_schema(db)
        subject, topic, course, copy = old_shape(db)
    for _ in range(2):          # the upgrade, then a later start-up that must change nothing
        with isolated() as db:
            app.init_schema(db)
    with isolated() as db:
        assert db.execute("SELECT to_regclass(%s)", (schema + '.courses',)).fetchone()[0] is None
        assert 'learning_topic_id' in columns(db, 'lessons') and 'course_id' not in columns(db, 'lessons')
        assert db.execute("SELECT topic_id, learning_topic_id FROM lessons").fetchall() == [(topic, course)]
        assert db.execute("SELECT predicted_recall FROM topics WHERE id = %s", (topic,)).fetchone()[0] == 0.4
        assert db.execute("SELECT topic_id, predicted_recall FROM review_questions").fetchall() == [(topic, 0.7)]
        assert 'mastery' not in columns(db, 'topics') | columns(db, 'review_questions')
        topics = db.execute("""SELECT t.id, t.subject_id, t.name, array_agg(ts.standard_number) FROM topics t
            JOIN topic_standards ts ON ts.topic_id = t.id WHERE t.global_id IS NULL GROUP BY t.id ORDER BY t.id""").fetchall()
        assert [(t[1], t[2], t[3]) for t in topics] == [
            (subject, 'Algebra', [91027]), (subject, 'Algebra (91028)', [91028]), (subject, 'Algebra (91029)', [91029])], topics
        assert topics[0][0] == topic
        studied = db.execute("SELECT topic_id, goal, active FROM learning_topics ORDER BY id").fetchall()
        assert studied[0][0] == topic and db.execute("SELECT id FROM learning_topics WHERE topic_id = %s", (topic,)).fetchone()[0] == course
        assert studied == [(t[0], 'Merit', True) for t in topics], studied      # a split-off Standard is still being studied
        assert db.execute("SELECT standard_number FROM topic_standards WHERE topic_id = %s", (copy,)).fetchall() == [(91027,)]
        assert db.execute("SELECT count(*) FROM topics WHERE subject_id = %s", (subject,)).fetchone()[0] == 4    # no local split of the copy
        assert db.execute("SELECT topic_id FROM resources").fetchall() == [(topic,)]
        linked = db.execute("""SELECT x.topic_id, o.standard_number FROM topic_outcomes x JOIN outcomes o ON o.id = x.outcome_id
            ORDER BY x.topic_id""").fetchall()
        assert linked == sorted([(t[0], t[3][0]) for t in topics] + [(copy, 91027)]), linked
        db.execute("SAVEPOINT second")
        try:
            db.execute("INSERT INTO topic_standards VALUES (%s, 91028)", (topic,))
            raise AssertionError('a second Standard on one Topic was stored')
        except app.psycopg.errors.UniqueViolation:
            db.execute("ROLLBACK TO SAVEPOINT second")
    print('PASS: old names and many-Standard Topics upgrade to the glossary terms, and a second run changes nothing')


try:
    with original() as db:
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    app.connect = isolated
    check()
finally:
    app.connect = original
    with original() as db:
        db.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
    print('CLEANUP: glossary-check schema removed')
