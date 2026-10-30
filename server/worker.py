"""Background extraction using the existing resources status column."""

import logging
import threading

logger = logging.getLogger(__name__)


def process_one(connect, extract):
    """Claim one pending resource, then invoke extract(id); return whether claimed."""
    with connect() as db:
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
    except Exception:
        logger.exception("Resource extraction failed: %s", resource_id)
        with connect() as db:
            db.execute("UPDATE resources SET status = 'failed' WHERE id = %s AND status = 'extracting'", (resource_id,))
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


def start_worker(connect, extract, interval=5):
    """Start a polling worker; caller stops it with stop.set() and thread.join()."""
    if interval <= 0:
        raise ValueError("interval must be positive")
    stop = threading.Event()

    def run():
        while not stop.is_set():
            try:
                if process_one(connect, extract):
                    continue
            except Exception:
                logger.exception("Extraction worker database error")
            stop.wait(interval)

    thread = threading.Thread(target=run, name="resource-extraction", daemon=True)
    thread.start()
    return stop, thread
