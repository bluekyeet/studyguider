"""Which account a piece of work belongs to.

Every account has its own PostgreSQL schema (u1, u2, ...) holding all of its study data, and its own folder of uploaded files.
A request's account is held in a context variable set when the session is checked; `connect()` then opens connections whose
search_path is that account's schema, so no query can see another account's rows. Accounts themselves live in `public`.
Work started from a request on another thread must carry the context with it (`submit`, `spawn`); loops that serve every
account (extraction, lesson schedules) enter each account in turn with `as_user`.
"""
import contextvars
import os
import threading
from contextlib import contextmanager
from pathlib import Path

current_user = contextvars.ContextVar("current_user", default=None)     # account id, or None outside an account


def schema_name(user_id):
    return f"u{int(user_id)}"


@contextmanager
def as_user(user_id):
    token = current_user.set(user_id)
    try:
        yield
    finally:
        current_user.reset(token)


def search_path():
    """The schema the current account's connections use; the shared accounts schema when no account is active."""
    user_id = current_user.get()
    return schema_name(user_id) if user_id else "public"


def upload_base():
    return Path(os.environ.get("UPLOAD_DIR", "/data/uploads"))


def upload_root():
    """Uploaded files of the current account. Outside an account (tests, scripts) this is the shared base folder."""
    user_id = current_user.get()
    return upload_base() / schema_name(user_id) if user_id else upload_base()


def submit(executor, function, *args, **kwargs):
    """executor.submit that keeps the caller's account."""
    return executor.submit(contextvars.copy_context().run, function, *args, **kwargs)


def spawn(target, *args, daemon=True):
    """Start a thread that keeps the caller's account."""
    thread = threading.Thread(target=contextvars.copy_context().run, args=(target, *args), daemon=daemon)
    thread.start()
    return thread


def each_user(user_ids, function):
    """Run `function` once inside every account. Returns True if any call returned a truthy value; one account failing never stops the rest."""
    progressed = False
    errors = []
    for user_id in user_ids():
        try:
            with as_user(user_id):
                progressed = bool(function()) or progressed
        except Exception as error:      # noqa: BLE001 - reported after every account has had its turn
            errors.append(error)
    if errors:
        raise errors[0]
    return progressed
