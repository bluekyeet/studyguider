import threading
import time

import pytest

import usage


@pytest.fixture
def settings(monkeypatch):
    stored = {}
    monkeypatch.delenv("STUDYGUIDER_MODEL_WORKERS", raising=False)
    usage.set_settings_reader(lambda: dict(stored))
    yield stored
    usage.set_settings_reader(None)


def test_the_limit_comes_from_the_administrator_then_the_environment_then_the_default(settings, monkeypatch):
    assert usage.model_workers_setting() == (usage.DEFAULT_MODEL_WORKERS, "default")
    monkeypatch.setenv("STUDYGUIDER_MODEL_WORKERS", "1")
    usage.forget_cached_settings()
    assert usage.model_workers_setting() == (1, "environment")
    settings["model_workers"] = "4"
    usage.forget_cached_settings()
    assert usage.model_workers_setting() == (4, "administrator")
    settings["model_workers"] = "99"      # out of range: ignored
    usage.forget_cached_settings()
    assert usage.model_workers_setting() == (1, "environment")
    assert usage.model_workers(default=3) == 1


def test_background_calls_never_exceed_the_limit_and_follow_a_change_without_a_restart(settings):
    settings["model_workers"] = "2"
    usage.forget_cached_settings()
    running, most, lock = [0], [0], threading.Lock()

    def call():
        with usage.model_slot():
            with lock:
                running[0] += 1
                most[0] = max(most[0], running[0])
            time.sleep(0.05)
            with lock:
                running[0] -= 1

    def run(count):
        threads = [threading.Thread(target=call) for _ in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    run(8)
    assert most[0] == 2
    settings["model_workers"] = "1"       # an administrator lowers it while the server runs
    usage.forget_cached_settings()
    most[0] = 0
    run(6)
    assert most[0] == 1
