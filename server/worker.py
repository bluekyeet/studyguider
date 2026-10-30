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


def recover_interrupted(connect):
    """Requeue interrupted claims only after every extraction worker has stopped."""
    # ponytail: no claim leases exist; add owner IDs and expiry before online recovery.
    with connect() as db:
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
