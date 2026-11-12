from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from scheduler import run_due, scheduler_router
from lessons import LessonGeneration


def test_scheduled_ownership_cannot_be_supplied_by_request_json():
    body = LessonGeneration.model_validate({"query": "algebra", "_schedule_run": [1, "2026-01-01"],
                                           "_schedule_persisted": True})
    assert body._schedule_run is None and body._schedule_persisted is False
    assert body.model_dump() == {"query": "algebra"}
    assert set(LessonGeneration.model_json_schema()["properties"]) == {"query"}


def test_run_history_includes_actual_lesson_review_status():
    class HistoryDatabase:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()):
            if "lesson_schedule_runs r" in sql:
                assert "LEFT JOIN lessons" in sql
                assert params == (1,)
            return self
        def fetchone(self): return (1,)
        def fetchall(self): return [("2026-11-02", "Waves", "completed", 42, None, None, None, "flagged")]

    app = FastAPI()
    app.include_router(scheduler_router(HistoryDatabase, lambda: None))
    response = TestClient(app).get("/topics/1/schedule/runs")
    assert response.status_code == 200
    assert response.json()[0]["status"] == "completed"
    assert response.json()[0]["review_status"] == "flagged"


class Database:
    def __init__(self):
        self.schedules = {1: ("algebra", 2, True), 2: ("geometry", 2, True),
                          3: ("disabled", 2, False)}
        self.runs = {}
        self.waiting = set()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params=()):
        if "INSERT INTO lesson_schedules" in sql:
            return self
        if "SELECT 1 FROM lesson_schedule_runs WHERE topic_id" in sql:
            self.result = (1,) if (params[0], params[1]) in self.runs else None
            return self
        if "SELECT 1 FROM lessons WHERE topic_id" in sql:
            self.result = (1,) if params[0] in getattr(self, "recent_lesson", set()) else None
            return self
        if "FROM lessons l WHERE l.topic_id" in sql:
            self.result = (1,) if params[0] in self.waiting else None
            return self
        if "UPDATE lesson_schedule_runs r SET" in sql:
            topic, day = params[0], params[1]
            run = self.runs.get((topic, day))
            self.result = None
            if run and "'failed'" in sql:
                if run["status"] == "failed" and run.get("lesson_id") is None and run.get("due_again") and run.get("attempts", 1) < params[2]:
                    run.update(status="running", attempts=run.get("attempts", 1) + 1, due_again=False)
                    self.result = (run["query"],)
            elif run and run["status"] == "completed" and run.get("flagged"):
                run.update(status="running", lesson_id=None, flagged=False)
                self.result = (run["query"],)
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
            if "AND status = 'running'" in sql and (run['status'] != 'running' or run.get('lesson_id') is not None):
                return self
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


def test_a_topic_with_an_unopened_lesson_waiting_gets_no_new_one():
    db = Database()
    db.waiting = {1}
    calls = []
    run_due(lambda: db, lambda topic, body: calls.append(topic) or {"id": 42}, datetime(2026, 1, 1, 2, tzinfo=timezone.utc))
    assert calls == [2] and (1, datetime(2026, 1, 1).date()) not in db.runs


def test_finishing_a_carried_over_lesson_does_not_bring_a_second_one_that_day():
    db = Database()
    db.waiting = {1}                  # the carried lesson counts as today's lesson, whether unopened or finished today
    calls = []
    run_due(lambda: db, lambda topic, body: calls.append(topic) or {"id": 42}, datetime(2026, 1, 1, 2, tzinfo=timezone.utc))
    assert calls == [2]


def test_a_lesson_that_failed_its_review_is_written_again_the_same_day():
    db = Database()
    due = datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
    db.runs[1, due.date()] = {"status": "completed", "query": "algebra", "lesson_id": 7, "flagged": True}
    calls = []
    run_due(lambda: db, lambda topic, body: calls.append(topic) or {"id": 8}, due)
    run_due(lambda: db, lambda topic, body: calls.append(topic) or {"id": 9}, due)
    assert calls == [1, 2]                      # topic 1 once more, not twice; topic 2 for the first time
    assert db.runs[1, due.date()]["lesson_id"] == 8


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


def test_unknown_outcomes_are_not_retried_and_completed_runs_are_not_downgraded():
    db = Database()
    due = datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
    db.runs[2, due.date()] = {"status": "running", "query": "geometry"}
    calls = []

    def generate(topic, body):
        assert body._schedule_run == (topic, due.date())
        calls.append(topic)
        # Model the DB accepting persistence but the caller losing the response.
        db.runs[body._schedule_run].update(status='completed', lesson_id=42)
        raise RuntimeError('commit acknowledgement lost')

    run_due(lambda: db, generate, due)
    run_due(lambda: db, generate, due)
    assert calls == [1]
    assert db.runs[1, due.date()] == {"status": "completed", "query": "algebra", "lesson_id": 42}
    assert db.runs[2, due.date()]["status"] == 'running'


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


def test_a_run_that_failed_without_a_lesson_is_tried_again_until_it_works():
    db = Database()
    due = datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
    outcomes = iter([RuntimeError("503"), RuntimeError("503"), {"id": 5}])

    def generate(topic, body):
        result = next(outcomes)
        if isinstance(result, Exception):
            raise result
        return result

    db.schedules = {1: ("algebra", 2, True)}
    run_due(lambda: db, generate, due)
    run_due(lambda: db, generate, due)             # the wait is not over yet: nothing happens
    assert db.runs[1, due.date()]["status"] == "failed"
    for _ in range(2):
        db.runs[1, due.date()]["due_again"] = True
        run_due(lambda: db, generate, due)
    assert db.runs[1, due.date()]["status"] == "completed" and db.runs[1, due.date()]["attempts"] == 3


def test_lessons_follow_the_plan_phase():
    db = Database()
    db.recent_lesson = {1}           # topic 1 had a lesson this week; topic 2 has not
    phases = {1: "maintain", 2: "maintain"}
    seen = []
    run_due(lambda: db, lambda topic, body: seen.append((topic, body._phase)) or {"id": 42},
            datetime(2026, 1, 1, 2, tzinfo=timezone.utc), phase_of=lambda db, topic, day: phases[topic])
    assert seen == [(2, "maintain")]       # maintenance: at most one short lesson a week, and it is told it is maintenance
    phases[1] = "exam_prep"
    run_due(lambda: db, lambda topic, body: seen.append((topic, body._phase)) or {"id": 43},
            datetime(2026, 1, 2, 2, tzinfo=timezone.utc), phase_of=lambda db, topic, day: phases[topic])
    assert (1, "exam_prep") in seen        # close to an assessment the nightly lesson comes back, written as exam practice
