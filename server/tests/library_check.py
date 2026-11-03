"""Real PostgreSQL checks for the global library: the first administrator's library becomes global, every account reads it
read-only, adds its own files beside it, and nobody sees another account's files.

Run only against a disposable stack:
  docker compose exec -T -e DISPOSABLE_TEST_DATABASE=yes api python - < server/tests/library_check.py
"""
import os
import tempfile
import time
import uuid
from pathlib import Path

assert os.environ.get("DISPOSABLE_TEST_DATABASE") == "yes", "refusing to run without DISPOSABLE_TEST_DATABASE=yes"

import subprocess
import sys

try:
    import httpx  # noqa: F401
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--target", "/tmp/httpx_site", "httpx"], check=True)
    sys.path.insert(0, "/tmp/httpx_site")

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

BASE = os.environ["DATABASE_URL"]
DB = "library_check_" + uuid.uuid4().hex[:12]
UPLOADS = tempfile.mkdtemp(prefix="library_check_")
with psycopg.connect(BASE, autocommit=True) as admin_db:
    admin_db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB)))
os.environ["DATABASE_URL"] = make_conninfo(BASE, dbname=DB)
os.environ["UPLOAD_DIR"] = UPLOADS

from fastapi.testclient import TestClient     # noqa: E402

import app as study                          # noqa: E402
import userspace                             # noqa: E402

PASSWORD = "admin-long-password"
PAPER, SCHEDULE, NOTES = (str(uuid.uuid4()) for _ in range(3))


def check(label, condition, detail=""):
    assert condition, f"FAIL {label} {detail}"
    print("PASS", label)


try:
    # The old single-account layout with a library in it, so the first start moves it into the global library.
    with study.connect_account() as db:
        study.init_schema(db)
        db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash text PRIMARY KEY, expires timestamptz NOT NULL)")
        db.execute("INSERT INTO settings VALUES ('password_hash', %s)", (study.hasher.hash(PASSWORD),))
        subject = db.execute("INSERT INTO subjects (name, level) VALUES ('Shared Physics', 2) RETURNING id").fetchone()[0]
        topic = db.execute("INSERT INTO topics (subject_id, name) VALUES (%s, 'Shared Mechanics') RETURNING id", (subject,)).fetchone()[0]
        db.execute("INSERT INTO standards VALUES (91171, 'Mechanics', 'Demonstrate understanding of mechanics')")
        for rid, name in ((PAPER, "91171-exm-2022.pdf"), (SCHEDULE, "91171-ass-2022.pdf"), (NOTES, "notes.txt")):
            db.execute("INSERT INTO resources (id, topic_id, filename, size, status, category, page_count) VALUES (%s, %s, %s, 5, 'extracted', 'extra', 1)", (rid, topic, name))
            db.execute("INSERT INTO resource_text VALUES (%s, %s)", (rid, f"text of {name} with the word momentum"))
            db.execute("INSERT INTO resource_pages VALUES (%s, 1, %s)", (rid, f"page of {name}"))
            db.execute("INSERT INTO resource_chunks (resource_id, topic_id, standard_number, page, ordinal, content) VALUES (%s, %s, 91171, 1, 1, %s)", (rid, topic, f"chunk about momentum in {name}"))
        db.execute("INSERT INTO topic_standards VALUES (%s, 91171)", (topic,))
        db.execute("""INSERT INTO exam_questions (topic_id, standard_number, year, question_number, paper_resource_id, paper_page, schedule_resource_id, schedule_page,
            marks, question_text, schedule_text, source) VALUES (%s, 91171, 2022, '1', %s, 1, %s, 1, 3, 'Q one', 'S one', 'pdf-layout')""", (topic, PAPER, SCHEDULE))
        db.execute("""INSERT INTO exam_questions (topic_id, standard_number, year, question_number, paper_page, schedule_page, source, question_text) VALUES (%s, 91171, 2022, 'ai1', 1, 1, 'ai', 'private practice')""", (topic,))
    for rid in (PAPER, SCHEDULE, NOTES):
        Path(UPLOADS, rid).write_bytes(b"file " + rid.encode())

    with TestClient(study.app) as client:
        def login(username, password):
            r = client.post("/login", json={"username": username, "password": password})
            assert r.status_code == 200, (username, r.status_code, r.text)
            client.cookies.clear()
            return {"Authorization": "Bearer " + r.json()["token"]}

        admin = login("admin", PASSWORD)
        GLOBAL = {"X-Library": "global"}
        with study.connect_account() as db:
            g = db.execute("""SELECT (SELECT count(*) FROM u0.subjects), (SELECT count(*) FROM u0.topics), (SELECT count(*) FROM u0.resources),
                (SELECT count(*) FROM u0.resource_pages), (SELECT count(*) FROM u0.resource_chunks), (SELECT count(*) FROM u0.exam_questions)""").fetchone()
            check("the first administrator's library became the global library (the AI practice question stayed private)", g == (1, 1, 3, 3, 3, 1), g)
            a = db.execute("SELECT (SELECT global_id FROM u1.subjects), (SELECT global_id FROM u1.topics), (SELECT count(*) FROM u1.resources WHERE is_global), (SELECT count(*) FROM u1.exam_questions WHERE global_id IS NOT NULL), (SELECT count(*) FROM u1.exam_questions)").fetchone()
            check("the administrator's own rows now point at the shared copies and keep their ids", a == (subject, topic, 3, 1, 2), a)
        check("global files are hard links, stored once", os.stat(Path(UPLOADS, "u0", PAPER)).st_ino == os.stat(Path(UPLOADS, "u1", PAPER)).st_ino)

        check("an admin can add a user", client.post("/users", headers=admin, json={"username": "learner1", "password": "learner-long-password"}).status_code == 201)
        check("and another", client.post("/users", headers=admin, json={"username": "learner2", "password": "learner2-long-password"}).status_code == 201)
        one = login("learner1", "learner-long-password")
        two = login("learner2", "learner2-long-password")

        subjects = client.get("/subjects", headers=one).json()
        check("a new user sees the global subject, marked as global", [(s["name"], s["global"]) for s in subjects] == [("Shared Physics", True)], subjects)
        topics = client.get(f"/subjects/{subjects[0]['id']}/topics", headers=one).json()
        check("and its topic", [(t["name"], t["global"]) for t in topics] == [("Shared Mechanics", True)], topics)
        mine = topics[0]["id"]
        files = client.get(f"/topics/{mine}/resources", headers=one).json()
        check("opening the topic brings in its global files, marked as global", sorted(f["filename"] for f in files) == ["91171-ass-2022.pdf", "91171-exm-2022.pdf", "notes.txt"] and all(f["is_global"] for f in files), files)
        with userspace.as_user(2), study.connect() as db:
            counts = db.execute("SELECT (SELECT count(*) FROM resource_pages), (SELECT count(*) FROM resource_chunks), (SELECT count(*) FROM exam_questions), (SELECT count(*) FROM topic_standards)").fetchone()
        check("their text, chunks, standards and imported questions came with them (not the private AI question)", counts == (3, 3, 1, 1), counts)
        check("the files are linked into the user's folder without a second copy", os.stat(Path(UPLOADS, "u2", NOTES)).st_ino == os.stat(Path(UPLOADS, "u0", NOTES)).st_ino)
        check("a user can download a global file", client.get(f"/resources/{NOTES}/download", headers=one).status_code == 200)

        check("a user cannot delete a global file, subject or topic, or relink its standards",
              client.delete(f"/resources/{NOTES}", headers=one).status_code == 403
              and client.delete(f"/subjects/{subjects[0]['id']}", headers=one).status_code == 403
              and client.delete(f"/subjects/{subjects[0]['id']}/topics/{mine}", headers=one).status_code == 403
              and client.put(f"/subjects/{subjects[0]['id']}/topics/{mine}", headers=one, json={"name": "Renamed"}).status_code == 403
              and client.delete(f"/topics/{mine}/standards/91171", headers=one).status_code == 403)
        check("a user can switch a global topic on as a learning topic", client.post("/courses", headers=one, json={"topic_id": mine}).status_code == 201)

        own = client.post(f"/topics/{mine}/resources", headers=one, files={"file": ("my-own-notes.txt", b"my private notes about thermodynamics")})
        check("a user can add their own file under a global topic", own.status_code == 201, own.text)
        names = sorted(f["filename"] for f in client.get(f"/topics/{mine}/resources", headers=one).json())
        check("they see global files plus their own", "my-own-notes.txt" in names and "notes.txt" in names, names)
        two_topic = client.get(f"/subjects/{client.get('/subjects', headers=two).json()[0]['id']}/topics", headers=two).json()[0]["id"]
        two_names = sorted(f["filename"] for f in client.get(f"/topics/{two_topic}/resources", headers=two).json())
        check("another user sees only the global files", "my-own-notes.txt" not in two_names and "notes.txt" in two_names, two_names)
        admin_names = [f["filename"] for f in client.get(f"/topics/{topic}/resources", headers=admin).json()]
        check("the administrator's normal library does not show the user's file either", "my-own-notes.txt" not in admin_names)

        deadline = time.time() + 40
        found = []
        while time.time() < deadline:
            found = client.get(f"/topics/{mine}/search", headers=one, params={"q": "thermodynamics"}).json()
            if found:
                break
            time.sleep(2)
        check("a user's own file is searchable by them", bool(found), found)
        check("but not by anyone else", client.get(f"/topics/{two_topic}/search", headers=two, params={"q": "thermodynamics"}).json() == [])
        check("search for the global text works for everyone", bool(client.get(f"/topics/{two_topic}/search", headers=two, params={"q": "momentum"}).json()))

        check("only an administrator may use the global library header", client.post("/subjects", headers={**one, **GLOBAL}, json={"name": "Hacked", "level": 1}).status_code == 403)
        check("and only for library actions", client.get("/lessons", headers={**admin, **GLOBAL}).status_code == 403)
        created = client.post("/subjects", headers={**admin, **GLOBAL}, json={"name": "Global Chemistry", "level": 2})
        check("an administrator can add a global subject", created.status_code == 201, created.text)
        gsubject = created.json()["id"]
        gtopic = client.post(f"/subjects/{gsubject}/topics", headers={**admin, **GLOBAL}, json={"name": "Global Bonding"}).json()["id"]
        check("global changes do not appear in the administrator's own library listing until synced, and never as editable",
              all(s["global"] for s in client.get("/subjects", headers=admin).json() if s["name"] == "Global Chemistry"))
        seen = client.get("/subjects", headers=one).json()
        check("a user sees the new global subject straight away, read-only", [s["global"] for s in seen if s["name"] == "Global Chemistry"] == [True], seen)
        uploaded = client.post(f"/topics/{gtopic}/resources", headers={**admin, **GLOBAL}, files={"file": ("bonding.txt", b"covalent bonding shares electrons")})
        check("an administrator can add a global file", uploaded.status_code == 201, uploaded.text)
        mapped = next(t["id"] for s in seen if s["name"] == "Global Chemistry" for t in client.get(f"/subjects/{s['id']}/topics", headers=one).json())
        deadline = time.time() + 40
        listed = []
        while time.time() < deadline:
            listed = client.get(f"/topics/{mapped}/resources", headers=one).json()
            if listed:
                break
            time.sleep(2)
        check("once extracted, the new global file reaches users", [f["filename"] for f in listed] == ["bonding.txt"] and listed[0]["is_global"], listed)
        check("a global file can be removed by an administrator in the library", client.delete(f"/resources/{uploaded.json()['id']}", headers={**admin, **GLOBAL}).status_code in (200, 204))

    print("ALL LIBRARY CHECKS PASSED")
finally:
    import shutil
    shutil.rmtree(UPLOADS, ignore_errors=True)
    with psycopg.connect(BASE, autocommit=True) as admin_db:
        admin_db.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(DB)))
