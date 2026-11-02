"""Opt-in live explanation/follow-up and exact note save, rollback-only study data.

Get-Content server/tests/live_explain_check.py -Raw |
  docker compose exec -T -e RUN_LIVE_EXPLAIN_CHECK=yes api python -
Two real streamed calls remain in usage accounting. No Android UI coverage.
"""
import asyncio
import json
import os
from contextlib import contextmanager

import app
from explain import ExplainRequest, ExplainTurn, explain_router

assert os.environ.get("RUN_LIVE_EXPLAIN_CHECK") == "yes"
db = app.connect()


@contextmanager
def connection():
    yield db


async def collect(response):
    text = []
    done = False
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode()
        for line in chunk.splitlines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:])
            assert "error" not in event, event
            if "text" in event:
                text.append(event["text"])
            done = done or event.get("done", False)
    assert done and text, "Missing completion or empty explanation"
    return "".join(text)


try:
    subject = db.execute("INSERT INTO subjects(name,level) VALUES ('Disposable Explain check',2) RETURNING id").fetchone()[0]
    topic = db.execute("INSERT INTO topics(subject_id,name) VALUES (%s,'Synthetic concentration') RETURNING id", (subject,)).fetchone()[0]
    focus = "At constant temperature, higher concentration means more reactant particles per unit volume, increasing collision frequency. It does not change average kinetic energy."
    source = [{"resource_id": "synthetic-explain", "filename": "synthetic.txt", "page": 1, "content": focus}]
    lesson = db.execute("""INSERT INTO lessons(topic_id,query,lesson,review_status,sources,standards)
        VALUES (%s,'Reaction rates',%s,'flagged',%s::jsonb,'[]') RETURNING id""", (topic, focus, json.dumps(source))).fetchone()[0]
    seen = []

    def stream(model, messages, task):
        payload = json.loads(messages[-1]["content"])
        assert payload["paragraph_in_focus"] == focus
        assert payload["sources"] == source
        seen.append(payload)
        return app.model_reply_stream(model, messages, task="acceptance-explain-followup")

    router = explain_router(connection, lambda: None, app.model_reply, stream)
    explain = next(route.endpoint for route in router.routes if route.path == '/lessons/{lesson_id}/explain')
    first_question = "Explain how concentration affects reaction rate at constant temperature."
    first = asyncio.run(collect(explain(lesson, ExplainRequest(question=first_question, paragraph=focus), stream=True)))
    second = asyncio.run(collect(explain(lesson, ExplainRequest(question="Why does that not mean the particles move faster?", paragraph=focus,
        history=[ExplainTurn(question=first_question, answer=first[:8000])]), stream=True)))
    assert seen[1]["conversation_history"][0]["answer"] == first[:8000]
    note_text = f"Lesson {lesson}\n\n{second}\n\nAI-generated explanation; not verified."
    original_connect = app.connect
    app.connect = connection
    try:
        note = app.create_note(topic, app.Note(content=note_text))
    finally:
        app.connect = original_connect
    assert db.execute('SELECT content FROM notes WHERE id=%s AND topic_id=%s', (note['id'], topic)).fetchone()[0] == note_text
    print('FIRST_REPLY', first)
    print('FOLLOW_UP_REPLY', second)
    print('PASS: actual Explain route receives focus/evidence/history, both streams finish normally, exact reply saved to topic notes')
finally:
    db.rollback()
    db.close()
    print('ROLLBACK: synthetic lesson/note records discarded; sequence gaps may remain')
