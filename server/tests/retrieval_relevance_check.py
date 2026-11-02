"""Read-only top-five concept coverage probe; no source text printed.

Get-Content server/tests/retrieval_relevance_check.py -Raw |
  docker compose exec -T api python -
Keyword coverage is a reproducible proxy, not human relevance grading.
"""
import json
import re

from app import connect, search_resources

cases = [
    (91170, 'waves closer together', [r'wavelength', r'frequency|speed']),
    (91171, 'how hard to change motion', [r'momentum|inertia', r'force|mass']),
    (91173, 'charge pushed between plates', [r'electric field', r'force|charge']),
    (91164, 'why molecules stick together', [r'intermolecular|hydrogen bond|van der waals', r'force|attract']),
    (91165, 'carbon double bond reaction', [r'alkene|double bond', r'addition|bromine']),
    (91166, 'more particles bump into each other', [r'collision', r'concentration|reaction rate|rate of reaction']),
]
passed = 0
for standard, query, concepts in cases:
    with connect() as db:
        topics = db.execute('SELECT topic_id FROM topic_standards WHERE standard_number=%s', (standard,)).fetchall()
    assert len(topics) == 1, 'Probe requires one explicit topic per standard'
    topic = topics[0][0]
    rows = search_resources(topic, query)[:5]
    with connect() as db:
        owners = db.execute('SELECT DISTINCT topic_id FROM resources WHERE id=ANY(%s::uuid[])',
                            ([row['resource_id'] for row in rows],)).fetchall()
    assert all(owner[0] == topic for owner in owners)
    hits = [index + 1 for index, row in enumerate(rows)
            if all(re.search(pattern, row['content'], re.I) for pattern in concepts)]
    passed += bool(hits)
    print(json.dumps({'standard': standard, 'query': query, 'top_five_results': len(rows),
                      'concept_coverage_ranks': hits, 'topic_isolated': True}))
print(f'CONCEPT_COVERAGE {passed}/{len(cases)}; proxy only, not human or semantic relevance validation')
