"""The global library: subjects, topics and files that every account can read and only administrators can change.

It lives in a library account of its own (id 0, schema u0) that the existing machinery treats like any other account, so
uploading, text extraction, paper import and maths restoration all work on it unchanged. Administrators edit it by sending
`X-Library: global` on library requests (see accounts.py).

Everyone else reads it through their own schema. Each account holds read-only copies of the global subjects and topics (marked
with global_id) and, once a topic is opened or switched on, of its files, their text, imported exam questions and schedules.
The files themselves are hard links, not copies. Because everything an account's lessons, exams and AI answers use is in its own
schema, they can only ever see global material plus what that account added itself.
"""
import logging
import os
import shutil

import userspace

log = logging.getLogger("uvicorn.error")

LIBRARY = userspace.LIBRARY_ID
SCHEMA = userspace.schema_name(LIBRARY)


def in_library():
    """True while the current request is editing the global library itself."""
    return userspace.current_user.get() == LIBRARY


def refuse_if_global(db, table, row_id, what):
    """Global subjects, topics and files cannot be changed by the account that merely reads them."""
    test = "is_global" if table == "resources" else "global_id IS NOT NULL"
    row = db.execute(f"SELECT {test} FROM {table} WHERE id = %s", (row_id,)).fetchone()
    if row and row[0]:
        from fastapi import HTTPException
        raise HTTPException(403, f"This {what} is part of the global library. Only an administrator can change it; you can add your own files beside it.")


def link_file(resource_id):
    """Make the global file available in the current account's folder without storing it twice."""
    source = userspace.upload_base() / SCHEMA / str(resource_id)
    target = userspace.upload_root() / str(resource_id)
    if target.exists() or not source.is_file():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def sync_catalog(db):
    """Every global subject and topic appears in this account (read-only). Cheap; safe to repeat."""
    if in_library():
        return
    g = SCHEMA
    db.execute(f"""INSERT INTO subjects (name, level, global_id) SELECT g.name, g.level, g.id FROM {g}.subjects g
        WHERE NOT EXISTS (SELECT 1 FROM subjects s WHERE s.global_id = g.id)""")
    db.execute(f"""UPDATE subjects s SET name = g.name, level = g.level FROM {g}.subjects g
        WHERE s.global_id = g.id AND (s.name, s.level) IS DISTINCT FROM (g.name, g.level)""")
    db.execute(f"""INSERT INTO topics (subject_id, name, position, global_id)
        SELECT s.id, g.name, g.position, g.id FROM {g}.topics g JOIN subjects s ON s.global_id = g.subject_id
        WHERE NOT EXISTS (SELECT 1 FROM topics t WHERE t.global_id = g.id)""")
    db.execute(f"""UPDATE topics t SET name = g.name, position = g.position FROM {g}.topics g
        WHERE t.global_id = g.id AND (t.name, t.position) IS DISTINCT FROM (g.name, g.position)""")


def sync_topic(db, topic_id):
    """Bring the global files, text, standards and imported questions of one topic into this account. Returns how many files were added."""
    if in_library():
        return 0
    row = db.execute("SELECT global_id FROM topics WHERE id = %s", (topic_id,)).fetchone()
    if not row or not row[0]:
        return 0
    gid, g = row[0], SCHEMA
    db.execute(f"INSERT INTO standards (number, title, description) SELECT number, title, description FROM {g}.standards ON CONFLICT (number) DO NOTHING")
    added = [r[0] for r in db.execute(f"""INSERT INTO resources (id, topic_id, filename, size, status, category, sha256, page_count, error, mime, is_global)
        SELECT g.id, %s, g.filename, g.size, g.status, g.category, g.sha256, g.page_count, g.error, g.mime, true FROM {g}.resources g
        WHERE g.topic_id = %s AND g.status = 'extracted' AND NOT EXISTS (SELECT 1 FROM resources r WHERE r.id = g.id)
        ON CONFLICT DO NOTHING RETURNING id""", (topic_id, gid)).fetchall()]
    if added:
        db.execute(f"INSERT INTO resource_text (resource_id, content) SELECT resource_id, content FROM {g}.resource_text WHERE resource_id = ANY(%s) ON CONFLICT DO NOTHING", (added,))
        db.execute(f"INSERT INTO resource_pages (resource_id, page, content) SELECT resource_id, page, content FROM {g}.resource_pages WHERE resource_id = ANY(%s) ON CONFLICT DO NOTHING", (added,))
        db.execute(f"""INSERT INTO resource_chunks (resource_id, topic_id, standard_number, page, ordinal, content, created_at)
            SELECT resource_id, %s, standard_number, page, ordinal, content, created_at FROM {g}.resource_chunks WHERE resource_id = ANY(%s)
            ON CONFLICT DO NOTHING""", (topic_id, added))
        for resource_id in added:
            link_file(resource_id)
    db.execute(f"INSERT INTO topic_standards (topic_id, standard_number) SELECT %s, standard_number FROM {g}.topic_standards WHERE topic_id = %s ON CONFLICT DO NOTHING", (topic_id, gid))
    has = "(q.{c} IS NULL OR EXISTS (SELECT 1 FROM resources r WHERE r.id = q.{c}))"
    db.execute(f"""INSERT INTO exam_questions (topic_id, standard_number, year, question_number, paper_resource_id, paper_page, schedule_resource_id,
            schedule_page, verified_at, marks, parts, question_text, schedule_text, figure_pages, source, math_state, math_display, global_id)
        SELECT %s, q.standard_number, q.year, q.question_number, q.paper_resource_id, q.paper_page, q.schedule_resource_id,
            q.schedule_page, q.verified_at, q.marks, q.parts, q.question_text, q.schedule_text, q.figure_pages, q.source, q.math_state, q.math_display, q.id
        FROM {g}.exam_questions q WHERE q.topic_id = %s AND q.parent_id IS NULL AND q.source <> 'ai'
          AND {has.format(c='paper_resource_id')} AND {has.format(c='schedule_resource_id')}
          AND NOT EXISTS (SELECT 1 FROM exam_questions l WHERE l.global_id = q.id)""", (topic_id, gid))
    # Improvements made in the library reach copies that no exam depends on, or whose parts still line up with saved answers.
    labels = "(SELECT array_agg(p->>'label') FROM jsonb_array_elements({0}.parts) p)"
    db.execute(f"""UPDATE exam_questions l SET parts = q.parts, question_text = q.question_text, schedule_text = q.schedule_text, figure_pages = q.figure_pages,
            marks = q.marks, math_state = q.math_state, math_display = q.math_display
        FROM {g}.exam_questions q WHERE l.global_id = q.id AND l.topic_id = %s
          AND (l.parts, l.question_text, l.schedule_text, l.figure_pages, l.marks) IS DISTINCT FROM (q.parts, q.question_text, q.schedule_text, q.figure_pages, q.marks)
          AND (NOT EXISTS (SELECT 1 FROM exam_items i WHERE i.question_id = l.id) OR {labels.format('l')} IS NOT DISTINCT FROM {labels.format('q')})""", (topic_id,))
    db.execute(f"""UPDATE exam_questions l SET math_state = q.math_state, math_display = q.math_display FROM {g}.exam_questions q
        WHERE l.global_id = q.id AND l.topic_id = %s AND q.math_state = 'done' AND l.math_state <> 'done'""", (topic_id,))
    db.execute(f"""INSERT INTO exam_grade_rules (standard_number, year, schedule_resource_id, page, achieved, merit, excellence, total, quote)
        SELECT r.standard_number, r.year, r.schedule_resource_id, r.page, r.achieved, r.merit, r.excellence, r.total, r.quote FROM {g}.exam_grade_rules r
        WHERE EXISTS (SELECT 1 FROM resources x WHERE x.id = r.schedule_resource_id) ON CONFLICT DO NOTHING""")
    db.execute(f"""INSERT INTO paper_import_runs (paper_id, schedule_id, status, detail, updated_at, parser_version)
        SELECT r.paper_id, r.schedule_id, r.status, r.detail, r.updated_at, r.parser_version FROM {g}.paper_import_runs r
        WHERE EXISTS (SELECT 1 FROM resources x WHERE x.id = r.paper_id) AND EXISTS (SELECT 1 FROM resources y WHERE y.id = r.schedule_id)
        ON CONFLICT DO NOTHING""")
    return len(added)


def sync_active(connect):
    """Per account, on the scheduler's tick: new global subjects and topics, and new files for every topic being studied."""
    if in_library():
        return
    with connect() as db:
        sync_catalog(db)
        for (topic_id,) in db.execute("SELECT c.topic_id FROM courses c JOIN topics t ON t.id = c.topic_id WHERE c.active AND t.global_id IS NOT NULL").fetchall():
            sync_topic(db, topic_id)


def adopt_library(connect_account, admin_id):
    """One time: the first administrator's existing library becomes the global library.

    Their rows keep their ids and simply gain a global_id pointing at the new shared copy, so their lessons, reviews and exams are untouched.
    Does nothing once the library has any subject, or when the administrator has none.
    """
    a, g = userspace.schema_name(admin_id), SCHEMA
    with connect_account() as db:
        if db.execute(f"SELECT 1 FROM {g}.subjects LIMIT 1").fetchone() or not db.execute(f"SELECT 1 FROM {a}.subjects LIMIT 1").fetchone():
            return False
        db.execute(f"INSERT INTO {g}.standards (number, title, description) SELECT number, title, description FROM {a}.standards ON CONFLICT DO NOTHING")
        db.execute(f"INSERT INTO {g}.subjects (id, name, level) OVERRIDING SYSTEM VALUE SELECT id, name, level FROM {a}.subjects")
        db.execute(f"INSERT INTO {g}.topics (id, subject_id, name, position) OVERRIDING SYSTEM VALUE SELECT id, subject_id, name, position FROM {a}.topics")
        db.execute(f"""INSERT INTO {g}.resources (id, topic_id, filename, size, status, category, sha256, page_count, error, mime)
            SELECT id, topic_id, filename, size, status, category, sha256, page_count, error, mime FROM {a}.resources WHERE status <> 'deleting'""")
        db.execute(f"INSERT INTO {g}.resource_text SELECT resource_id, content FROM {a}.resource_text WHERE resource_id IN (SELECT id FROM {g}.resources)")
        db.execute(f"INSERT INTO {g}.resource_pages SELECT resource_id, page, content FROM {a}.resource_pages WHERE resource_id IN (SELECT id FROM {g}.resources)")
        db.execute(f"""INSERT INTO {g}.resource_chunks (resource_id, topic_id, standard_number, page, ordinal, content, created_at)
            SELECT resource_id, topic_id, standard_number, page, ordinal, content, created_at FROM {a}.resource_chunks WHERE resource_id IN (SELECT id FROM {g}.resources)""")
        db.execute(f"INSERT INTO {g}.topic_standards SELECT topic_id, standard_number FROM {a}.topic_standards")
        db.execute(f"""INSERT INTO {g}.exam_questions (id, topic_id, standard_number, year, question_number, paper_resource_id, paper_page, schedule_resource_id,
                schedule_page, verified_at, marks, parts, question_text, schedule_text, figure_pages, source, math_state, math_display)
            OVERRIDING SYSTEM VALUE
            SELECT id, topic_id, standard_number, year, question_number, paper_resource_id, paper_page, schedule_resource_id,
                schedule_page, verified_at, marks, parts, question_text, schedule_text, figure_pages, source, math_state, math_display
            FROM {a}.exam_questions q WHERE parent_id IS NULL AND source <> 'ai'
              AND (paper_resource_id IS NULL OR paper_resource_id IN (SELECT id FROM {g}.resources))
              AND (schedule_resource_id IS NULL OR schedule_resource_id IN (SELECT id FROM {g}.resources))""")
        db.execute(f"INSERT INTO {g}.exam_grade_rules SELECT * FROM {a}.exam_grade_rules WHERE schedule_resource_id IN (SELECT id FROM {g}.resources)")
        db.execute(f"""INSERT INTO {g}.paper_import_runs (paper_id, schedule_id, status, detail, updated_at, parser_version)
            SELECT paper_id, schedule_id, status, detail, updated_at, parser_version FROM {a}.paper_import_runs
            WHERE paper_id IN (SELECT id FROM {g}.resources) AND schedule_id IN (SELECT id FROM {g}.resources)""")
        for table in ("subjects", "topics", "exam_questions"):
            db.execute(f"SELECT setval(pg_get_serial_sequence('{g}.{table}', 'id'), GREATEST((SELECT max(id) FROM {g}.{table}), 1))")
        db.execute(f"UPDATE {a}.subjects SET global_id = id WHERE id IN (SELECT id FROM {g}.subjects)")
        db.execute(f"UPDATE {a}.topics SET global_id = id WHERE id IN (SELECT id FROM {g}.topics)")
        db.execute(f"UPDATE {a}.exam_questions SET global_id = id WHERE id IN (SELECT id FROM {g}.exam_questions)")
        db.execute(f"UPDATE {a}.resources SET is_global = true WHERE id IN (SELECT id FROM {g}.resources)")
        ids = [r[0] for r in db.execute(f"SELECT id FROM {g}.resources").fetchall()]
    with userspace.as_user(LIBRARY):
        for resource_id in ids:
            source = userspace.upload_base() / a / str(resource_id)
            target = userspace.upload_root() / str(resource_id)
            if source.is_file() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(source, target)
                except OSError:
                    shutil.copy2(source, target)
    log.warning("Moved %s files of account %s into the global library", len(ids), admin_id)
    return True
