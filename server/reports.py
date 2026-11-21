"""Problem reports from a test system (docs/test-system.md).

A test system runs with STUDYGUIDER_TEST_SYSTEM=yes. The website and the test build of the Android app then show a "Report a
problem" button that sends what the tester wrote, where they were, their device and app version, the app's recent errors and an
optional screenshot. Reports live in the shared accounts schema: testers see their own, administrators see and close all of them.
On any other installation there is no button and the routes answer 404.
"""
import io
import json
import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field

SCREENSHOT_MAX_BYTES = 8 * 1024 * 1024
CONTEXT_MAX_CHARS = 200_000
STATUSES = ("open", "fixed", "wontfix")


def is_test_system():
    return os.environ.get("STUDYGUIDER_TEST_SYSTEM", "").lower() in {"1", "yes", "true"}


def create_report_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS problem_reports (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id bigint REFERENCES users(id) ON DELETE SET NULL, username text NOT NULL,
        client text NOT NULL, app_version text NOT NULL DEFAULT '', device text NOT NULL DEFAULT '', screen text NOT NULL DEFAULT '',
        description text NOT NULL, context jsonb NOT NULL DEFAULT '{}'::jsonb, screenshot bytea,
        status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'fixed', 'wontfix')), note text NOT NULL DEFAULT '',
        created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())""")


class ReportUpdate(BaseModel):
    status: str = Field(pattern="^(open|fixed|wontfix)$")
    note: str = Field(default="", max_length=5000)


def png_screenshot(data):
    """The upload as a PNG no wider than 1600 px, or 422 when it is not a picture."""
    from PIL import Image, UnidentifiedImageError
    if len(data) > SCREENSHOT_MAX_BYTES:
        raise HTTPException(413, "Choose a screenshot under 8 MB")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        raise HTTPException(422, "The screenshot is not a readable picture") from None
    image.thumbnail((1600, 1600 * 4))
    out = io.BytesIO()
    image.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def report_router(connect_account, authorised, admin_only):
    router = APIRouter()

    def test_system_only():
        if not is_test_system():
            raise HTTPException(404, "Not Found")

    @router.get("/test-system")
    def test_system():
        """Whether this is a test system, asked before sign-in so the sign-in page can say so."""
        return {"test_system": is_test_system()}

    @router.post("/reports", status_code=201, dependencies=[Depends(test_system_only)])
    def send_report(user: dict = Depends(authorised), description: str = Form(..., max_length=5000), client: str = Form(..., max_length=20),
                    screen: str = Form("", max_length=300), app_version: str = Form("", max_length=60), device: str = Form("", max_length=300),
                    context: str = Form("{}", max_length=CONTEXT_MAX_CHARS), screenshot: UploadFile | None = File(None)):
        if not description.strip():
            raise HTTPException(422, "Say what went wrong")
        try:
            details = json.loads(context or "{}")
        except ValueError:
            details = {"unparsed": context}
        picture = png_screenshot(screenshot.file.read(SCREENSHOT_MAX_BYTES + 1)) if screenshot and screenshot.filename else None
        with connect_account() as db:
            row = db.execute("""INSERT INTO problem_reports (user_id, username, client, app_version, device, screen, description, context, screenshot)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s) RETURNING id, created_at""",
                (user["id"], user["username"], client.strip(), app_version.strip(), device.strip(), screen.strip(), description.strip(),
                 json.dumps(details), picture)).fetchone()
        return {"id": row[0], "created_at": row[1], "status": "open"}

    @router.get("/reports", dependencies=[Depends(test_system_only)])
    def list_reports(user: dict = Depends(authorised), status: str | None = Query(default=None, pattern="^(open|fixed|wontfix)$")):
        """Newest first. Testers get their own; administrators get everyone's."""
        with connect_account() as db:
            rows = db.execute("""SELECT id, username, client, app_version, device, screen, description, context, screenshot IS NOT NULL,
                    status, note, created_at, updated_at FROM problem_reports
                WHERE (%s OR user_id = %s) AND (%s::text IS NULL OR status = %s) ORDER BY id DESC LIMIT 500""",
                (user["is_admin"], user["id"], status, status)).fetchall()
        keys = ("id", "username", "client", "app_version", "device", "screen", "description", "context", "has_screenshot",
                "status", "note", "created_at", "updated_at")
        return [dict(zip(keys, row)) for row in rows]

    @router.get("/reports/{report_id}/screenshot", dependencies=[Depends(test_system_only)])
    def report_screenshot(report_id: int, user: dict = Depends(authorised)):
        with connect_account() as db:
            row = db.execute("SELECT screenshot FROM problem_reports WHERE id = %s AND (%s OR user_id = %s)",
                             (report_id, user["is_admin"], user["id"])).fetchone()
        if not row or row[0] is None:
            raise HTTPException(404, "No screenshot")
        return Response(bytes(row[0]), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})

    @router.put("/reports/{report_id}", dependencies=[Depends(test_system_only)])
    def update_report(report_id: int, body: ReportUpdate, user: dict = Depends(admin_only)):
        with connect_account() as db:
            row = db.execute("UPDATE problem_reports SET status = %s, note = %s, updated_at = now() WHERE id = %s RETURNING id, status, note",
                             (body.status, body.note.strip(), report_id)).fetchone()
        if not row:
            raise HTTPException(404, "Report not found")
        return {"id": row[0], "status": row[1], "note": row[2]}

    return router
