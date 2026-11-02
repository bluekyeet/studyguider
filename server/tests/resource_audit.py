"""Read-only metadata audit; no paper text or credentials printed.

Get-Content server/tests/resource_audit.py -Raw | docker compose exec -T api python -
Checks ownership/linkage, not scientific accuracy or human approval.
"""
import json

from app import connect
from paper_parser import file_identity

standards = (91170, 91171, 91173, 91164, 91165, 91166)
problems = []
with connect() as db:
    db.execute("SET TRANSACTION READ ONLY")
    for standard in standards:
        topics = [row[0] for row in db.execute('SELECT topic_id FROM topic_standards WHERE standard_number=%s', (standard,)).fetchall()]
        chunks = db.execute('''SELECT c.id,c.topic_id,c.standard_number,r.topic_id
            FROM resource_chunks c JOIN resources r ON r.id=c.resource_id
            WHERE c.topic_id=ANY(%s) ORDER BY c.id LIMIT 10''', (topics,)).fetchall()
        questions = db.execute('''SELECT q.id,q.topic_id,q.standard_number,q.year,p.topic_id,p.filename,s.topic_id,s.filename,q.verified_at
            FROM exam_questions q JOIN resources p ON p.id=q.paper_resource_id
            JOIN resources s ON s.id=q.schedule_resource_id
            WHERE q.standard_number=%s AND q.source<>'ai' ORDER BY q.id LIMIT 10''', (standard,)).fetchall()
        for ident, topic, tagged, owner in chunks:
            if topic != owner or (tagged is not None and tagged != standard):
                problems.append({'kind': 'chunk', 'id': ident, 'standard': standard})
        for ident, topic, tagged, year, paper_topic, paper_name, schedule_topic, schedule_name, verified in questions:
            paper = file_identity(paper_name)
            schedule = file_identity(schedule_name)
            if (topic not in topics or paper_topic != topic or schedule_topic != topic
                    or (paper and paper != (tagged, year, 'exm'))
                    or (schedule and schedule != (tagged, year, 'ass'))):
                problems.append({'kind': 'question', 'id': ident, 'standard': standard})
        counts = db.execute('''SELECT count(*),count(*) FILTER (WHERE verified_at IS NOT NULL),max(year)
            FROM exam_questions WHERE standard_number=%s AND source<>'ai' ''', (standard,)).fetchone()
        print(json.dumps({'standard': standard, 'linked_topics': len(topics), 'chunks_sampled': len(chunks),
                          'questions_sampled': len(questions), 'registered_real_questions': counts[0],
                          'human_review_timestamp_present': counts[1], 'latest_real_year': counts[2]}))
        if len(chunks) < 10 or len(questions) < 10:
            problems.append({'kind': 'sample_shortfall', 'standard': standard})
print('PROBLEMS', json.dumps(problems))
assert not problems, 'Metadata audit found mismatches or insufficient samples; inspect before claiming acceptance'
print('PASS: sampled topic/resource/standard metadata consistent; original wording and human review NOT checked')
