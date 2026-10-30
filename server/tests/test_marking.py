import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from marking import marking_router


ROW = ("My answer", "1(a)", 12345, 2024, "paper-id", 2,
       "Question 1(a): Explain.", "schedule-id", 3, "Achieved: explains the idea.")


def make_client(row=ROW, reply=None, auth=None):
    calls = []

    class DB:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params):
            calls.append((sql, params))
            return self

        def fetchone(self):
            return row

    def model(model_name, messages):
        calls.append((model_name, messages))
        return reply if reply is not None else json.dumps({
            "outcome": "achieved", "feedback": "Your explanation addresses the idea.",
            "evidence": [{"quote": "explains the idea", "explanation": "Relevant criterion."}]})

    app = FastAPI()
    app.include_router(marking_router(DB, auth or (lambda: None), model))
    return TestClient(app), calls


def test_feedback_uses_actual_pages_and_answer():
    client, calls = make_client()
    response = client.post('/exams/1/answers/2/feedback')
    assert response.status_code == 200
    assert response.json()['experimental'] is True
    assert response.json()['schedule']['page'] == 3
    assert calls[0][1] == (1, 2)
    assert 'resource_pages schedule' in calls[0][0]
    payload = json.loads(calls[1][1][1]['content'])
    assert payload['schedule_page_text'] == ROW[9]
    assert payload['paper_page_text'] == ROW[6]
    assert payload['answer'] == ROW[0]


def test_missing_item_answer_or_pages_do_not_call_model():
    for row, status in [(None, 404), ((None,) + ROW[1:], 422),
                        (ROW[:6] + (None,) + ROW[7:], 422),
                        (ROW[:9] + ('',), 422)]:
        client, calls = make_client(row=row)
        assert client.post('/exams/1/answers/2/feedback').status_code == status
        assert len(calls) == 1


def test_invalid_model_outputs_are_rejected():
    outputs = ['not json', json.dumps({'outcome': 'achieved', 'feedback': 'ok',
               'evidence': [{'quote': 'invented', 'explanation': 'x'}]}),
               json.dumps({'outcome': 'verified', 'feedback': 'ok', 'evidence': []}),
               json.dumps({'outcome': 'uncertain', 'feedback': 'ok', 'evidence': [], 'verified': True})]
    for output in outputs:
        client, _ = make_client(reply=output)
        assert client.post('/exams/1/answers/2/feedback').status_code == 502


def test_authentication_is_required():
    def deny():
        raise HTTPException(401, 'Authentication required')
    client, calls = make_client(auth=deny)
    assert client.post('/exams/1/answers/2/feedback').status_code == 401
    assert not calls


def test_second_review_and_override_are_advisory_and_unsaved():
    client, calls = make_client()
    response = client.post('/exams/1/answers/2/feedback', json={
        'second_review': True, 'self_override': 'merit'})
    assert response.status_code == 200
    result = response.json()
    assert result['outcome'] == 'achieved'
    assert result['second_review']['outcome'] == 'achieved'
    assert 'not verified' in result['second_review_disclaimer']
    assert result['self_override'] == 'merit'
    assert 'not saved' in result['self_override_disclaimer']
    assert json.loads(calls[2][1][1]['content'])['prior_ai_feedback']['outcome'] == 'achieved'
    assert calls[2][0] == 'education-reviewer'
    assert len(calls) == 3 and calls[0][0].lstrip().startswith('SELECT')


def test_second_review_rejects_invented_evidence_and_invalid_requests():
    client, calls = make_client()
    assert client.post('/exams/1/answers/2/feedback', json={'self_override': 'official'}).status_code == 422
    assert not calls

    valid = json.dumps({'outcome': 'achieved', 'feedback': 'ok', 'evidence': [
        {'quote': 'explains the idea', 'explanation': 'criterion'}]})
    invalid = valid.replace('explains the idea', 'invented')
    replies = iter([valid, invalid])
    # Replace the model through a fresh router so only the second response is invalid.
    class DB:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *args): return self
        def fetchone(self): return ROW
    app = FastAPI()
    app.include_router(marking_router(DB, lambda: None, lambda *args: next(replies)))
    assert TestClient(app).post('/exams/1/answers/2/feedback', json={'second_review': True}).status_code == 502
