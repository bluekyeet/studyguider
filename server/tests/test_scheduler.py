from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from scheduler import run_due, scheduler_router


class Database:
    def __init__(self):
        self.schedules = {1: ("algebra", 2, True), 2: ("geometry", 2, True),
                          3: ("disabled", 2, False)}
        self.runs = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=()):
        if "INSERT INTO lesson_schedules" in sql:
            return self
        if "SELECT topic_id, timezone FROM lesson_schedules" in sql:
            self.result = [(topic, "UTC") for topic, (_, hour, enabled) in self.schedules.items() if enabled]
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


def test_auckland_daylight_saving_uses_local_date_and_hour():
    class NZDatabase(Database):
        def execute(self, sql, params=()):
            if "SELECT topic_id, timezone FROM lesson_schedules" in sql:
                self.result = [(1, "Pacific/Auckland")]
                return self
            return super().execute(sql, params)

    for instant in (datetime(2026, 1, 1, 13, tzinfo=timezone.utc),
                    datetime(2026, 7, 1, 14, tzinfo=timezone.utc)):
        db = NZDatabase()
        run_due(lambda: db, lambda topic, body: {"id": 1}, instant)
        assert db.runs[1, instant.date().replace(day=2)]["status"] == "completed"


def test_schedule_endpoints():
    class ApiDatabase:
        schedule = None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, sql, params):
            if "INSERT INTO lesson_schedules" in sql:
                self.result = params[:4] if params[4] == 1 else None
                if self.result:
                    self.schedule = self.result
            elif "SELECT 1 FROM topics" in sql:
                self.result = (1,) if params[0] == 1 else None
            elif "FROM lesson_schedules" in sql:
                self.result = self.schedule
            else:
                self.result = [(datetime(2026, 1, 1).date(), "algebra", "failed", None,
                                "gateway down", None, None)]
            return self

        def fetchone(self):
            return self.result

        def fetchall(self):
            return self.result

    db = ApiDatabase()

    def authorised(authorization: str = Header(default="")):
        if authorization != "Bearer valid":
            raise HTTPException(401)

    app = FastAPI()
    app.include_router(scheduler_router(lambda: db, authorised))
    client = TestClient(app)
    headers = {"Authorization": "Bearer valid"}
    url = "/topics/1/schedule"
    body = {"query": " algebra ", "hour_utc": 2, "enabled": True}
    assert client.get(url).status_code == 401
    assert client.put(url, json=body).status_code == 401
    assert client.get(url + "/runs").status_code == 401
    assert client.get(url, headers=headers).json() is None
    assert client.put(url, headers=headers, json=body).json() == {
        "topic_id": 1, "query": "algebra", "hour_utc": 2, "enabled": True, "timezone": "UTC"}
    assert client.get(url, headers=headers).json()["query"] == "algebra"
    assert client.get(url + "/runs", headers=headers).json()[0]["error"] == "gateway down"
    assert client.put(url, headers=headers, json={**body, "hour_utc": 24}).status_code == 422
    assert client.put(url, headers=headers, json={**body, "query": "   "}).status_code == 422
    assert client.put("/topics/2/schedule", headers=headers, json=body).status_code == 404
    assert client.get("/topics/2/schedule", headers=headers).status_code == 404
    assert client.get("/topics/2/schedule/runs", headers=headers).status_code == 404
