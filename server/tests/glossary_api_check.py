"""Real PostgreSQL checks for the API under the glossary's names: Learning topics (old /courses kept as an alias), one Standard per
Topic, and Predicted recall (old mastery routes kept as an alias).

Run only against a disposable stack (it creates and drops its own database inside that server):
  docker compose exec -T -e DISPOSABLE_TEST_DATABASE=yes api python - < server/tests/glossary_api_check.py
"""
import os
import subprocess
import sys
import tempfile
import uuid

assert os.environ.get("DISPOSABLE_TEST_DATABASE") == "yes", "refusing to run without DISPOSABLE_TEST_DATABASE=yes"

try:
    import httpx  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--target", "/tmp/httpx_site", "httpx"], check=True)
    sys.path.insert(0, "/tmp/httpx_site")

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

BASE = os.environ["DATABASE_URL"]
DB = "glossary_api_check_" + uuid.uuid4().hex[:12]
with psycopg.connect(BASE, autocommit=True) as admin_db:
    admin_db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB)))
os.environ["DATABASE_URL"] = make_conninfo(BASE, dbname=DB)
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="glossary_api_check_")

from fastapi.testclient import TestClient     # noqa: E402

import app as study                          # noqa: E402

PASSWORD = "glossary-password-12"


def check(label, condition, detail=""):
    assert condition, f"FAIL {label} {detail}"
    print("PASS", label)


try:
    with study.connect_account() as db:         # a single-password installation, which start-up turns into the admin account
        study.init_schema(db)
        db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash text PRIMARY KEY, expires timestamptz NOT NULL)")
        db.execute("INSERT INTO settings VALUES ('password_hash', %s)", (study.hasher.hash(PASSWORD),))

    with TestClient(study.app) as client:
        r = client.post("/login", json={"username": "admin", "password": PASSWORD})
        assert r.status_code == 200, r.text
        client.cookies.clear()
        me = {"Authorization": "Bearer " + r.json()["token"]}
        maths = client.post("/subjects", headers=me, json={"name": "Maths", "level": 1}).json()["id"]
        algebra, graphs = (client.post(f"/subjects/{maths}/topics", headers=me, json={"name": name}).json()["id"] for name in ("Algebra", "Graphs"))
        for number, title in ((91027, "Algebra"), (91028, "Graphs")):
            assert client.put(f"/standards/{number}", headers=me, json={"title": title}).status_code == 200

        # ---- Learning topics ----
        added = client.post("/learning-topics", headers=me, json={"topic_id": algebra})
        check("a Topic can be made a Learning topic", added.status_code == 201 and added.json()["topic_id"] == algebra, added.text)
        listed = client.get("/learning-topics", headers=me).json()
        check("Learning topics are listed", [(t["id"], t["topic_id"], t["topic"]) for t in listed] == [(added.json()["id"], algebra, "Algebra")], listed)
        check("the old /courses route lists the same", client.get("/courses", headers=me).json() == listed)
        old = client.post("/courses", headers=me, json={"topic_id": graphs})
        check("the old /courses route still adds one", old.status_code == 201 and old.json()["topic_id"] == graphs, old.text)
        gone = client.delete(f"/learning-topics/{added.json()['id']}", headers=me)
        check("a Learning topic can be switched off", gone.status_code == 200, gone.text)
        check("the old /courses route still removes one", client.delete(f"/courses/{old.json()['id']}", headers=me).status_code == 200)
        check("nothing is left active", client.get("/learning-topics", headers=me).json() == [])
        check("a missing Learning topic is 404", client.delete("/learning-topics/999999", headers=me).status_code == 404)

        # ---- an NCEA Topic is one Standard ----
        first = client.put(f"/topics/{algebra}/standards/91027", headers=me)
        check("a Topic takes its Standard", first.status_code in (200, 201), first.text)
        check("linking the same Standard again is harmless", client.put(f"/topics/{algebra}/standards/91027", headers=me).status_code in (200, 201))
        second = client.put(f"/topics/{algebra}/standards/91028", headers=me)
        check("a second Standard on the same Topic is refused", second.status_code == 409, second.text)
        check("the Topic still has only its first Standard",
              [s["number"] for s in client.get(f"/topics/{algebra}/standards", headers=me).json()] == [91027])
        check("the other Standard can go on its own Topic", client.put(f"/topics/{graphs}/standards/91028", headers=me).status_code in (200, 201))

        # ---- Predicted recall ----
        topics = client.get(f"/subjects/{maths}/topics", headers=me).json()
        check("Topics carry predicted_recall, not mastery", all("predicted_recall" in t and "mastery" not in t for t in topics), topics)
        recall = client.get(f"/topics/{algebra}/predicted-recall", headers=me)
        check("a Topic's Predicted recall has its own route", recall.status_code == 200 and recall.json()["predicted_recall"] == 0, recall.text)
        old_route = client.get(f"/topics/{algebra}/mastery", headers=me).json()
        check("the old /mastery route answers the same, with the old key too",
              old_route == {**recall.json(), "mastery": recall.json()["predicted_recall"]}, old_route)
        client.post("/learning-topics", headers=me, json={"topic_id": algebra})
        summary = client.get("/study-summary", headers=me)
        assert summary.status_code == 200, summary.text
        summary = summary.json()
        row = next(t for t in summary["topics"] if t["topic_id"] == algebra)
        check("Home gives overall and per-Topic predicted_recall", "overall_predicted_recall" in summary and "predicted_recall" in row, summary)
        check("Home keeps the old mastery keys for apps built before the rename",
              summary["overall_mastery"] == summary["overall_predicted_recall"] and row["mastery"] == row["predicted_recall"], summary)
        check("the review plan reads", client.get("/review-plan", headers=me).status_code == 200)
        check("the rewards profile reads", client.get("/game/me", headers=me).status_code == 200)
        board = client.get("/game/leaderboard/grade", headers=me)
        check("the estimated-grade leaderboard reads", board.status_code == 200, board.text)
finally:
    with psycopg.connect(BASE, autocommit=True) as admin_db:
        admin_db.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(DB)))
    print("CLEANUP: disposable database removed")
