"""Background extraction using the existing resources status column."""

import logging
import threading

import userspace
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


MAX_ATTEMPTS = 8
# Counts the failure and schedules the next automatic try: 30 s, 1 min, 2 min ... capped at an hour.
RETRY_SET = "attempts = attempts + 1, retry_at = now() + make_interval(secs => least(30 * power(2, attempts), 3600))"


def requeue_failed(db):
    """Put failed resources whose wait is over back in the queue; after MAX_ATTEMPTS they wait for a manual Retry."""
    return db.execute(
        "UPDATE resources SET status = 'pending' WHERE status = 'failed' AND attempts < %s AND (retry_at IS NULL OR retry_at <= now())",
        (MAX_ATTEMPTS,),
    ).rowcount


def worker_router(connect, authorised):
    router = APIRouter(dependencies=[Depends(authorised)])

    @router.post("/resources/{resource_id}/retry", status_code=202)
    def retry_resource(resource_id: UUID):
        with connect() as db:
            row = db.execute(
                "UPDATE resources SET status = 'pending', error = NULL, attempts = 0, retry_at = NULL WHERE id = %s AND status = 'failed' RETURNING id",
                (resource_id,),
            ).fetchone()
            if row is None:
                row = db.execute("SELECT status FROM resources WHERE id = %s", (resource_id,)).fetchone()
                if row is None:
                    raise HTTPException(404, "Resource not found")
                raise HTTPException(409, "Only failed resources can be retried")
        return {"id": resource_id, "status": "pending"}

    return router


def process_one(connect, extract):
    """Claim one pending resource, then invoke extract(id); return whether claimed."""
    with connect() as db:
        requeue_failed(db)
        row = db.execute("""
            UPDATE resources SET status = 'extracting'
            WHERE id = (
                SELECT id FROM resources WHERE status = 'pending'
                ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1
            ) RETURNING id
        """).fetchone()
    if row is None:
        return False
    resource_id = row[0]
    try:
        extract(resource_id)
    except Exception as exc:
        logger.exception("Resource extraction failed: %s", resource_id)
        with connect() as db:
            db.execute("UPDATE resources SET status = 'failed', error = %s, " + RETRY_SET + " WHERE id = %s AND status = 'extracting'",
                       (str(exc)[:2000], resource_id))
    return True


def recover_interrupted(connect, resource_ids=None):
    """Requeue claims after all workers have stopped, optionally only for given IDs.

    Stop and join workers on every instance before calling, and prevent new ones
    starting until recovery completes. The caller must establish this externally;
    neither a status nor a resource ID proves that an extraction has stopped.
    Omit resource_ids to retain the original all-claims recovery behaviour.
    """
    # ponytail: status has no fencing; online recovery needs leases and fenced extraction writes.
    if resource_ids is not None:
        resource_ids = list(resource_ids)
        if not resource_ids:
            return 0
    with connect() as db:
        if resource_ids is not None:
            return db.execute(
                "UPDATE resources SET status = 'pending' WHERE status = 'extracting' AND id = ANY(%s)",
                (resource_ids,),
            ).rowcount
        return db.execute("UPDATE resources SET status = 'pending' WHERE status = 'extracting'").rowcount


def start_worker(connect, extract, interval=5, user_ids=None):
    """Start a polling worker; caller stops it with stop.set() and thread.join()."""
    if interval <= 0:
        raise ValueError("interval must be positive")
    stop = threading.Event()

    def run():
        while not stop.is_set():
            try:
                if user_ids is not None:
                    progressed = userspace.each_user(user_ids, lambda: process_one(connect, extract))
                else:
                    progressed = process_one(connect, extract)
                if progressed:
                    continue
            except Exception:
                logger.exception("Extraction worker database error")
            stop.wait(interval)

    thread = threading.Thread(target=run, name="resource-extraction", daemon=True)
    thread.start()
    return stop, thread
