"""Fill a fresh test system with two accounts and made-up study material (docs/test-system.md).

Runs inside the test stack's api container, never against the real one:
  docker compose -f compose.test.yaml exec -T -e STUDYGUIDER_SEED_OK=yes api python - < scripts/seed_test_system.py
Prints the two sign-ins as KEY=value lines. Does nothing when the test system already has accounts.
Everything here is invented: no real papers, notes or people.
"""
import json
import os
import secrets
import sys
import urllib.request
import uuid
from datetime import date, timedelta

assert os.environ.get("STUDYGUIDER_TEST_SYSTEM") == "yes", "refusing: this is not a test system"
assert os.environ.get("STUDYGUIDER_SEED_OK") == "yes", "refusing: run through scripts/test-system.sh"

import pymupdf
from accounts import create_account_tables
from app import connect_account, hasher, provision_account

BASE = "http://127.0.0.1:8000"


def call(method, path, token="", body=None, files=None):
    headers = {"Authorization": "Bearer " + token} if token else {}
    data = None
    if files:
        boundary = uuid.uuid4().hex
        parts = []
        for name, (filename, content, kind) in files.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\nContent-Type: {kind}\r\n\r\n'.encode() + content + b"\r\n")
        for name, value in (body or {}).items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        data = b"".join(parts) + f"--{boundary}--\r\n".encode()
        headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read()
    return json.loads(text) if text else None


def notes_pdf(title, paragraphs):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 545, 800), title + "\n\n" + "\n\n".join(paragraphs), fontsize=11)
    return document.tobytes()


def seed(token):
    today = date.today()
    # An NCEA subject: one Topic per Standard, each a Learning topic, with invented notes and an exam in six weeks.
    maths = call("POST", "/subjects", token, {"name": "Mathematics", "level": 1})["id"]
    standards = [(91027, "Apply algebraic procedures in solving problems", "Algebra", [
        "Expanding brackets: a(b + c) = ab + ac. Factorising reverses this, for example x^2 + 5x + 6 = (x + 2)(x + 3).",
        "To solve a linear equation, do the same thing to both sides until x is alone: 3x + 4 = 19 gives 3x = 15, so x = 5.",
        "Quadratic equations in factorised form are solved by setting each factor to zero: (x - 2)(x + 7) = 0 gives x = 2 or x = -7."]),
        (91028, "Investigate relationships between tables, equations and graphs", "Graphs", [
        "A straight line y = mx + c has gradient m and crosses the y-axis at c. A gradient of 2 means up 2 for every 1 across.",
        "A table of values with a constant difference between y values is linear; a constant second difference means quadratic.",
        "The graph of y = x^2 is a parabola with its vertex at the origin; y = (x - 3)^2 moves it 3 to the right."])]
    for number, title, name, paragraphs in standards:
        call("PUT", f"/standards/{number}", token, {"title": title})
        topic = call("POST", f"/subjects/{maths}/topics", token, {"name": name})["id"]
        call("PUT", f"/topics/{topic}/standards/{number}", token)
        call("POST", "/learning-topics", token, {"topic_id": topic})
        call("POST", f"/topics/{topic}/resources", token, {"category": "extra"},
             files={"file": (f"{name} notes (sample).pdf", notes_pdf(f"{name}: sample notes", paragraphs), "application/pdf")})
        call("POST", f"/topics/{topic}/notes", token, {"content": f"Sample note: revise {name.lower()} before the exam."})
    call("POST", f"/subjects/{maths}/assessments", token, {"title": "End-of-year exam", "kind": "exam", "standard_number": 91027,
                                                           "due_date": str(today + timedelta(days=42)), "credits": 4})
    # A university paper with Learning outcomes and dated, weighted Assessments, one of them next week.
    programme = call("POST", "/programmes", token, {"kind": "university", "institution": "other", "name": "Sample degree", "year": today.year})["id"]
    paper = call("POST", "/papers", token, {
        "programme_id": programme, "code": "TEST101", "title": "Introduction to Programming (sample)", "points": 15, "level": 5,
        "grade_scale": "aut9", "pass_rule": "Attempt all assessments and achieve an overall C-.",
        "outcomes": [{"code": "LO1", "title": "Write and debug small programs"}, {"code": "LO2", "title": "Use selection and iteration"}],
        "assessments": [{"title": "Practical test", "kind": "test", "weight_pct": 40, "due_date": str(today + timedelta(days=7)), "outcome_codes": ["LO1"]},
                        {"title": "Final exam", "kind": "exam", "weight_pct": 60, "due_date": str(today + timedelta(days=60)), "outcome_codes": ["LO1", "LO2"]}]})
    for topic in call("GET", f"/subjects/{paper['subject_id']}/topics", token):
        call("POST", "/learning-topics", token, {"topic_id": topic["id"]})


with connect_account() as db:
    create_account_tables(db)
    if db.execute("SELECT count(*) FROM users").fetchone()[0]:
        print("SEEDED=already", file=sys.stderr)
        raise SystemExit(0)
    accounts = [("tester", True), ("learner", False)]
    passwords = {name: "test-" + secrets.token_urlsafe(9) for name, _ in accounts}
    ids = {name: db.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s) RETURNING id",
                            (name, hasher.hash(passwords[name]), admin)).fetchone()[0] for name, admin in accounts}
for user_id in ids.values():
    provision_account(user_id)
for name, _ in accounts:
    seed(call("POST", "/login", body={"username": name, "password": passwords[name]})["token"])
    print(f"{name.upper()}_PASSWORD={passwords[name]}")
