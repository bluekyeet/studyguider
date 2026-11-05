import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worker import MAX_ATTEMPTS, process_one, recover_interrupted, start_worker


class Result:
    def __init__(self, row=None, rowcount=0):
        self.row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self.row


class Database:
    def __init__(self, statuses):
        self.statuses = statuses
        self.attempts = {}
        self.lock = threading.Lock()

    def __call__(self):
        return self

    def __enter__(self):
        self.lock.acquire()
        return self

    def __exit__(self, *args):
        self.lock.release()

    def execute(self, query, params=()):
        if "retry_at IS NULL" in query:
            keys = [key for key, value in self.statuses.items() if value == "failed" and self.attempts.get(key, 0) < params[0]]
            for key in keys:
                self.statuses[key] = "pending"
            return Result(rowcount=len(keys))
        if "SKIP LOCKED" in query:
            for key in sorted(self.statuses):
                if self.statuses[key] == "pending":
                    self.statuses[key] = "extracting"
                    return Result((key,))
            return Result()
        if "status = 'failed'" in query:
            key = params[-1]
            if self.statuses.get(key) == "extracting":
                self.statuses[key] = "failed"
                self.attempts[key] = self.attempts.get(key, 0) + 1
            return Result()
        if "status = 'pending'" in query:
            keys = [key for key, value in self.statuses.items() if value == "extracting"]
            for key in keys:
                self.statuses[key] = "pending"
            return Result(rowcount=len(keys))
        raise AssertionError(query)


class WorkerTests(unittest.TestCase):
    def test_claims_once_across_workers(self):
        db = Database({1: "pending"})
        entered, release = threading.Event(), threading.Event()
        calls = []

        def extract(key):
            calls.append(key)
            entered.set()
            self.assertTrue(release.wait(2))
            db.statuses[key] = "extracted"

        thread = threading.Thread(target=process_one, args=(db, extract))
        thread.start()
        self.assertTrue(entered.wait(2))
        self.assertFalse(process_one(db, extract))
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(calls, [1])
        self.assertEqual(db.statuses[1], "extracted")

    def test_failure_does_not_mark_ready_or_overwrite_deletion(self):
        db = Database({1: "pending", 2: "pending"})

        def fail(key):
            if key == 2:
                db.statuses[key] = "deleting"
            raise ValueError("unsupported format")

        db.attempts[1] = MAX_ATTEMPTS - 1       # one try left, so it ends up failed rather than waiting
        with self.assertLogs("worker", level="ERROR"):
            self.assertTrue(process_one(db, fail))
            self.assertTrue(process_one(db, fail))
        self.assertEqual(db.statuses, {1: "failed", 2: "deleting"})
        self.assertFalse(process_one(db, fail))

    def test_failed_resources_are_retried_until_they_work(self):
        db = Database({1: "pending"})
        tries = []

        def flaky(key):
            tries.append(key)
            if len(tries) < 3:
                raise ValueError("gateway timeout")
            db.statuses[key] = "extracted"

        with self.assertLogs("worker", level="ERROR"):
            for _ in range(3):
                self.assertTrue(process_one(db, flaky))
        self.assertEqual((tries, db.statuses), ([1, 1, 1], {1: "extracted"}))

    def test_gives_up_after_the_attempt_limit(self):
        db = Database({1: "pending"})

        def fail(key):
            raise ValueError("bad file")

        with self.assertLogs("worker", level="ERROR"):
            runs = 0
            while process_one(db, fail):
                runs += 1
        self.assertEqual((runs, db.statuses), (MAX_ATTEMPTS, {1: "failed"}))

    def test_explicit_recovery_and_shutdown(self):
        db = Database({1: "extracting", 2: "failed", 3: "deleting"})
        db.attempts[2] = MAX_ATTEMPTS
        self.assertEqual(recover_interrupted(db), 1)
        done = threading.Event()

        def extract(key):
            db.statuses[key] = "extracted"
            done.set()

        stop, thread = start_worker(db, extract, interval=0.01)
        self.assertTrue(done.wait(2))
        stop.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(db.statuses, {1: "extracted", 2: "failed", 3: "deleting"})


if __name__ == "__main__":
    unittest.main()
