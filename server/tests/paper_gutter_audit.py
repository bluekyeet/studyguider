"""Audit all registered source-backed papers; optionally repair gutter-only changes.

Get-Content server/tests/paper_gutter_audit.py -Raw | docker compose exec -T api python -
Set REPAIR_PAPER_GUTTERS=yes for backed-up repairs. Backups stay in private uploads.
Never changes answers, marks, schedules, human-review flags or original PDFs.
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import fitz
from app import connect
from paper_parser import parse_pair

root = Path(os.environ.get('UPLOAD_DIR', '/data/uploads'))
apply = os.environ.get('REPAIR_PAPER_GUTTERS') == 'yes'
groups = defaultdict(list)
with connect() as db:
    db.execute('SET TRANSACTION READ ONLY')
    rows = db.execute("""SELECT q.id,q.standard_number,q.year,q.question_number,q.paper_resource_id,
        q.schedule_resource_id,q.question_text,q.parts,p.filename,s.filename,q.source
        FROM exam_questions q JOIN resources p ON p.id=q.paper_resource_id
        JOIN resources s ON s.id=q.schedule_resource_id WHERE q.source<>'ai'
        ORDER BY q.standard_number,q.year,q.id""").fetchall()
for row in rows:
    groups[row[4], row[5]].append(row)

repairs = []
skipped = []
for (paper, schedule), items in groups.items():
    standard, year = items[0][1:3]
    try:
        # Identify actual PDF gutter text, rather than guessing from letter patterns.
        with fitz.open(root / str(paper)) as doc:
            gutter_lines = sum(1 for page in doc for block in page.get_text('dict')['blocks']
                for line in block.get('lines', [])
                if (line['bbox'][2] <= 40 or line['bbox'][0] >= page.rect.width-40)
                and line['bbox'][1] >= 30 and line['bbox'][3] <= page.rect.height-28)
        if gutter_lines < 100:
            print(json.dumps({'standard': standard, 'year': year, 'status': 'no_patterned_gutter', 'gutter_lines': gutter_lines}))
            continue
        parsed = parse_pair(root / str(paper), root / str(schedule), filenames=(items[0][8], items[0][9]))
        if parsed['warnings']:
            raise ValueError('Parser warnings; manual inspection required')
        questions = {q['question_number']: q for q in parsed['questions']}
        changed = 0
        for row in items:
            q = questions.get(row[3])
            if q is None:
                raise ValueError('Stored question number not found in new parse')
            old = row[6] or ''
            new = q['question_text']
            if old == new:
                continue
            if row[10] != 'pdf-layout':
                raise ValueError('Non-layout source differs; preserve manual text')
            if len(new) < 100 or len(new) >= len(old):
                raise ValueError('Change is not a conservative gutter-text reduction')
            # All surviving physical lines must exist in the stored extraction.
            if any(line.strip() not in old for line in new.splitlines() if line.strip()):
                raise ValueError('New extraction adds text; not a gutter-only repair')
            repairs.append((row, q))
            changed += 1
        print(json.dumps({'standard': standard, 'year': year, 'status': 'repairable' if changed else 'already_clean', 'changed_questions': changed, 'gutter_lines': gutter_lines}))
    except (OSError, RuntimeError, ValueError) as exc:
        # Do not partially repair a paper whose layout changed unexpectedly.
        repairs = [(row, q) for row, q in repairs if (row[4], row[5]) != (paper, schedule)]
        skipped.append({'standard': standard, 'year': year, 'reason': str(exc)[:200]})
        print(json.dumps({'standard': standard, 'year': year, 'status': 'needs_inspection', 'reason': str(exc)[:200]}))

if apply and repairs:
    directory = root / 'parser-repair-backups'
    directory.mkdir(exist_ok=True)
    backup = directory / ('all-papers-gutters-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    with backup.open('x', encoding='utf-8') as out:
        json.dump([row for row, _ in repairs], out, default=str)
    with connect() as db:
        for row, q in repairs:
            result = db.execute("""UPDATE exam_questions SET question_text=%s,parts=%s::jsonb
                WHERE id=%s AND question_text=%s AND parts=%s::jsonb RETURNING id""",
                (q['question_text'], json.dumps(q['parts']), row[0], row[6], json.dumps(row[7]))).fetchone()
            if not result:
                raise RuntimeError('Question changed during audit; entire repair transaction rolled back')
    print('PRIVATE_BACKUP', str(backup))
print('SUMMARY', json.dumps({'paper_schedule_pairs': len(groups), 'registered_questions': len(rows),
    'repairable_questions': len(repairs), 'applied': apply, 'needs_inspection': skipped}))
