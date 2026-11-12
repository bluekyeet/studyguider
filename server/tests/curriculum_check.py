"""Real PostgreSQL checks for the curriculum model and spaced review: migration of an account made before them, then a
university paper planned over several simulated days.

Run only against a disposable stack (it creates and drops its own database inside that server):
  docker compose exec -T -e DISPOSABLE_TEST_DATABASE=yes api python - < server/tests/curriculum_check.py
The pre-curriculum layout is built with the real table-creation code with the new tables and columns removed again, plus data
(an NCEA subject, a linked standard, answered and unanswered review questions, a switched-off topic).
"""
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

assert os.environ.get("DISPOSABLE_TEST_DATABASE") == "yes", "refusing to run without DISPOSABLE_TEST_DATABASE=yes"
os.environ["STUDYGUIDER_DEV_CLOCK"] = "yes"

try:
    import httpx  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--target", "/tmp/httpx_site", "httpx"], check=True)
    sys.path.insert(0, "/tmp/httpx_site")

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

BASE = os.environ["DATABASE_URL"]
DB = "curriculum_check_" + uuid.uuid4().hex[:12]
with psycopg.connect(BASE, autocommit=True) as admin_db:
    admin_db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB)))
os.environ["DATABASE_URL"] = make_conninfo(BASE, dbname=DB)
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="curriculum_check_")

from fastapi.testclient import TestClient     # noqa: E402

import app as study                          # noqa: E402
import clock                                 # noqa: E402
import userspace                             # noqa: E402

PASSWORD = "legacy-password-12"


def check(label, condition, detail=""):
    assert condition, f"FAIL {label} {detail}"
    print("PASS", label)


try:
    # ---- an installation from before the curriculum model ----
    now = datetime.now(timezone.utc)
    with study.connect_account() as db:
        study.init_schema(db)
        for table in ("assessment_outcomes", "assessments", "topic_outcomes", "outcomes", "subject_details", "programmes"):
            db.execute(f"DROP TABLE {table} CASCADE")
        for column in ("stability", "difficulty", "last_review", "reps", "lapses", "last_grade", "material"):
            db.execute(f"ALTER TABLE review_questions DROP COLUMN {column}")
        for column in ("grade", "retrievability", "elapsed_days"):
            db.execute(f"ALTER TABLE review_answers DROP COLUMN {column}")
        db.execute("ALTER TABLE subjects DROP CONSTRAINT subjects_level_range")
        db.execute("ALTER TABLE subjects ADD CONSTRAINT subjects_level_check CHECK (level BETWEEN 1 AND 3)")
        db.execute("ALTER TABLE exam_questions ALTER COLUMN standard_number SET NOT NULL")
        db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash text PRIMARY KEY, expires timestamptz NOT NULL)")
        db.execute("INSERT INTO settings VALUES ('password_hash', %s)", (study.hasher.hash(PASSWORD),))
        physics = db.execute("INSERT INTO subjects (name, level) VALUES ('Physics', 2) RETURNING id").fetchone()[0]
        mechanics = db.execute("INSERT INTO topics (subject_id, name) VALUES (%s, 'Mechanics') RETURNING id", (physics,)).fetchone()[0]
        waves = db.execute("INSERT INTO topics (subject_id, name) VALUES (%s, 'Waves') RETURNING id", (physics,)).fetchone()[0]
        db.execute("INSERT INTO standards VALUES (91171, 'Demonstrate understanding of mechanics', '')")
        db.execute("INSERT INTO topic_standards VALUES (%s, 91171)", (mechanics,))
        db.execute("INSERT INTO courses (topic_id) VALUES (%s), (%s)", (mechanics, waves))
        db.execute("UPDATE courses SET active = false WHERE topic_id = %s", (waves,))
        answered = db.execute("""INSERT INTO review_questions (topic_id, question, due_date, expected_answer, mastery)
            VALUES (%s, 'State Newton''s second law.', current_date - 20, 'F = ma', 0.4) RETURNING id""", (mechanics,)).fetchone()[0]
        for days, correct, confidence in ((60, True, 4), (52, True, 4)):
            db.execute("""INSERT INTO review_answers (question_id, answer, confidence, correct, outcome, answered_at)
                VALUES (%s, 'F = ma', %s, %s, 'correct', %s)""", (answered, confidence, correct, now - timedelta(days=days)))
        fresh = db.execute("""INSERT INTO review_questions (topic_id, question, due_date) VALUES (%s, 'Explain why a ball thrown up slows down.', current_date)
            RETURNING id""", (mechanics,)).fetchone()[0]
        switched_off = db.execute("""INSERT INTO review_questions (topic_id, question, due_date) VALUES (%s, 'Define wavelength.', current_date)
            RETURNING id""", (waves,)).fetchone()[0]

    with TestClient(study.app) as client:
        r = client.post("/login", json={"username": "admin", "password": PASSWORD})
        assert r.status_code == 200, r.text
        client.cookies.clear()
        me = {"Authorization": "Bearer " + r.json()["token"]}

        # ---- migration ----
        with study.connect_account() as db:
            q = db.execute("SELECT reps, stability > 0, last_review IS NOT NULL FROM u1.review_questions WHERE id = %s", (answered,)).fetchone()
            check("migration: answered questions get a memory state replayed from their answers", q == (2, True, True), q)
            check("migration: unanswered questions start new", db.execute("SELECT reps, stability FROM u1.review_questions WHERE id = %s", (fresh,)).fetchone() == (0, None))
            outcome = db.execute("""SELECT o.code, o.kind, x.topic_id FROM u1.outcomes o JOIN u1.topic_outcomes x ON x.outcome_id = o.id""").fetchall()
            check("migration: the linked NCEA standard became an outcome of its subject and topic", outcome == [("AS91171", "standard", mechanics)], outcome)
            check("migration: the old subject is untouched and still has no programme", db.execute("SELECT name, level FROM u1.subjects").fetchall() == [("Physics", 2)])
        with userspace.as_user(1):
            study.replan_daily()
        plan = client.get("/review-plan", headers=me).json()
        ids = [item["id"] for item in plan["items"]]
        check("an answered question comes back once it is due (it is no longer asked only once)", answered in ids, ids)
        check("a switched-off topic stays out of the daily list", switched_off not in ids and fresh in ids, ids)
        summary = client.get("/study-summary", headers=me).json()
        check("Home counts the same list", summary["reviews"]["due"] == len(ids))
        mechanics_row = next(t for t in summary["topics"] if t["topic_id"] == mechanics)
        check("topic recall counts only reviewed questions (the unanswered one is not a zero)",
              mechanics_row["reviewed_questions"] == 1 and mechanics_row["questions"] == 2 and 0.5 < mechanics_row["mastery"] <= 1, mechanics_row)
        check("NCEA estimate waits for a marked past paper", next(e for e in client.get("/grade-estimates", headers=me).json()
                                                                  if e["subject_id"] == physics)["estimate"] is None)

        # ---- a university paper ----
        today = clock.today()
        programme = client.post("/programmes", headers=me, json={"kind": "university", "institution": "aut", "name": "BCIS", "year": today.year})
        check("a university programme can be set up", programme.status_code == 201, programme.text)
        paper = client.post("/papers", headers=me, json={
            "programme_id": programme.json()["id"], "code": "COMP500", "title": "Programming Concepts", "points": 15, "level": 5,
            "grade_scale": "aut9", "source": "aut_descriptor", "pass_rule": "Attempt all and achieve an overall C-.",
            "outcomes": [{"code": "LO1", "title": "Write and debug small programs"}, {"code": "LO2", "title": "Use selection and iteration"}],
            "assessments": [{"title": "Practical test", "kind": "test", "weight_pct": 40, "due_date": str(today + timedelta(days=20)), "outcome_codes": ["LO1"]},
                            {"title": "Final exam", "kind": "exam", "weight_pct": 60, "due_date": str(today + timedelta(days=60)), "outcome_codes": ["LO1", "LO2"]}]})
        check("a paper is saved with level 5 (the NCEA-only 1-3 limit is gone)", paper.status_code == 201, paper.text)
        paper_id = paper.json()["subject_id"]
        curriculum = client.get("/curriculum", headers=me).json()
        saved = next(s for s in curriculum["subjects"] if s["subject_id"] == paper_id)
        check("one topic per learning outcome, each linked to it", [(t["name"], len(t["outcome_ids"])) for t in saved["topics"]]
              == [("Write and debug small programs", 1), ("Use selection and iteration", 1)], saved["topics"])
        check("assessments keep weights and outcomes", [(a["title"], a["weight_pct"], a["outcome_codes"]) for a in saved["assessments"]]
              == [("Practical test", 40.0, ["LO1"]), ("Final exam", 60.0, ["LO1", "LO2"])], saved["assessments"])
        topic = saved["topics"][0]["id"]
        client.post("/courses", headers=me, json={"topic_id": topic})
        question = client.post(f"/topics/{topic}/review-questions", headers=me, json={"question": "What does a compiler do?", "due_date": str(today)}).json()["id"]

        def answer(confidence):
            reply = client.post(f"/review-questions/{question}/answers", headers=me, json={"answer": "It translates source code", "confidence": confidence})
            assert reply.status_code == 201, reply.text
            return reply.json()

        def due_ids():
            return [i["id"] for i in client.get("/review-plan", headers=me).json()["items"]]

        def advance(days):
            client.put("/dev/clock", headers=me, json={"offset_days": clock.offset_days() + days})

        check("a new question is in today's list", question in due_ids())
        first = answer(4)                                        # unmarked here: confidence 4 -> Good
        check("after a first Good answer it returns in 2 days", first["interval_days"] == 2 and first["grade"] == 3, first)
        check("it leaves today's list once answered", question not in due_ids())
        advance(1)
        check("not due the day before its date", question not in due_ids())
        advance(1)
        check("due on its date", question in due_ids())
        second = answer(4)
        check("a second Good answer gives a longer gap", second["interval_days"] > first["interval_days"], second)
        wrong = answer(1)
        check("a wrong answer is asked again this session and its gap shrinks",
              wrong["relearn"] and wrong["interval_days"] < second["interval_days"], (second, wrong))
        advance(1)
        answer(4)
        answer(5)
        gap_before = client.get(f"/review-questions?topic_id={topic}", headers=me).json()[0]["due_date"]
        test_id = saved["assessments"][0]["id"]
        moved_to = clock.today() + timedelta(days=4)
        client.put(f"/assessments/{test_id}", headers=me, json={"title": "Practical test", "kind": "test", "weight_pct": 40,
                                                                "due_date": str(moved_to), "outcome_codes": ["LO1"]})
        gap_after = client.get(f"/review-questions?topic_id={topic}", headers=me).json()[0]["due_date"]
        check("moving the test closer pulls the review in before it", gap_after < str(moved_to) and gap_after <= gap_before, (gap_before, gap_after, moved_to))
        ready = client.get("/review-plan", headers=me).json()["assessments"]
        check("readiness is reported for the coming test", ready and ready[0]["title"] == "Practical test" and ready[0]["reviewed"] == 1, ready)

        advance(70)                  # both assessments are now past
        with userspace.as_user(1), study.connect() as db:
            import review_plan
            check("after its assessments the topic is in maintenance", review_plan.topic_phase(db, topic, clock.today())[0] == "maintain")
        later = answer(4)
        check("maintenance keeps the item on a schedule (it is not dropped)", later["next_due"] > str(clock.today()), later)

        client.put(f"/assessments/{test_id}", headers=me, json={"title": "Practical test", "kind": "test", "weight_pct": 40,
                                                                "due_date": str(moved_to), "outcome_codes": ["LO1"], "status": "done", "result_pct": 76})
        estimate = next(e for e in client.get("/grade-estimates", headers=me).json() if e["subject_id"] == paper_id)
        check("a university estimate is the weighted grade so far on the A+ to D scale", estimate["estimate"] == "B+" and estimate["weight_counted"] == 40, estimate)
        hours = client.put("/study-time", headers=me, json={"hours_per_week": 7})
        check("study time sets the daily cap", hours.status_code == 200 and client.get("/review-plan", headers=me).json()["cap"] == 18)
        client.put("/dev/clock", headers=me, json={"offset_days": 0})
finally:
    clock._offset = timedelta()
    with psycopg.connect(BASE, autocommit=True) as admin_db:
        admin_db.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(DB)))
    print("CLEANUP: disposable database removed")
