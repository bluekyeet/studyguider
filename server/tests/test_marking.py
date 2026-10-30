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
