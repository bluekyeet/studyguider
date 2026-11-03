"""Accounts: sign-in, sessions, profile (username, password, picture) and admin-only user management.

Accounts live in the shared `public` schema; each account's study data lives in its own schema (see userspace.py).
Admins can add and remove accounts and reset another account's username or password; everyone can change their own.
"""
import hashlib
import io
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from psycopg import errors as pg_errors

import userspace

log = logging.getLogger("uvicorn.error")

USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,31}$")
MIN_PASSWORD = 12
LOCK_AFTER, LOCK_MINUTES, SESSION_DAYS = 5, 15, 30
AVATAR_SIDE, AVATAR_MAX_BYTES, AVATAR_MAX_PIXELS = 256, 5 * 1024 * 1024, 40_000_000
ACCOUNT_TABLES = ("users", "sessions")


def clean_username(value):
    name = str(value or "").strip()
    if not USERNAME.match(name):
        raise HTTPException(422, "Usernames are 3 to 32 characters: letters, numbers, dots, dashes and underscores, starting with a letter or number")
    return name


def check_password(value):
    if not isinstance(value, str) or not MIN_PASSWORD <= len(value) <= 1024:
        raise HTTPException(422, f"Passwords must be at least {MIN_PASSWORD} characters")
    return value


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


class UsernameChange(BaseModel):
    username: str = Field(max_length=64)
    current_password: str = Field(min_length=1, max_length=1024)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(max_length=1024)


class NewUser(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=1024)
    is_admin: bool = False


class UserEdit(BaseModel):
    username: str | None = Field(default=None, max_length=64)
    password: str | None = Field(default=None, max_length=1024)
    is_admin: bool | None = None


def create_account_tables(db):
    db.execute("""CREATE TABLE IF NOT EXISTS users (
        id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        username text NOT NULL,
        password_hash text NOT NULL,
        is_admin boolean NOT NULL DEFAULT false,
        failed_logins integer NOT NULL DEFAULT 0,
        locked_until timestamptz,
        avatar bytea,
        avatar_version integer NOT NULL DEFAULT 0,
        created_at timestamptz NOT NULL DEFAULT now())""")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_idx ON users (lower(username))")
    db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash text PRIMARY KEY, expires timestamptz NOT NULL)")
    db.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id bigint REFERENCES users(id) ON DELETE CASCADE")
    db.execute("CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions (user_id)")


def migrate_legacy(db, hasher):
    """First start after the move to accounts: the single-password installation becomes the first admin account.

    Its tables are moved (not copied) into that account's schema in the caller's transaction, so nothing is lost
    and nothing is left behind in the shared schema. Returns the new account id, or None if there was nothing to do.
    """
    if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return None
    tables = [r[0] for r in db.execute("""SELECT tablename FROM pg_tables WHERE schemaname = 'public'
        AND tablename <> ALL(%s)""", (list(ACCOUNT_TABLES),)).fetchall()]
    password = None
    if "settings" in tables:
        row = db.execute("SELECT value FROM settings WHERE key = 'password_hash'").fetchone()
        password = row[0] if row else None
    if not tables and not password:
        return None             # a fresh installation: the first admin is created by set_password.py
    admin = db.execute("INSERT INTO users (username, password_hash, is_admin) VALUES ('admin', %s, true) RETURNING id",
                       (password or hasher.hash(secrets.token_urlsafe(32)),)).fetchone()[0]
    schema = userspace.schema_name(admin)
    db.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    for table in tables:
        db.execute(f'ALTER TABLE public."{table}" SET SCHEMA "{schema}"')
    if "settings" in tables:
        db.execute(f"DELETE FROM \"{schema}\".settings WHERE key IN ('password_hash', 'login_failures', 'locked_until')")
    db.execute("UPDATE sessions SET user_id = %s WHERE user_id IS NULL", (admin,))
    log.warning("Moved the existing installation into account %s (admin) with %s tables", admin, len(tables))
    return admin


def move_legacy_files(base):
    """Move uploaded files from the old shared folder into the first account's folder. Idempotent."""
    target = base / "u1"
    if not base.is_dir():
        return 0
    moved = 0
    for entry in list(base.iterdir()):
        if re.fullmatch(r"u\d+", entry.name):
            continue
        target.mkdir(parents=True, exist_ok=True)
        entry.rename(target / entry.name)
        moved += 1
    return moved


def user_json(row):
    return {"id": row[0], "username": row[1], "is_admin": row[2], "has_avatar": row[4], "avatar_version": row[3]}


def make_auth(connect_account):
    """The sign-in check every protected route uses, and the stricter admin check."""
    def lookup(token):
        with connect_account() as db:
            return db.execute("""SELECT u.id, u.username, u.is_admin, u.avatar_version, u.avatar IS NOT NULL
                FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = %s AND s.expires > now()""",
                              (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()

    async def authorised(request: Request, authorization: str = Header(default="")):
        token = authorization[7:] if authorization.startswith("Bearer ") else request.cookies.get("studyguider_session", "")
        if not token:
            raise HTTPException(401, "Authentication required")
        if not authorization.startswith("Bearer ") and request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") == "cross-site" or (origin and urlsplit(origin).netloc != request.headers.get("host")):
                raise HTTPException(403, "Cross-site request rejected")
        row = await run_in_threadpool(lookup, token)
        if not row:
            raise HTTPException(401, "Invalid or expired session")
        # Set here, in the request's own task: the route that runs next (on a worker thread) inherits it.
        userspace.current_user.set(row[0])
        user = {**user_json(row), "token": token}
        request.state.user = user
        return user

    async def admin_only(user: dict = Depends(authorised)):
        if not user["is_admin"]:
            raise HTTPException(403, "Only an administrator can do this")
        return user

    return authorised, admin_only


def process_avatar(data):
    """Square-crop and shrink an uploaded picture to a small JPEG. Everything else about the upload (metadata, animation, size) is dropped."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    if not data or len(data) > AVATAR_MAX_BYTES:
        raise HTTPException(413 if data else 422, "Choose a picture under 5 MB")
    try:
        image = Image.open(io.BytesIO(data))
        if image.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
            raise HTTPException(422, "Use a JPEG, PNG, WebP or GIF picture")
        if image.width * image.height > AVATAR_MAX_PIXELS:
            raise HTTPException(422, "That picture is too large")
        image.load()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        raise HTTPException(422, "That file is not a readable picture") from None
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        flat = Image.new("RGB", image.size, "white")
        flat.paste(image, mask=image.getchannel("A"))
        image = flat
    else:
        image = image.convert("RGB")
    image = ImageOps.fit(image, (AVATAR_SIDE, AVATAR_SIDE), method=Image.LANCZOS, centering=(0.5, 0.4))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=86, optimize=True)
    return out.getvalue()


def accounts_router(connect_account, authorised, admin_only, hasher, provision, deprovision):
    router = APIRouter()
    dummy_hash = hasher.hash("not-a-real-password")       # so an unknown username takes as long to refuse as a wrong password

    def verify(stored, password):
        try:
            return hasher.verify(stored, password)
        except (VerifyMismatchError, InvalidHashError):
            return False

    # ---- sign in and out -----------------------------------------------------------------------
    @router.post("/login")
    def login(body: Login, response: Response, request: Request):
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (origin and urlsplit(origin).netloc != request.headers.get("host")):
            raise HTTPException(403, "Cross-site login rejected")
        now = datetime.now(timezone.utc)
        with connect_account() as db:
            row = db.execute("""SELECT id, username, password_hash, is_admin, failed_logins, locked_until, avatar_version, avatar IS NOT NULL
                FROM users WHERE lower(username) = lower(%s) FOR UPDATE""", (body.username.strip(),)).fetchone()
            if row and row[5] and row[5] > now:
                raise HTTPException(429, "Login temporarily locked")
            if not verify(row[2] if row else dummy_hash, body.password) or not row:
                if row:
                    failures = row[4] + 1
                    locked = now + timedelta(minutes=LOCK_MINUTES) if failures >= LOCK_AFTER else None
                    db.execute("UPDATE users SET failed_logins = %s, locked_until = %s WHERE id = %s", (0 if locked else failures, locked, row[0]))
                    db.commit()
                raise HTTPException(401, "Invalid credentials")
            db.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = %s", (row[0],))
            db.execute("DELETE FROM sessions WHERE expires <= now()")
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO sessions (token_hash, expires, user_id) VALUES (%s, %s, %s)",
                       (hashlib.sha256(token.encode()).hexdigest(), now + timedelta(days=SESSION_DAYS), row[0]))
        response.set_cookie("studyguider_session", token, max_age=SESSION_DAYS * 86400, httponly=True,
                            secure=request.url.scheme == "https", samesite="strict", path="/")
        return {"token": token, "expires_in": SESSION_DAYS * 86400,
                "user": {"id": row[0], "username": row[1], "is_admin": row[3], "has_avatar": row[7], "avatar_version": row[6]}}

    @router.post("/logout")
    def logout(response: Response, user: dict = Depends(authorised)):
        with connect_account() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = %s", (hashlib.sha256(user["token"].encode()).hexdigest(),))
        response.delete_cookie("studyguider_session", path="/", httponly=True, samesite="strict")
        return {"status": "ok"}

    def public(user):
        return {k: user[k] for k in ("id", "username", "is_admin", "has_avatar", "avatar_version")}

    @router.get("/session")
    def session(user: dict = Depends(authorised)):
        return {"authenticated": True, "user": public(user)}

    @router.get("/me")
    def me(user: dict = Depends(authorised)):
        return public(user)

    # ---- your own account ----------------------------------------------------------------------
    def verified_own_row(db, user, current_password):
        row = db.execute("SELECT password_hash FROM users WHERE id = %s FOR UPDATE", (user["id"],)).fetchone()
        if not row or not verify(row[0], current_password):
            raise HTTPException(403, "Your current password is not correct")

    @router.put("/me/username")
    def change_username(body: UsernameChange, user: dict = Depends(authorised)):
        name = clean_username(body.username)
        with connect_account() as db:
            verified_own_row(db, user, body.current_password)
            try:
                db.execute("UPDATE users SET username = %s WHERE id = %s", (name, user["id"]))
            except pg_errors.UniqueViolation:
                raise HTTPException(409, "That username is taken") from None
        return {**public(user), "username": name}

    @router.put("/me/password")
    def change_password(body: PasswordChange, user: dict = Depends(authorised)):
        check_password(body.new_password)
        with connect_account() as db:
            verified_own_row(db, user, body.current_password)
            db.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hasher.hash(body.new_password), user["id"]))
            # Every other device is signed out; this one stays.
            db.execute("DELETE FROM sessions WHERE user_id = %s AND token_hash <> %s",
                       (user["id"], hashlib.sha256(user["token"].encode()).hexdigest()))
        return {"status": "changed"}

    def send_avatar(db, user_id):
        row = db.execute("SELECT avatar, avatar_version FROM users WHERE id = %s", (user_id,)).fetchone()
        if not row or row[0] is None:
            raise HTTPException(404, "No profile picture")
        return Response(bytes(row[0]), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=0, must-revalidate", "ETag": f'"{user_id}-{row[1]}"'})

    @router.get("/me/avatar")
    def my_avatar(user: dict = Depends(authorised)):
        with connect_account() as db:
            return send_avatar(db, user["id"])

    @router.post("/me/avatar")
    async def set_my_avatar(file: UploadFile = File(...), user: dict = Depends(authorised)):
        data = await file.read(AVATAR_MAX_BYTES + 1)
        picture = await run_in_threadpool(process_avatar, data)
        return await run_in_threadpool(store_avatar, user, picture)

    def store_avatar(user, picture):
        with connect_account() as db:
            version = db.execute("UPDATE users SET avatar = %s, avatar_version = avatar_version + 1 WHERE id = %s RETURNING avatar_version", (picture, user["id"])).fetchone()[0]
        return {**public(user), "has_avatar": True, "avatar_version": version}

    @router.delete("/me/avatar")
    def remove_my_avatar(user: dict = Depends(authorised)):
        with connect_account() as db:
            version = db.execute("UPDATE users SET avatar = NULL, avatar_version = avatar_version + 1 WHERE id = %s RETURNING avatar_version", (user["id"],)).fetchone()[0]
        return {**public(user), "has_avatar": False, "avatar_version": version}

    # ---- administration ------------------------------------------------------------------------
    @router.get("/users")
    def users(admin: dict = Depends(admin_only)):
        with connect_account() as db:
            rows = db.execute("SELECT id, username, is_admin, avatar_version, avatar IS NOT NULL, created_at FROM users ORDER BY lower(username)").fetchall()
        return [{**user_json(r), "created_at": r[5]} for r in rows]

    @router.get("/users/{user_id}/avatar")
    def user_avatar(user_id: int, user: dict = Depends(authorised)):
        if user_id != user["id"] and not user["is_admin"]:
            raise HTTPException(403, "Only an administrator can see other accounts")
        with connect_account() as db:
            return send_avatar(db, user_id)

    @router.post("/users", status_code=201)
    def add_user(body: NewUser, admin: dict = Depends(admin_only)):
        name, password = clean_username(body.username), check_password(body.password)
        with connect_account() as db:
            try:
                user_id = db.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s) RETURNING id",
                                     (name, hasher.hash(password), body.is_admin)).fetchone()[0]
            except pg_errors.UniqueViolation:
                raise HTTPException(409, "That username is taken") from None
        try:
            provision(user_id)
        except Exception:
            log.exception("Could not set up the new account %s", user_id)
            with connect_account() as db:
                db.execute("DELETE FROM users WHERE id = %s", (user_id,))
            raise HTTPException(500, "The account could not be set up; nothing was created") from None
        return {"id": user_id, "username": name, "is_admin": body.is_admin, "has_avatar": False, "avatar_version": 0}

    def last_admin_guard(db, user_id, losing_admin):
        """Lock the admin rows and refuse a change that would leave nobody able to manage accounts."""
        admins = [r[0] for r in db.execute("SELECT id FROM users WHERE is_admin ORDER BY id FOR UPDATE").fetchall()]
        if losing_admin and admins == [user_id]:
            raise HTTPException(409, "There must always be at least one administrator")

    @router.put("/users/{user_id}")
    def edit_user(user_id: int, body: UserEdit, admin: dict = Depends(admin_only)):
        name = clean_username(body.username) if body.username is not None else None
        password = check_password(body.password) if body.password is not None else None
        with connect_account() as db:
            row = db.execute("SELECT is_admin FROM users WHERE id = %s FOR UPDATE", (user_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Account not found")
            if body.is_admin is False and row[0]:
                last_admin_guard(db, user_id, True)
            try:
                if name is not None:
                    db.execute("UPDATE users SET username = %s WHERE id = %s", (name, user_id))
                if body.is_admin is not None:
                    db.execute("UPDATE users SET is_admin = %s WHERE id = %s", (body.is_admin, user_id))
                if password is not None:
                    db.execute("UPDATE users SET password_hash = %s, failed_logins = 0, locked_until = NULL WHERE id = %s", (hasher.hash(password), user_id))
                    db.execute("DELETE FROM sessions WHERE user_id = %s AND token_hash <> %s", (user_id, hashlib.sha256(admin["token"].encode()).hexdigest()))
            except pg_errors.UniqueViolation:
                raise HTTPException(409, "That username is taken") from None
            if body.is_admin is False:
                db.execute("DELETE FROM sessions WHERE user_id = %s AND token_hash <> %s", (user_id, hashlib.sha256(admin["token"].encode()).hexdigest()))
            out = db.execute("SELECT id, username, is_admin, avatar_version, avatar IS NOT NULL FROM users WHERE id = %s", (user_id,)).fetchone()
        return user_json(out)

    @router.delete("/users/{user_id}")
    def remove_user(user_id: int, confirm: str = "", admin: dict = Depends(admin_only)):
        """Remove an account and everything it owns. The caller must repeat the username to confirm; this cannot be undone."""
        if user_id == admin["id"]:
            raise HTTPException(409, "You cannot remove your own account")
        with connect_account() as db:
            row = db.execute("SELECT username, is_admin FROM users WHERE id = %s FOR UPDATE", (user_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Account not found")
            if confirm.strip().lower() != row[0].lower():
                raise HTTPException(422, "Type the account's username to confirm removing it and all of its data")
            if row[1]:
                last_admin_guard(db, user_id, True)
            db.execute("DELETE FROM users WHERE id = %s", (user_id,))      # its sessions go with it
        try:
            deprovision(user_id)
        except Exception:
            log.exception("The account %s was removed but its data could not be fully deleted", user_id)
            raise HTTPException(500, "The account was removed, but some of its data could not be deleted. Check the server logs.") from None
        return {"status": "removed", "username": row[0]}

    return router
