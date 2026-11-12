"""Real PostgreSQL checks for accounts: legacy migration, separation of every account's data and files, roles and profile.

Run only against a disposable stack (it creates and drops its own database inside that server):
  docker compose exec -T -e DISPOSABLE_TEST_DATABASE=yes api python - < server/tests/accounts_check.py
The old single-password layout is built with the real table-creation code (everything in `public`), then the app starts on it.
"""
import io
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

assert os.environ.get("DISPOSABLE_TEST_DATABASE") == "yes", "refusing to run without DISPOSABLE_TEST_DATABASE=yes"

import subprocess
import sys

try:
    import httpx  # noqa: F401  (needed by the test client; the production image does not carry it)
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--target", "/tmp/httpx_site", "httpx"], check=True)
    sys.path.insert(0, "/tmp/httpx_site")

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

BASE = os.environ["DATABASE_URL"]
DB = "accounts_check_" + uuid.uuid4().hex[:12]
UPLOADS = tempfile.mkdtemp(prefix="accounts_check_")
with psycopg.connect(BASE, autocommit=True) as admin_db:
    admin_db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB)))
os.environ["DATABASE_URL"] = make_conninfo(BASE, dbname=DB)
os.environ["UPLOAD_DIR"] = UPLOADS

from fastapi.testclient import TestClient     # noqa: E402

import app as study                          # noqa: E402
import userspace                             # noqa: E402

OLD_PASSWORD = "legacy-password-12"
LEGACY_FILE = str(uuid.uuid4())


def check(label, condition, detail=""):
    assert condition, f"FAIL {label} {detail}"
    print("PASS", label)


def png(color=(200, 30, 30), size=(600, 400)):
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


try:
    # ---- the old layout: every table in public, one password in settings ----
    with study.connect_account() as db:
        study.init_schema(db)
        db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash text PRIMARY KEY, expires timestamptz NOT NULL)")
        db.execute("INSERT INTO settings VALUES ('password_hash', %s)", (study.hasher.hash(OLD_PASSWORD),))
        db.execute("INSERT INTO settings VALUES ('login_failures', '2')")
        subject = db.execute("INSERT INTO subjects (name, level) VALUES ('Legacy Physics', 2) RETURNING id").fetchone()[0]
        topic = db.execute("INSERT INTO topics (subject_id, name) VALUES (%s, 'Legacy Mechanics') RETURNING id", (subject,)).fetchone()[0]
        db.execute("INSERT INTO resources (id, topic_id, filename, size, status) VALUES (%s, %s, 'old.txt', 5, 'extracted')", (LEGACY_FILE, topic))
        db.execute("INSERT INTO notes (topic_id, content) VALUES (%s, 'an old note')", (topic,))
    Path(UPLOADS, LEGACY_FILE).write_bytes(b"hello")

    with TestClient(study.app) as client:
        def login(username, password, expect=200):
            r = client.post("/login", json={"username": username, "password": password})
            assert r.status_code == expect, (username, r.status_code, r.text)
            client.cookies.clear()         # requests below authenticate with the token only
            return {"Authorization": "Bearer " + r.json()["token"]} if expect == 200 else None

        # ---- migration ----
        with study.connect_account() as db:
            users = db.execute("SELECT id, username, is_admin FROM users").fetchall()
            public_tables = {r[0] for r in db.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()}
            check("migration: the old installation became the first admin account", users == [(1, "admin", True)], users)
            check("migration: only accounts, sessions and the leaderboard snapshot are left in the shared schema", public_tables == {"users", "sessions", "game_profiles"}, public_tables)
            moved = db.execute("SELECT (SELECT count(*) FROM u1.subjects), (SELECT count(*) FROM u1.notes), (SELECT count(*) FROM u1.settings WHERE key <> 'x')").fetchone()
            check("migration: the old data moved into the account's schema intact", moved[:2] == (1, 1), moved)
            check("migration: the old login lock and password rows were not carried over", db.execute("SELECT count(*) FROM u1.settings").fetchone()[0] == 0)
        check("migration: uploaded files moved into the account's folder", Path(UPLOADS, "u1", LEGACY_FILE).read_bytes() == b"hello" and not Path(UPLOADS, LEGACY_FILE).exists())
        admin = login("admin", OLD_PASSWORD)
        check("the old password still works for the migrated admin", True)
        check("the admin sees the old subject", [s["name"] for s in client.get("/subjects", headers=admin).json()] == ["Legacy Physics"])
        check("the old upload still downloads for the admin", client.get(f"/resources/{LEGACY_FILE}/download", headers=admin).content == b"hello")

        # ---- accounts and roles ----
        check("unauthenticated requests are refused", client.get("/subjects").status_code == 401 and client.get("/users").status_code == 401)
        check("an admin can add a user", client.post("/users", headers=admin, json={"username": "bob.smith", "password": "bobs-long-password"}).status_code == 201)
        check("usernames are unique regardless of case", client.post("/users", headers=admin, json={"username": "BOB.SMITH", "password": "another-long-pass"}).status_code == 409)
        check("short passwords and odd usernames are refused", client.post("/users", headers=admin, json={"username": "carol", "password": "short"}).status_code == 422
              and client.post("/users", headers=admin, json={"username": "a b", "password": "long-enough-password"}).status_code == 422)
        bob = login("bob.smith", "bobs-long-password")
        check("usernames sign in case-insensitively", login("Bob.Smith", "bobs-long-password") is not None)
        login("bob.smith", "wrong-password", 401)
        login("nobody", "whatever-password", 401)

        check("a normal user cannot manage accounts", all(client.request(m, p, headers=bob, json={"username": "eve1", "password": "evil-long-password"}).status_code == 403
                                                           for m, p in (("GET", "/users"), ("POST", "/users"), ("PUT", "/users/1"), ("DELETE", "/users/1"))))
        check("a normal user cannot open the advanced tools' admin routes", client.get("/usage", headers=bob).status_code == 403
              and client.get("/topics/1/parsed-questions", headers=bob).status_code == 403)
        check("the admin can", client.get("/usage?days=7", headers=admin).status_code == 200)
        check("session reports the role", client.get("/session", headers=bob).json()["user"]["is_admin"] is False and client.get("/session", headers=admin).json()["user"]["is_admin"] is True)

        # ---- everything separated ----
        check("a new user starts with only the read-only global library", [(s["name"], s["global"]) for s in client.get("/subjects", headers=bob).json()] == [("Legacy Physics", True)])
        mine = client.post("/subjects", headers=bob, json={"name": "Bob Chemistry", "level": 2})
        check("a user can create their own subject (ids are their own)", mine.status_code == 201 and mine.json()["id"] == 2, mine.text)
        bob_topic = client.post("/subjects/2/topics", headers=bob, json={"name": "Bob Topic"}).json()["id"]
        check("each account sees the global library and only its own additions", [s["name"] for s in client.get("/subjects", headers=bob).json()] == ["Legacy Physics", "Bob Chemistry"]
              and [s["name"] for s in client.get("/subjects", headers=admin).json()] == ["Legacy Physics"])
        # The global topic is shared (with the same id here, because the library came from the first account); what stays private is the account's own notes.
        check("a user cannot read another account's private notes through the shared topic", client.get(f"/topics/{topic}/notes", headers=bob).json() == [])
        upload = client.post(f"/topics/{bob_topic}/resources", headers=bob, files={"file": ("bob.txt", b"bob's own notes about acids", "text/plain")})
        check("a user can upload to their own topic", upload.status_code == 201, upload.text)
        bob_resource = upload.json()["id"]
        admin_up = client.post(f"/topics/{topic}/resources", headers=admin, files={"file": ("admin.txt", b"admin notes about forces", "text/plain")})
        check("the admin can upload to theirs", admin_up.status_code == 201, admin_up.text)
        check("a user cannot download another account's file", client.get(f"/resources/{LEGACY_FILE}/download", headers=bob).status_code == 404
              and client.get(f"/resources/{admin_up.json()['id']}/download", headers=bob).status_code == 404
              and client.get(f"/resources/{bob_resource}/download", headers=admin).status_code == 404)
        check("files are stored in each account's own folder", Path(UPLOADS, "u2", bob_resource).is_file() and not Path(UPLOADS, "u1", bob_resource).exists()
              and Path(UPLOADS, "u1", admin_up.json()["id"]).is_file())
        deadline = time.time() + 40
        while time.time() < deadline:
            states = (client.get(f"/topics/{bob_topic}/resources", headers=bob).json()[0]["status"], client.get(f"/topics/{topic}/resources", headers=admin).json()[0]["status"])
            if states == ("extracted", "extracted") or "failed" in states:
                break
            time.sleep(0.5)
        check("the extraction worker serves every account", states == ("extracted", "extracted"), states)
        check("searching only finds your own text", [r["filename"] for r in client.get(f"/topics/{bob_topic}/search?q=acids", headers=bob).json()] == ["bob.txt"]
              and client.get(f"/topics/{bob_topic}/search?q=forces", headers=bob).json() == [])

        # ---- AI usage is recorded per account ----
        with userspace.as_user(2):
            study.log_run("accounts-check", "model", 1, 1, "ok")
        with study.connect_account() as db:
            mine_n = db.execute("SELECT count(*) FROM u2.ai_runs WHERE task = 'accounts-check'").fetchone()[0]
            theirs_n = db.execute("SELECT count(*) FROM u1.ai_runs WHERE task = 'accounts-check'").fetchone()[0]
        check("AI usage is recorded in the account's own schema", (mine_n, theirs_n) == (1, 0), (mine_n, theirs_n))

        # ---- teaching style is separate ----
        client.put("/style-profile", headers=admin, json={"content": "Admin style: short bullet points."})
        client.put("/style-profile", headers=bob, json={"content": "Bob style: long stories."})
        check("teaching style is separate", "Admin" in client.get("/style-profile", headers=admin).json()["content"]
              and "Bob" in client.get("/style-profile", headers=bob).json()["content"])

        # ---- your own profile ----
        check("changing a username needs the current password", client.put("/me/username", headers=bob, json={"username": "robert", "current_password": "nope-nope-nope"}).status_code == 403)
        check("a username cannot be taken", client.put("/me/username", headers=bob, json={"username": "ADMIN", "current_password": "bobs-long-password"}).status_code == 409)
        check("a user can rename themselves", client.put("/me/username", headers=bob, json={"username": "robert", "current_password": "bobs-long-password"}).json()["username"] == "robert")
        login("bob.smith", "bobs-long-password", 401)
        second = login("robert", "bobs-long-password")
        check("a user can change their password; other devices are signed out, this one stays",
              client.put("/me/password", headers=bob, json={"current_password": "bobs-long-password", "new_password": "bobs-new-long-password"}).status_code == 200
              and client.get("/session", headers=bob).status_code == 200 and client.get("/session", headers=second).status_code == 401)
        login("robert", "bobs-long-password", 401)
        bob = login("robert", "bobs-new-long-password")
        check("a short new password is refused", client.put("/me/password", headers=bob, json={"current_password": "bobs-new-long-password", "new_password": "short"}).status_code == 422)

        check("no picture to begin with", client.get("/me/avatar", headers=bob).status_code == 404)
        r = client.post("/me/avatar", headers=bob, files={"file": ("me.png", png(), "image/png")})
        check("a picture can be uploaded", r.status_code == 200 and r.json()["has_avatar"] is True and r.json()["avatar_version"] == 1, r.text)
        from PIL import Image
        got = client.get("/me/avatar", headers=bob)
        check("it is stored as a small square JPEG", got.headers["content-type"] == "image/jpeg" and Image.open(io.BytesIO(got.content)).size == (256, 256))
        check("a non-picture is refused", client.post("/me/avatar", headers=bob, files={"file": ("x.png", b"not an image", "image/png")}).status_code == 422)
        check("an oversized picture is refused", client.post("/me/avatar", headers=bob, files={"file": ("x.png", b"0" * (5 * 1024 * 1024 + 10), "image/png")}).status_code in (413, 422))
        check("others cannot see your picture, the admin can", client.get(f"/users/{client.get('/me', headers=bob).json()['id']}/avatar", headers=admin).status_code == 200
              and client.get("/users/1/avatar", headers=bob).status_code == 403)
        check("a picture can be removed", client.delete("/me/avatar", headers=bob).json()["has_avatar"] is False and client.get("/me/avatar", headers=bob).status_code == 404)

        # ---- the admin's powers ----
        users = {u["username"]: u for u in client.get("/users", headers=admin).json()}
        bob_id = users["robert"]["id"]
        check("the admin can reset another account's password and username", client.put(f"/users/{bob_id}", headers=admin, json={"username": "rob", "password": "reset-by-admin-123"}).json()["username"] == "rob"
              and client.get("/session", headers=bob).status_code == 401)
        bob = login("rob", "reset-by-admin-123")
        check("an admin cannot demote or remove the last admin", client.put("/users/1", headers=admin, json={"is_admin": False}).status_code == 409
              and client.delete("/users/1?confirm=admin", headers=admin).status_code == 409)
        check("an admin can add another admin", client.post("/users", headers=admin, json={"username": "second.admin", "password": "second-admin-password", "is_admin": True}).status_code == 201)
        check("removal needs the username as confirmation", client.delete(f"/users/{bob_id}", headers=admin).status_code == 422 and client.delete(f"/users/{bob_id}?confirm=wrong", headers=admin).status_code == 422)

        # ---- sign-in lock is per account ----
        for _ in range(5):
            login("second.admin", "wrong-wrong-wrong", 401)
        login("second.admin", "second-admin-password", 429)
        check("five wrong passwords lock only that account", login("admin", OLD_PASSWORD) is not None)

        # ---- removing an account removes everything it owns ----
        check("removing a user deletes their data and files", client.delete(f"/users/{bob_id}?confirm=ROB", headers=admin).status_code == 200)
        with study.connect_account() as db:
            check("the schema is gone", db.execute("SELECT count(*) FROM pg_namespace WHERE nspname = 'u2'").fetchone()[0] == 0)
        check("their files are gone", not Path(UPLOADS, "u2").exists())
        check("their session no longer works and they cannot sign in", client.get("/subjects", headers=bob).status_code == 401)
        login("rob", "reset-by-admin-123", 401)
        check("other accounts are untouched", [s["name"] for s in client.get("/subjects", headers=admin).json()] == ["Legacy Physics"])
        check("you cannot remove yourself", client.delete("/users/1?confirm=admin", headers=admin).status_code == 409)
        print("ALL ACCOUNT CHECKS PASSED")
finally:
    shutil.rmtree(UPLOADS, ignore_errors=True)
    os.environ["DATABASE_URL"] = BASE
    with psycopg.connect(BASE, autocommit=True) as admin_db:
        admin_db.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(DB)))
    print("CLEANUP: disposable database removed")
