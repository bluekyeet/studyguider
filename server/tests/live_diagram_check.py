"""Opt-in live diagram generation/review; rollback-only rows and temporary files.

Get-Content server/tests/live_diagram_check.py -Raw |
  docker compose exec -T -e RUN_LIVE_DIAGRAM_CHECK=yes api python -
Real gateway calls remain in usage accounting; no human visual approval implied.
"""
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from app import connect, model_reply, model_reply_vision
from diagrams import DiagramRequest, diagram_router

assert os.environ.get("RUN_LIVE_DIAGRAM_CHECK") == "yes"
db = connect()


@contextmanager
def connection():
    yield db


calls = []


def teacher(model, messages, task):
    calls.append(task)
    return model_reply(model, messages, task="acceptance-" + task)


def reviewer(model, prompt, image, task):
    calls.append(task)
    return model_reply_vision(model, prompt, image, task="acceptance-" + task)


original_upload_dir = os.environ.get("UPLOAD_DIR")
try:
    with tempfile.TemporaryDirectory(prefix="studyguider-diagram-check-") as directory:
        os.environ["UPLOAD_DIR"] = directory
        subject = db.execute("INSERT INTO subjects(name,level) VALUES ('Disposable diagram check',2) RETURNING id").fetchone()[0]
        topic = db.execute("INSERT INTO topics(subject_id,name) VALUES (%s,'Synthetic wave') RETURNING id", (subject,)).fetchone()[0]
        evidence = "For a transverse wave, wavelength is the horizontal distance between adjacent crests. Amplitude is the vertical distance from equilibrium to a crest. Draw only one wavelength arrow and one amplitude arrow with these labels; no numbers."
        sources = [{"resource_id": "synthetic-wave", "page": 1, "content": evidence}]
        lesson = db.execute("""INSERT INTO lessons(topic_id,query,lesson,review_status,sources,standards)
            VALUES (%s,'Wave diagram',%s,'flagged',%s::jsonb,'[]') RETURNING id""", (topic, evidence, json.dumps(sources))).fetchone()[0]
        router = diagram_router(connection, lambda: None, teacher, reviewer)
        generate = next(r.endpoint for r in router.routes if r.path == '/topics/{topic_id}/diagrams' and 'POST' in r.methods)
        result = generate(topic, DiagramRequest(lesson_id=lesson, description=evidence))
        print("CALLS", calls, flush=True)
        print("RESULT", result['status'], "REVIEW", result['review'], flush=True)
        assert result['image_path'], "No rendered image"
        image = (Path(directory) / result['image_path']).read_bytes()
        assert image.startswith(b'\x89PNG\r\n\x1a\n')
        print("PNG_BYTES", len(image), flush=True)
        assert result['status'] == 'passed', "Diagram did not pass independent AI review; do not claim visual correctness"
        print("PASS: live source-grounded SVG rendered and independently AI-reviewed; human visual correctness unverified")
finally:
    if original_upload_dir is None:
        os.environ.pop("UPLOAD_DIR", None)
    else:
        os.environ["UPLOAD_DIR"] = original_upload_dir
    db.rollback()
    db.close()
    print("CLEANUP: temporary images removed, synthetic rows rolled back; sequence gaps may remain")
