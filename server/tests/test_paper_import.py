from paper_import import import_topic_papers


def test_unpaired_resources_do_not_import():
    class Result:
        def fetchall(self):
            return [("paper-id", "91164-exm-2024.pdf")]

    class Database:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params):
            assert "SELECT id, filename FROM resources" in sql
            return Result()

    result = import_topic_papers(Database, 4)
    assert result[0]["status"] == "waiting"
    assert "matching schedule" in result[0]["detail"]
