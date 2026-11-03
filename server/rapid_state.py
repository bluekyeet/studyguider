"""Shared by the exam, marking and rapid-session code: results stay hidden while a rapid session is open."""
import threading

from fastapi import HTTPException

# The background marker runs on its own threads and sets this; request threads never do.
bypass = threading.local()


def is_open(db, exam_id):
    """True while the exam is a rapid session that has not been ended (regardless of who is asking)."""
    return db.execute("SELECT 1 FROM rapid_sessions WHERE exam_id = %s AND ended_at IS NULL", (exam_id,)).fetchone() is not None


def blindfolded(db, exam_id):
    """True when a request must not see results: the session is open and this is not the background marker."""
    if getattr(bypass, "on", False):
        return False
    return is_open(db, exam_id)


def refuse_if_blind(db, exam_id):
    if blindfolded(db, exam_id):
        raise HTTPException(409, "Results are hidden until you end the rapid session")
