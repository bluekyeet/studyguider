"""Drawings in answers: stored per account, served back, and sent to the marker as an image beside the text."""
import io
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

import answer_media
from answer_media import composite, for_marker, media_router, model_mark, refs


def png(colour="white", size=(80, 50)):
    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, format="PNG")
    return out.getvalue()


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.row


class Images:
    """answer_images in memory, keyed by content hash as the real table is."""
    def __init__(self):
        self.rows = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=()):
        if sql.lstrip().startswith("INSERT INTO answer_images"):
            digest, data, drawing = params
            existing = next((i for i, row in self.rows.items() if row[0] == digest), None)
            image_id = existing or len(self.rows) + 1
            self.rows[image_id] = (digest, data, json.loads(drawing))
            return Result((image_id,))
        if "SELECT image FROM answer_images" in sql:
            row = self.rows.get(params[0])
            return Result((row[1],) if row else None)
        if "SELECT drawing FROM answer_images" in sql:
            row = self.rows.get(params[0])
            return Result((row[2],) if row else None)
        if "WHERE id = ANY" in sql:
            return Result([(i, self.rows[i][1]) for i in params[0] if i in self.rows])
        if "FROM lessons l" in sql:
            return Result(("## Your Turn 1\nSketch y = x^2.", [{"page": 1, "content": "Parabolas"}], "Mathematics"))
        raise AssertionError(sql)


def client(db, model_reply=None, vision=None):
    app = FastAPI()
    app.include_router(media_router(lambda: db, lambda: None, model_reply, vision))
    return TestClient(app)


def test_a_drawing_is_stored_once_and_served_back_with_its_strokes():
    db = Images()
    api = client(db)
    strokes = {"kind": "drawing", "items": [{"t": "line", "p": [[1, 2], [3, 4]]}]}
    first = api.post("/answer-images", files={"image": ("d.png", png(), "image/png")}, data={"drawing": json.dumps(strokes)})
    again = api.post("/answer-images", files={"image": ("d.png", png(), "image/png")}, data={"drawing": json.dumps(strokes)})
    assert first.status_code == 201 and first.json() == again.json() == {"id": 1, "url": "/answer-images/1"}
    shown = api.get("/answer-images/1")
    assert shown.headers["content-type"] == "image/png" and shown.content == png()
    assert api.get("/answer-images/1/drawing").json() == strokes
    assert api.get("/answer-images/9").status_code == 404


def test_uploads_must_be_png_with_object_strokes():
    api = client(Images())
    jpeg = io.BytesIO(); Image.new("RGB", (10, 10)).save(jpeg, format="JPEG")
    assert api.post("/answer-images", files={"image": ("d.jpg", jpeg.getvalue(), "image/jpeg")}).status_code == 422
    assert api.post("/answer-images", files={"image": ("d.png", png(), "image/png")}, data={"drawing": "[1]"}).status_code == 422
    assert api.post("/answer-images", files={"image": ("d.png", b"x" * (answer_media.MAX_IMAGE_BYTES + 1), "image/png")}).status_code == 413


def test_the_marker_reads_panels_in_place_of_image_links():
    answer = '| a | b |\n| --- | --- |\n| 1 | 2 |\n\n![Drawing 1](/answer-images/4)\n\n![Graph 2](/answer-images/7)\nGraph 2: x-axis "t"'
    assert refs(answer) == [("Drawing 1", 4), ("Graph 2", 7)]
    marked = for_marker(answer)
    assert "[Drawing 1: see image panel 1]" in marked and "[Graph 2: see image panel 2]" in marked
    assert "| 1 | 2 |" in marked and "/answer-images/" not in marked
    # Only this app's own image links count; an outside picture stays text.
    assert refs("![x](https://example.com/a.png)") == []


def test_drawings_are_stacked_into_one_captioned_image():
    sheet = Image.open(io.BytesIO(composite([("Drawing 1", png("red")), ("Graph 2", png("blue", (300, 200)))])))
    assert sheet.format == "PNG" and sheet.height > 50 + 200
    assert composite([]) is None and composite([("Drawing 1", b"not an image")]) is None


def test_an_answer_with_a_drawing_goes_to_the_vision_model_and_one_without_does_not():
    calls = []
    reply = lambda model, messages, task: calls.append(("text", task)) or "text reply"
    vision = lambda model, prompt, image, task: calls.append(("vision", task, prompt, image)) or "vision reply"
    messages = [{"role": "system", "content": "Mark it."}, {"role": "user", "content": '{"answer": "x"}'}]
    assert model_mark(reply, vision, "education", messages, "review-mark", None) == "text reply"
    assert model_mark(reply, vision, "education", messages, "review-mark", b"png") == "vision reply"
    assert calls[1][2] == 'Mark it.\n\n{"answer": "x"}' and calls[1][3] == b"png"


def test_a_lesson_answer_with_a_graph_is_checked_with_its_image():
    db = Images()
    db.rows[3] = ("h", png(), {})
    seen = {}

    def vision(model, prompt, image, task):
        seen.update(prompt=prompt, image=image, task=task)
        return "Partly correct: the intercepts are right."
    api = client(db, model_reply=lambda *a, **k: "no image", vision=vision)
    result = api.post("/lessons/1/check", json={"question": "Sketch y = x^2.", "answer": "![Graph 1](/answer-images/3)\nGraph 1: x-axis"}).json()
    assert result["feedback"] == "Partly correct: the intercepts are right."
    assert seen["task"] == "lesson-answer-check" and "[Graph 1: see image panel 1]" in seen["prompt"]
    assert answer_media.GUIDANCE[:40] in seen["prompt"]
    assert Image.open(io.BytesIO(seen["image"])).format == "PNG"


def test_answer_forms_for_lesson_wording():
    forms = client(Images()).post("/answer-forms", json={"question": "Sketch the graph of y = x^2 on the axes."}).json()["answer_forms"]
    assert [f["kind"] for f in forms] == ["graph", "text"]
