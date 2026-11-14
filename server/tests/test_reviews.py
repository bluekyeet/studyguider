import json
import unittest
from datetime import date, datetime, timedelta, timezone

from pydantic import ValidationError

import review_plan
from reviews import ReviewAnswer, ReviewQuestion, review_router


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
                           "Cells", "Biology", 91164, None, None))
        if "SELECT question FROM review_questions" in sql:
            return Result(("What is osmosis?",))
        if "INSERT INTO review_answers" in sql:
            self.answers.append(params)
            return Result((42, self.timestamp))
        if "SELECT mastery, status FROM topics" in sql:
            return Result((0.91, "secure"))
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
            return Result([])

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
    db.graded = []

    def record(database, question_id, grade, now):
        # The scheduling itself is tested against the FSRS maths in test_fsrs.py and on PostgreSQL in review_plan_check.py.
        db.graded.append((question_id, grade))
        days = 1 if grade == 1 else 16
        return {"grade": grade, "retrievability_before": None, "elapsed_days": None, "next_due": date.today() + timedelta(days=days),
                "interval_days": days, "stability": 2.3, "relearn": grade == 1, "exam": None}
    db.restore = review_plan.record_review
    review_plan.record_review = record
    return db, calls, endpoint


class ReviewTests(unittest.TestCase):
    def tearDown(self):
        if getattr(self, "db", None) is not None:
            review_plan.record_review = self.db.restore

    def test_answer_is_ai_marked_and_rescheduled(self):
        db, calls, endpoint = make_router()
        self.db = db
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
        self.assertEqual(db.graded, [(7, 3)])        # right, confidence 4: Good
        self.assertFalse(result["relearn"])
        self.assertEqual(db.answers[0][9], 3)       # the grade is kept with the answer

    def test_wrong_answer_returns_tomorrow(self):
        db, calls, endpoint = make_router(reply=json.dumps(
            {"correct": False, "feedback": "No, that is not diffusion.", "concept": "osmosis"}))
        self.db = db
        result = endpoint(7, ReviewAnswer(answer="active transport", confidence=5))
        self.assertEqual(result["correct"], False)
        self.assertEqual(result["interval_days"], 1)
        self.assertEqual(db.graded, [(7, 1)])
        self.assertTrue(result["relearn"] and result["confident_miss"])     # asked again this session; a confident miss
        self.assertEqual(result["outcome"], "incorrect")
        self.assertEqual(db.answers[0][3], False)

    def test_invalid_mark_falls_back_to_confidence(self):
        db, calls, endpoint = make_router(reply="not json")
        self.db = db
        result = endpoint(7, ReviewAnswer(answer="something", confidence=4))
        self.assertEqual(db.graded, [(7, 3)])       # unmarked: confidence alone, never Easy
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
        self.assertEqual(len(router.routes), 8)
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
                return Result([(1, [{"kind": "graph"}], "Physics", 2), (2, None, "Physics", 0)])
            self.calls.append(params)
            return Result([(1, 2, "Now?", date(2026, 11, 3), "force", None, 0.5, 1, 2, None, 2, "concept"),
                           (2, 2, "Later?", date(2026, 12, 1), "", 91171, 0.0, 0, 0, None, 0, "fact")])

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


class PlanDb:
    """Answers the daily plan's queries: due rows, answered questions (for repeats), and no assessments or settings."""
    def __init__(self, due, answered=()):
        self.due, self.answered, self.sql = due, list(answered), []

    def execute(self, sql, params=()):
        self.sql.append(sql)
        if "q.exam_origin, q.stability" in sql:
            return Result(self.due)
        if "WHERE q.reps > 0" in sql and "q.exam_origin" in sql:
            return Result(self.answered)
        if "FROM settings" in sql:
            return Result(None)
        return Result([])


def due_row(id, topic, question, concept="", origin="", reps=0, stability=None, material="concept"):
    # (id, topic, question, due, concept, standard, mastery, topic name, origin, stability, last review, reps, material, expected, subject)
    last = datetime(2026, 11, 1, tzinfo=timezone.utc) if reps else None
    return (id, topic, question, date(2026, 11, 2), concept, None, 0, "E", origin, stability, last, reps, material, "", "Chemistry")


def test_new_questions_that_repeat_an_answered_one_are_left_out():
    from reviews import due_list
    due = [due_row(1, 7, "What is the magnitude of the electrical force on a charge of $2$ C in a field?"),
           due_row(2, 7, "Explain why alkanes are saturated."),
           due_row(3, 7, "Explain why alkanes are saturated!", origin="pack:3:0.1"),
           due_row(4, 7, "Ethanol burns. Complete the table below.", origin="49:28:c(i)"),
           due_row(5, 7, "Ethanol burns. Explain the high melting point of palladium.", origin="49:28:c(ii)"),
           due_row(6, 8, "Explain why alkanes are saturated.")]
    answered = [(7, "What is the magnitude of the electrical force experienced by a charge of $5$ C in a field?", "")]
    rows, info = due_list(PlanDb(due, answered), date(2026, 11, 2), datetime(2026, 11, 2, tzinfo=timezone.utc))
    assert sorted(row["id"] for row in rows) == [2, 4, 5, 6]     # near-repeats go; exam parts and other topics stay
    assert info["left_out"] == 0


def test_answered_questions_come_back_when_due():
    from reviews import due_list
    due = [due_row(1, 7, "Define osmosis.", reps=2, stability=3.0, material="fact"), due_row(2, 7, "Explain diffusion.")]
    rows, _ = due_list(PlanDb(due), date(2026, 11, 9), datetime(2026, 11, 9, tzinfo=timezone.utc))
    assert [row["id"] for row in rows] == [1, 2]
    assert 0 < rows[0]["recall"] < 0.9          # eight days after a review with stability 3: partly forgotten


def test_review_skips_paperwork_questions():
    from reviews import due_list, is_admin_question
    assert is_admin_question("How many credits is this standard worth?", "NCEA assessment criteria")
    assert is_admin_question("Which grades can you get?", "")
    assert is_admin_question("Solve the equation.", "NCEA Level 2 Standard 91261 details")
    assert not is_admin_question("Solve $x^2 = 9$.", "quadratics")
    db = PlanDb([due_row(1, 7, "How many credits is this standard worth?", "NCEA assessment criteria"),
                 due_row(2, 7, "Solve $x^2 = 9$.", "quadratics")])
    rows, _ = due_list(db, date(2026, 11, 2), datetime(2026, 11, 2, tzinfo=timezone.utc))
    assert [row["id"] for row in rows] == [2]
    assert any("q.exam_origin, q.stability" in sql and "NOT sw.active" in sql for sql in db.sql)   # switched-off topics are not asked


def test_study_summary_leaves_out_switched_off_topics():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    class Db:
        sql = []

        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()):
            self.sql.append(sql)
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
