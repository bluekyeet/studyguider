import app


def test_empty_strict_search_uses_ranked_topic_scoped_fallback(monkeypatch):
    calls = []

    class Database:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params):
            calls.append((sql, params))
            self.sql = sql
            return self
        def fetchone(self): return (3,)
        def fetchall(self):
            if "replace(plainto_tsquery" in self.sql:
                assert "c.topic_id = %s" in self.sql and "r.status = 'extracted'" in self.sql
                assert calls[-1][1] == (3, "charge pushed between plates", "charge pushed between plates")
                return [(1, "resource", "notes.txt", 2, "Electric field between plates", 91173)]
            return []

    monkeypatch.setattr(app, "connect", Database)
    rows = app.search_resources(3, "charge pushed between plates")
    assert rows[0]["content"] == "Electric field between plates"
    assert len(calls) == 4  # topic check, strict chunks/pages, relaxed chunks
