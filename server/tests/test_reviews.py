import json
import unittest
from datetime import date, datetime, timedelta, timezone

from pydantic import ValidationError

from reviews import ReviewAnswer, ReviewQuestion, next_interval, review_router


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.row


class Database:
    def __init__(self):
        self.timestamp = datetime(2026, 10, 31, tzinfo=timezone.utc)
        self.calls = []
        self.answers = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM review_questions q JOIN topics t" in sql:
            return Result((8, "Osmosis is diffusion of water.", [], "osmosis", 1,
                           "Cells", "Biology", 91164))
        if "SELECT question FROM review_questions" in sql:
            return Result(("What is osmosis?",))
        if "INSERT INTO review_answers" in sql:
            self.answers.append(params)
            return Result((42, self.timestamp))
        if "SELECT AVG(mastery)" in sql:
            return Result((0.25,))
        if "UPDATE review_questions" in sql or "UPDATE topics" in sql:
            return Result()
        raise AssertionError(sql)


def test_completed_lessons_automatically_get_reviews_once():
    class ReviewDatabase:
        generated = False
        inserted = []

        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()):
            if "FROM lessons" in sql:
                return Result([] if self.generated else [(1, 2, "Assistant-written lesson", [])])
            if "FROM lesson_answers" in sql:
                return Result([])
            if "INSERT INTO review_questions" in sql:
                self.inserted.append(params)
            elif "UPDATE lessons" in sql:
                self.generated = True
            elif "FROM review_questions q" in sql:
                return Result([])
            return Result()

    db = ReviewDatabase()
    model_calls = []
    def reply(*args, **kwargs):
        model_calls.append(args)
        return json.dumps([{"question": "What is force?", "expected_answer": "A push or pull.", "concept": "force"}])
    router = review_router(lambda: db, lambda: None, reply)
    due = next(route.endpoint for route in router.routes if route.path == "/review-questions/due")
    due(date.today())
    due(date.today())
    assert len(db.inserted) == 1
    assert len(model_calls) == 1
    assert "Relevant formulae" in model_calls[0][1][0]["content"]
    assert "Do not substitute values" in model_calls[0][1][0]["content"]
    assert db.inserted[0][0] == 2


def make_router(reply=None):
    db = Database()
    calls = []

    def model(model_name, messages, task="general"):
        calls.append((model_name, messages, task))
        return reply if reply is not None else json.dumps(
            {"correct": True, "feedback": "Yes, water moves by diffusion.", "concept": "osmosis"})

    router = review_router(lambda: db, lambda: None, model)
    endpoint = next(r.endpoint for r in router.routes if r.path.endswith("/answers") and "POST" in r.methods)
    return db, calls, endpoint


class ReviewTests(unittest.TestCase):
    def test_self_assessed_intervals(self):
        self.assertEqual([next_interval(0, c) for c in range(1, 6)], [1, 1, 1, 2, 4])
        self.assertEqual([next_interval(8, c) for c in range(1, 6)], [1, 1, 8, 16, 24])
        self.assertEqual(next_interval(36500, 5), 36500)
        self.assertEqual(next_interval(8, 5, correct=False), 1)
        self.assertEqual(next_interval(8, 5, correct=True), 24)

    def test_answer_is_ai_marked_and_rescheduled(self):
        db, calls, endpoint = make_router()
        result = endpoint(7, ReviewAnswer(answer=" water moves ", confidence=4))
        self.assertEqual(result["answer"], "water moves")
        self.assertEqual(result["correct"], True)
        self.assertEqual(result["outcome"], "correct")
        self.assertEqual(result["interval_days"], 16)
        self.assertEqual(result["next_due"], date.today() + timedelta(days=16))
        self.assertEqual(calls[0][0], "education")
        self.assertEqual(calls[0][2], "review-mark")
        payload = json.loads(calls[0][1][1]["content"])
        self.assertEqual(payload["expected_answer"], "Osmosis is diffusion of water.")
        self.assertIn("FOR UPDATE", db.calls[0][0])
        self.assertIn("Pacific/Auckland", db.calls[3][0])

    def test_wrong_answer_returns_tomorrow(self):
        db, calls, endpoint = make_router(reply=json.dumps(
            {"correct": False, "feedback": "No, that is not diffusion.", "concept": "osmosis"}))
        result = endpoint(7, ReviewAnswer(answer="active transport", confidence=5))
        self.assertEqual(result["correct"], False)
        self.assertEqual(result["interval_days"], 1)
        self.assertEqual(result["outcome"], "incorrect")
        self.assertEqual(db.answers[0][3], False)

    def test_invalid_mark_falls_back_to_confidence(self):
        db, calls, endpoint = make_router(reply="not json")
        result = endpoint(7, ReviewAnswer(answer="something", confidence=4))
        self.assertEqual(result["outcome"], "confidence-based")
        self.assertEqual(result["correct"], True)
        self.assertIn("unavailable", result["feedback"])

    def test_validation(self):
        self.assertEqual(ReviewQuestion(question="Why?", due_date="2026-10-31").due_date, date(2026, 10, 31))
        for values in ({"answer": " ", "confidence": 3}, {"answer": "Yes", "confidence": 0}, {"answer": "Yes", "confidence": 6}):
            with self.assertRaises(ValidationError):
                ReviewAnswer(**values)

    def test_routes_require_authentication(self):
        def authorised():
            pass

        router = review_router(None, authorised, lambda *args: "")
        self.assertEqual(len(router.routes), 7)
        self.assertTrue(all(route.dependencies[0].dependency is authorised for route in router.routes))


if __name__ == "__main__":
    unittest.main()


def test_all_questions_lists_due_and_future_questions_with_optional_topic_filter():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    class ListDatabase:
        calls = []

        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()):
            assert "review_questions q" in sql
            if "answer_forms" in sql:       # the forms each listed question needs: stored for 1, inferred for 2
                return Result([(1, [{"kind": "graph"}], "Physics"), (2, None, "Physics")])
            self.calls.append(params)
            return Result([(1, 2, "Now?", date(2026, 11, 3), "force", None, 0.5, 1, 2, None),
                           (2, 2, "Later?", date(2026, 12, 1), "", 91171, 0.0, 0, 0, None)])

    app = FastAPI()
    app.include_router(review_router(ListDatabase, lambda: None, None))
    client = TestClient(app)
    rows = client.get("/review-questions?topic_id=2").json()
    assert [r["question"] for r in rows] == ["Now?", "Later?"]
    assert rows[1]["due_date"] == "2026-12-01" and rows[0]["answer_count"] == 2
    assert [f["kind"] for f in rows[0]["answer_forms"]] == ["graph", "text"]
    assert rows[1]["answer_forms"] == [{"kind": "text", "palette": "physics"}]
    assert ListDatabase.calls[-1] == (2, 2, 200, 0)
    client.get("/review-questions")
    assert ListDatabase.calls[-1] == (None, None, 200, 0)
    assert client.get("/review-questions?limit=501").status_code == 422


def test_estimated_grade_needs_enough_answers_and_uses_fixed_bands():
    from reviews import estimate_grade
    assert estimate_grade(0.9, 4) is None
    assert [estimate_grade(m, 5) for m in (0.0, 0.39, 0.4, 0.59, 0.6, 0.79, 0.8, 1.0)] == [
        "Not achieved", "Not achieved", "Achieved", "Achieved", "Merit", "Merit", "Excellence", "Excellence"]


def test_review_only_asks_new_questions():
    from reviews import fresh_due
    # (id, topic, question, due, concept, standard, mastery, topic name, origin)
    due = [(1, 7, "What is the magnitude of the electrical force on a charge of $2$ C in a field?", None, "", None, 0, "E", ""),
           (2, 7, "Explain why alkanes are saturated.", None, "", None, 0, "E", ""),
           (3, 7, "Explain why alkanes are saturated!", None, "", None, 0, "E", "pack:3:0.1"),
           (4, 7, "Ethanol burns. Complete the table below.", None, "", None, 0, "E", "49:28:c(i)"),
           (5, 7, "Ethanol burns. Explain the high melting point of palladium.", None, "", None, 0, "E", "49:28:c(ii)"),
           (6, 8, "Explain why alkanes are saturated.", None, "", None, 0, "F", "")]
    answered = [(7, "What is the magnitude of the electrical force experienced by a charge of $5$ C in a field?", "")]

    class Db:
        def execute(self, sql, params=()):
            return Result(answered if "SELECT DISTINCT" in sql else due)
    assert [row[0] for row in fresh_due(Db(), date.today())] == [2, 4, 5, 6]     # near-repeats go; exam parts and other topics stay


def test_review_skips_paperwork_questions():
    from reviews import fresh_due, is_admin_question
    assert is_admin_question("How many credits is this standard worth?", "NCEA assessment criteria")
    assert is_admin_question("Which grades can you get?", "")
    assert is_admin_question("Solve the equation.", "NCEA Level 2 Standard 91261 details")
    assert not is_admin_question("Solve $x^2 = 9$.", "quadratics")
    due = [(1, 7, "How many credits is this standard worth?", None, "NCEA assessment criteria", None, 0, "Algebra", ""),
           (2, 7, "Solve $x^2 = 9$.", None, "quadratics", None, 0, "Algebra", "")]

    class Db:
        sql = []

        def execute(self, sql, params=()):
            self.sql.append(sql)
            return Result([] if "SELECT DISTINCT" in sql else due)
    db = Db()
    assert [row[0] for row in fresh_due(db, date.today())] == [2]
    assert "NOT sw.active" in db.sql[0]            # a topic switched off in Settings is not asked about


def test_study_summary_leaves_out_switched_off_topics():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    class Db:
        sql = []

        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()):
            self.sql.append(sql)
            if "SELECT (now()" in sql:
                return Result((date(2026, 11, 6),))
            if "FROM lessons l" in sql:
                return Result((0, 0, 0, 0))
            if "count(*) FILTER (WHERE due_date" in sql:
                return Result((0, 0, 0))
            if "SELECT q.concept, t.name" in sql:
                return Result([("NCEA assessment criteria", "Algebra", 0.0, "How many credits?"), ("Factorising", "Algebra", 0.0, "Factorise $x^2-1$.")])
            return Result([])
    db = Db()
    app = FastAPI()
    app.include_router(review_router(lambda: db, lambda: None, None))
    summary = TestClient(app).get("/study-summary").json()
    assert [c["concept"] for c in summary["weak_concepts"]] == ["Factorising"]
    checked = [sql for sql in db.sql if "FROM lessons l" in sql or "SELECT q.concept, t.name" in sql or "count(*) FILTER (WHERE due_date" in sql]
    assert len(checked) == 3 and all("NOT sw.active" in sql for sql in checked)


def test_review_photo_is_read_into_text_without_saving():
    import io
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from PIL import Image

    class Db:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()):
            assert "SELECT question FROM review_questions" in sql
            return Result(("Solve $x^2=9$.",) if params == (4,) else None)
    prompts = []

    def vision(model, prompt, image, mime="image/png", task="vision"):
        prompts.append((prompt, task, image[:4]))
        return "x = 3 or x = -3"
    app = FastAPI()
    app.include_router(review_router(lambda: Db(), lambda: None, None, vision))
    client = TestClient(app)
    picture = io.BytesIO(); Image.new("RGB", (40, 40), "white").save(picture, format="PNG")
    page = ("files", ("a.png", picture.getvalue(), "image/png"))
    reply = client.post("/review-questions/4/scan", files=[page])
    assert reply.status_code == 200 and reply.json()["transcription"] == "x = 3 or x = -3"
    assert "Solve $x^2=9$." in prompts[0][0] and prompts[0][1] == "review-handwriting" and prompts[0][2] == b"\x89PNG"
    assert client.post("/review-questions/5/scan", files=[page]).status_code == 404
    assert client.post("/review-questions/4/scan").status_code == 422
    assert client.post("/review-questions/4/scan", files=[("files", ("a.txt", b"hello", "text/plain"))]).status_code == 422
    unavailable = FastAPI(); unavailable.include_router(review_router(lambda: Db(), lambda: None, None))
    assert TestClient(unavailable).post("/review-questions/4/scan", files=[page]).status_code == 503
