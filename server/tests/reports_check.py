"""Real PostgreSQL checks for problem reports on a test system: off unless STUDYGUIDER_TEST_SYSTEM=yes, any account can send one,
each tester sees their own, an administrator sees and closes all of them.

Run only against a disposable stack (it creates and drops its own database inside that server):
  docker compose exec -T -e DISPOSABLE_TEST_DATABASE=yes api python - < server/tests/reports_check.py
"""
import io
import json
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
DB = "reports_check_" + uuid.uuid4().hex[:12]
with psycopg.connect(BASE, autocommit=True) as admin_db:
    admin_db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB)))
os.environ["DATABASE_URL"] = make_conninfo(BASE, dbname=DB)
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="reports_check_")

from fastapi.testclient import TestClient     # noqa: E402
from PIL import Image                         # noqa: E402

import app as study                          # noqa: E402

PASSWORD = "reports-password-12"


def check(label, condition, detail=""):
    assert condition, f"FAIL {label} {detail}"
    print("PASS", label)


def png():
    out = io.BytesIO()
    Image.new("RGB", (40, 30), "red").save(out, format="PNG")
    return out.getvalue()


try:
    with study.connect_account() as db:
        study.init_schema(db)
        db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash text PRIMARY KEY, expires timestamptz NOT NULL)")
        db.execute("INSERT INTO settings VALUES ('password_hash', %s)", (study.hasher.hash(PASSWORD),))

    with TestClient(study.app) as client:
        def login(username, password):
            r = client.post("/login", json={"username": username, "password": password})
            assert r.status_code == 200, r.text
            client.cookies.clear()
            return {"Authorization": "Bearer " + r.json()["token"]}
        admin = login("admin", PASSWORD)
        assert client.post("/users", headers=admin, json={"username": "tester", "password": PASSWORD}).status_code == 201
        tester = login("tester", PASSWORD)
        report = {"description": "The Next button does nothing", "screen": "Review", "client": "android", "app_version": "1.1.1-test",
                  "device": "Pixel 8, Android 16", "context": json.dumps({"errors": ["GET /review-plan 500"]})}

        os.environ.pop("STUDYGUIDER_TEST_SYSTEM", None)
        check("a normal system says it is not a test system", client.get("/test-system").json() == {"test_system": False})
        check("a normal system takes no reports", client.post("/reports", headers=tester, data=report).status_code == 404)

        os.environ["STUDYGUIDER_TEST_SYSTEM"] = "yes"
        check("a test system says so, before sign-in", client.get("/test-system").json()["test_system"] is True)
        check("sending a report needs an account", client.post("/reports", data=report).status_code == 401)
        sent = client.post("/reports", headers=tester, data=report, files={"screenshot": ("screen.png", png(), "image/png")})
        check("a tester sends a report with a screenshot", sent.status_code == 201, sent.text)
        own = client.post("/reports", headers=admin, data={**report, "description": "Admin's own note", "client": "web"})
        check("a report without a screenshot is fine too", own.status_code == 201, own.text)
        check("an empty description is refused", client.post("/reports", headers=tester, data={**report, "description": "  "}).status_code == 422)
        check("a screenshot must be a picture", client.post("/reports", headers=tester, data=report,
                                                             files={"screenshot": ("x.png", b"not a picture", "image/png")}).status_code == 422)

        mine = client.get("/reports", headers=tester).json()
        check("a tester sees only their own reports", [r["description"] for r in mine] == ["The Next button does nothing"], mine)
        row = mine[0]
        check("a report keeps who, where and what", (row["username"], row["screen"], row["client"], row["device"], row["status"], row["has_screenshot"],
                                                     row["context"]) == ("tester", "Review", "android", "Pixel 8, Android 16", "open", True,
                                                                         {"errors": ["GET /review-plan 500"]}), row)
        everything = client.get("/reports", headers=admin).json()
        check("an administrator sees every report, newest first", [r["description"] for r in everything] == ["Admin's own note", "The Next button does nothing"])
        shot = client.get(f"/reports/{row['id']}/screenshot", headers=tester)
        check("the screenshot can be fetched back as a PNG", shot.status_code == 200 and shot.content[:4] == b"\x89PNG", shot.status_code)
        check("a tester cannot see someone else's screenshot or report",
              client.get(f"/reports/{everything[0]['id']}/screenshot", headers=tester).status_code == 404)
        check("a tester cannot close a report", client.put(f"/reports/{row['id']}", headers=tester, json={"status": "fixed"}).status_code == 403)
        closed = client.put(f"/reports/{row['id']}", headers=admin, json={"status": "fixed", "note": "Fixed in c1d1abd"})
        check("an administrator marks a report fixed with a note", closed.status_code == 200 and closed.json()["status"] == "fixed", closed.text)
        check("open reports can be listed on their own", [r["id"] for r in client.get("/reports?status=open", headers=admin).json()] == [everything[0]["id"]])
finally:
    with psycopg.connect(BASE, autocommit=True) as admin_db:
        admin_db.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(DB)))
    print("CLEANUP: disposable database removed")
