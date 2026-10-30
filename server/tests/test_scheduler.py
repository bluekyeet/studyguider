from datetime import datetime, timezone

from scheduler import run_due


class Database:
    def __init__(self):
        self.schedules = {1: ("algebra", 2, True), 2: ("geometry", 2, True),
                          3: ("disabled", 2, False)}
        self.runs = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params):
        if "SELECT topic_id FROM lesson_schedules" in sql:
            self.result = [(topic,) for topic, (_, hour, enabled) in self.schedules.items()
                           if enabled and hour <= params[0]]
        elif "INSERT INTO lesson_schedule_runs" in sql:
            day, topic, hour = params
            query, scheduled_hour, enabled = self.schedules[topic]
            key = topic, day
            self.result = None
            if enabled and scheduled_hour <= hour and key not in self.runs:
                self.runs[key] = {"status": "running", "query": query}
                self.result = (query,)
        else:
            value, topic, day = params
            run = self.runs[topic, day]
            if "'failed'" in sql:
                run.update(status="failed", error=value)
            else:
                run.update(status="completed", lesson_id=value)
        return self

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.result


def test_due_runs_are_at_most_once_and_failures_visible():
    db = Database()
    calls = []

    def generate(topic, body):
        calls.append((topic, body.query))
        if topic == 2:
            raise RuntimeError("gateway down")
        return {"id": 42}

    early = datetime(2026, 1, 1, 1, tzinfo=timezone.utc)
    due = early.replace(hour=2)
    run_due(lambda: db, generate, early)
    assert not calls
    run_due(lambda: db, generate, due)
    run_due(lambda: db, generate, due)
    assert calls == [(1, "algebra"), (2, "geometry")]
    assert db.runs[1, due.date()]["lesson_id"] == 42
    assert db.runs[2, due.date()]["error"] == "gateway down"
    assert db.runs[2, due.date()]["status"] == "failed"
    run_due(lambda: db, generate, due.replace(day=2))
    assert len(calls) == 4
