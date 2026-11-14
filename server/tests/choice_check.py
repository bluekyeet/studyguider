"""Real PostgreSQL checks for multiple choice and past-exam imports: an account made before them is migrated, a multiple-choice
question is marked against its answer key with no model gateway at all, and an import that cannot reach the model ends as a
failure the learner can see.

Run only against a disposable stack (it creates and drops its own database inside that server):
  docker compose exec -T -e DISPOSABLE_TEST_DATABASE=yes api python - < server/tests/choice_check.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid

assert os.environ.get("DISPOSABLE_TEST_DATABASE") == "yes", "refusing to run without DISPOSABLE_TEST_DATABASE=yes"
os.environ.pop("ROUTER_BASE_URL", None)       # no model: anything that needs one must say so, not hang or guess
os.environ.pop("ROUTER_API_KEY", None)
os.environ["IMPORT_PAUSE_SECONDS"] = "0"

try:
    import httpx  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--target", "/tmp/httpx_site", "httpx"], check=True)
    sys.path.insert(0, "/tmp/httpx_site")

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

BASE = os.environ["DATABASE_URL"]
DB = "choice_check_" + uuid.uuid4().hex[:12]
with psycopg.connect(BASE, autocommit=True) as admin_db:
    admin_db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB)))
os.environ["DATABASE_URL"] = make_conninfo(BASE, dbname=DB)
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="choice_check_")

from fastapi.testclient import TestClient     # noqa: E402

import app as study                          # noqa: E402

PASSWORD = "legacy-password-12"


def check(label, condition, detail=""):
    assert condition, f"FAIL {label} {detail}"
    print("PASS", label)


try:
    # ---- an installation from before multiple choice and past-exam imports ----
    with study.connect_account() as db:
        study.init_schema(db)
        db.execute("DROP TABLE exam_imports CASCADE")
        db.execute("DROP TABLE review_variants CASCADE")
        for column in ("choice_key", "marks_exact", "guide_source", "import_id", "outcome_codes"):
            db.execute(f"ALTER TABLE exam_questions DROP COLUMN {column}")
        for column in ("choice_key", "variant_failed_at"):
            db.execute(f"ALTER TABLE review_questions DROP COLUMN {column}")
        db.execute("ALTER TABLE assessments DROP COLUMN question_format")
        db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash text PRIMARY KEY, expires timestamptz NOT NULL)")
        db.execute("INSERT INTO settings VALUES ('password_hash', %s)", (study.hasher.hash(PASSWORD),))
        subject = db.execute("INSERT INTO subjects (name, level) VALUES ('Computing', 1) RETURNING id").fetchone()[0]
        topic = db.execute("INSERT INTO topics (subject_id, name) VALUES (%s, 'Storage') RETURNING id", (subject,)).fetchone()[0]
        old = db.execute("""INSERT INTO exam_questions (topic_id, year, question_number, paper_page, schedule_page, marks, question_text,
                schedule_text, source) VALUES (%s, 2025, '1', 1, 1, 3, 'Explain RAID.', 'Redundancy (1 mark).', 'ai') RETURNING id""",
                         (topic,)).fetchone()[0]

    with TestClient(study.app) as client:
        r = client.post("/login", json={"username": "admin", "password": PASSWORD})
        assert r.status_code == 200, r.text
        client.cookies.clear()
        me = {"Authorization": "Bearer " + r.json()["token"]}

        # ---- migration ----
        with study.connect_account() as db:
            columns = {row[0] for row in db.execute("""SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'u1' AND table_name = 'exam_questions'""").fetchall()}
            check("migration: exam questions gain the answer key, printed marks, guide source, import and outcomes",
                  {"choice_key", "marks_exact", "guide_source", "import_id", "outcome_codes"} <= columns, columns)
            tables = {row[0] for row in db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'u1'").fetchall()}
            check("migration: every account gets the import and variant tables", {"exam_imports", "review_variants"} <= tables)
            check("migration: an existing question keeps its text and has no key",
                  db.execute("SELECT question_text, choice_key, guide_source FROM u1.exam_questions WHERE id = %s", (old,)).fetchone()
                  == ("Explain RAID.", None, ""))

        # ---- a multiple-choice question is marked against its key, with no gateway ----
        form = {"kind": "choice", "options": [{"key": "A", "text": "USB drive"}, {"key": "B", "text": "RAM"}, {"key": "C", "text": "SSD"}],
                "multiple": False, "shuffle": True, "instructions": "Choose one answer.", "group": "", "penalty": 0.5}
        key = {"correct": ["B"], "explanations": {"B": "RAM loses its contents without power.", "C": "An SSD keeps data without power."},
               "partial": False, "source": "official"}
        with study.userspace.as_user(1), study.connect() as db:
            question = db.execute("""INSERT INTO exam_questions (topic_id, year, question_number, paper_page, schedule_page, marks, marks_exact,
                    question_text, schedule_text, source, answer_forms, choice_key, guide_source)
                VALUES (%s, 2025, '2', 1, 1, 3, 2.5, 'Which one of the following is volatile storage?', 'Correct option: B. RAM', 'import',
                        %s::jsonb, %s::jsonb, 'official') RETURNING id""",
                (topic, json.dumps({"": [form, {"kind": "text", "palette": "general"}]}), json.dumps({"": key}))).fetchone()[0]
            exam = db.execute("INSERT INTO exams (subject_id, kind, total_marks) VALUES (%s, 'original', 3) RETURNING id", (subject,)).fetchone()[0]
            db.execute("INSERT INTO exam_items (exam_id, question_id, position) VALUES (%s, %s, 1)", (exam, question))
        shown = client.get(f"/exams/{exam}", headers=me).json()["questions"][0]
        choice_form = shown["answer_forms"][""][0]
        check("the form reaches the learner without the key, in this attempt's order",
              choice_form["kind"] == "choice" and "correct" not in json.dumps(shown["answer_forms"])
              and sorted(choice_form["display_order"]) == ["A", "B", "C"], choice_form)
        check("an imported question says where its guide came from", shown["guide_source"] == "official" and shown["marks_exact"] == 2.5)

        def mark(answer):
            saved = client.put(f"/exams/{exam}/answers/{question}", headers=me,
                               json={"answer": answer, "revision": client.get(f"/exams/{exam}", headers=me).json()["questions"][0]["answer_revision"]})
            assert saved.status_code == 200, saved.text
            return client.post(f"/exams/{exam}/answers/{question}/feedback", headers=me, json={})

        right = mark("Choice: B")
        check("a right choice is marked from the key with no model", right.status_code == 200 and right.json()["marked_by"] == "answer-key"
              and right.json()["net_marks"] == 2.5 and right.json()["second_review"] is None, right.text)
        wrong = mark("Choice: C")
        body = wrong.json()
        check("a wrong choice loses the paper's negative marking and is explained", body["net_marks"] == -0.5
              and "An SSD keeps data without power." in body["feedback"], body)
        totals = client.get(f"/exams/{exam}/marks", headers=me).json()
        check("the paper total after negative marking never goes below zero", totals["net_marks_awarded"] == 0 and totals["net_marks_available"] == 2.5, totals)
        with study.userspace.as_user(1), study.connect() as db:
            review = db.execute("SELECT question, choice_key IS NULL FROM review_questions WHERE exam_origin = %s", (f"{exam}:{question}",)).fetchone()
        check("the miss comes back in review", review is not None and "volatile" in review[0], review)

        # ---- an import that cannot reach the model ends as a visible failure ----
        started = client.post(f"/subjects/{subject}/exam-imports", headers=me, data={"title": "Test 2025", "year": "2025"},
                              files={"paper": ("test.txt", b"Question 1 [2 marks] Which one of the following is volatile storage?\n(a) RAM\n(b) SSD\n" * 3, "text/plain")})
        check("an upload starts an import", started.status_code == 202, started.text)
        for _ in range(60):
            state = client.get(f"/exam-imports/{started.json()['id']}", headers=me).json()
            if state["status"] != "reading":
                break
            time.sleep(1)
        check("an import that cannot reach the model fails with a reason", state["status"] == "failed" and state["error"], state)
        again = client.post(f"/subjects/{subject}/exam-imports", headers=me, data={"title": "Test 2025"},
                            files={"paper": ("test.txt", b"Question 1 [2 marks] Which one of the following is volatile storage?\n(a) RAM\n(b) SSD\n" * 3, "text/plain")})
        check("a failed import can be uploaded again", again.status_code == 202, again.text)
        for _ in range(60):     # let it finish before the database goes
            if client.get(f"/exam-imports/{again.json()['id']}", headers=me).json()["status"] != "reading":
                break
            time.sleep(1)
        refused = client.post(f"/subjects/{subject}/exam-imports", headers=me, files={"paper": ("virus.exe", b"MZ", "application/octet-stream")})
        check("a file that is not a paper is refused", refused.status_code == 422)
finally:
    with psycopg.connect(BASE, autocommit=True) as admin_db:
        admin_db.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(DB)))
    print("CLEANUP: disposable database removed")
