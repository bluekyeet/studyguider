"""Automatic source-paired PDF imports; ambiguous layouts remain visibly flagged."""
import userspace
import json
import os
from pathlib import Path

from paper_parser import file_identity, parse_pair, cut_scores


def create_import_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS paper_import_runs (
        paper_id uuid PRIMARY KEY REFERENCES resources(id) ON DELETE CASCADE,
        schedule_id uuid NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
        status text NOT NULL, detail text NOT NULL DEFAULT '', updated_at timestamptz NOT NULL DEFAULT now())""")
    db.execute("ALTER TABLE paper_import_runs ADD COLUMN IF NOT EXISTS parser_version integer NOT NULL DEFAULT 1")


def import_topic_papers(connect, topic_id):
    with connect() as db:
        resources = db.execute("SELECT id, filename FROM resources WHERE topic_id=%s AND status='extracted' ORDER BY id", (topic_id,)).fetchall()
    pairs = {}
    for resource_id, filename in resources:
        identity = file_identity(Path(filename).name)
        if identity:
            standard, year, kind = identity
            pairs.setdefault((standard, year), {}).setdefault(kind, []).append((resource_id, filename))
    results = []
    for (standard, year), pair in pairs.items():
        if len(pair.get('exm', [])) != 1 or len(pair.get('ass', [])) != 1:
            results.append({"standard": standard, "year": year, "status": "waiting", "detail": "Requires exactly one paper and one matching schedule"})
            continue
        paper_id, paper_name = pair['exm'][0]
        schedule_id, schedule_name = pair['ass'][0]
        with connect() as db:
            if not db.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s))", (str(paper_id),)).fetchone()[0]:
                continue
            prior = db.execute("SELECT status, detail FROM paper_import_runs WHERE paper_id=%s AND schedule_id=%s AND parser_version=6", (paper_id, schedule_id)).fetchone()
            if prior and prior[0] == 'imported':
                results.append({"standard": standard, "year": year, "status": prior[0], "detail": prior[1]})
                continue
            if not db.execute("SELECT 1 FROM topic_standards WHERE topic_id=%s AND standard_number=%s", (topic_id, standard)).fetchone():
                results.append({"standard": standard, "year": year, "status": "waiting", "detail": "Standard is not linked to this topic"})
                continue
            root = userspace.upload_root()
            try:
                parsed = parse_pair(root / str(paper_id), root / str(schedule_id), ocr=True, filenames=(paper_name, schedule_name))
                warnings = parsed['warnings']
                status = 'needs_attention' if warnings else 'imported'
                detail = '; '.join(warnings)
                if not warnings:
                    import fitz
                    with fitz.open(root / str(schedule_id)) as schedule:
                        for page_index, page in enumerate(schedule):
                            boundaries = cut_scores(page.get_text(sort=True))
                            if boundaries:
                                db.execute("""INSERT INTO exam_grade_rules
                                    (standard_number,year,schedule_resource_id,page,achieved,merit,excellence,total,quote)
                                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                                    (standard, year, schedule_id, page_index + 1, boundaries['achieved'], boundaries['merit'], boundaries['excellence'], boundaries['total'], boundaries['quote']))
                    for q in parsed['questions']:
                        # A re-read refreshes the parts (their wording and diagram positions). A question already in an exam only
                        # takes it when it has the same labelled parts, so saved answers still line up; the restored
                        # maths for the old wording is dropped so it is read again.
                        labels = [part.get('label') for part in q['parts']]
                        for question_id, old_parts, used in db.execute("""SELECT id, parts, EXISTS (SELECT 1 FROM exam_items WHERE question_id=exam_questions.id)
                                FROM exam_questions WHERE paper_resource_id=%s AND question_number=%s AND source='pdf-layout'""",
                                                                    (paper_id, q['question_number'])).fetchall():
                            if used and [part.get('label') for part in (old_parts or [])] != labels:
                                continue
                            db.execute("UPDATE exam_questions SET parts=%s::jsonb, math_state='', math_display=NULL WHERE id=%s",
                                       (json.dumps(q['parts']), question_id))
                        db.execute("""INSERT INTO exam_questions
                            (topic_id,standard_number,year,question_number,paper_resource_id,paper_page,
                             schedule_resource_id,schedule_page,marks,parts,question_text,schedule_text,figure_pages,source,verified_at)
                            SELECT %s,%s,%s,%s,%s,%s,%s,%s,0,%s::jsonb,%s,%s,%s::jsonb,'pdf-layout',NULL
                            WHERE NOT EXISTS (SELECT 1 FROM exam_questions WHERE paper_resource_id=%s AND question_number=%s)""",
                            (topic_id, standard, year, q['question_number'], paper_id, q['paper_page'], schedule_id,
                             q['schedule_page'], json.dumps(q['parts']), q['question_text'], q['schedule_text'],
                             json.dumps(q['pages']), paper_id, q['question_number']))
            except (OSError, RuntimeError, ValueError) as exc:
                status, detail = 'needs_attention', type(exc).__name__ + ': PDF could not be parsed safely'
            db.execute("""INSERT INTO paper_import_runs (paper_id,schedule_id,status,detail,parser_version) VALUES (%s,%s,%s,%s,6)
                ON CONFLICT (paper_id) DO UPDATE SET schedule_id=EXCLUDED.schedule_id,status=EXCLUDED.status,
                detail=EXCLUDED.detail,parser_version=6,updated_at=now()""", (paper_id, schedule_id, status, detail))
            results.append({"standard": standard, "year": year, "status": status, "detail": detail})
    return results


def backfill_cut_scores(connect):
    """Scan every imported schedule for cut-score tables and insert missing rules.

    Safe to run multiple times; ON CONFLICT DO NOTHING skips already-extracted rows.
    Returns a list of {standard, year, status} dicts.
    """
    import fitz
    root = userspace.upload_root()
    with connect() as db:
        rows = db.execute("""
            SELECT DISTINCT q.standard_number, q.year, q.schedule_resource_id, r.filename
            FROM exam_questions q
            JOIN resources r ON r.id = q.schedule_resource_id
            WHERE q.source = 'pdf-layout'
            ORDER BY q.standard_number, q.year
        """).fetchall()
    results = []
    for standard, year, schedule_id, filename in rows:
        path = root / str(schedule_id)
        if not path.is_file():
            results.append({"standard": standard, "year": year, "status": "missing_file"})
            continue
        found = False
        try:
            with fitz.open(path) as doc:
                for page_index, page in enumerate(doc):
                    boundaries = cut_scores(page.get_text(sort=True))
                    if boundaries:
                        with connect() as db:
                            db.execute("""INSERT INTO exam_grade_rules
                                (standard_number,year,schedule_resource_id,page,achieved,merit,excellence,total,quote)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                                (standard, year, schedule_id, page_index + 1,
                                 boundaries['achieved'], boundaries['merit'],
                                 boundaries['excellence'], boundaries['total'], boundaries['quote']))
                        found = True
                        break
        except Exception as exc:
            results.append({"standard": standard, "year": year, "status": "error", "detail": str(exc)[:200]})
            continue
        results.append({"standard": standard, "year": year,
                        "status": "extracted" if found else "not_found"})
    return results
