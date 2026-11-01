import pytest
from fastapi import HTTPException

import app


def test_note_edit_compares_original_and_preserves_other_client_work(monkeypatch):
    class Database:
        content = "Original note"
        exists = True
        result = None
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params):
            if "UPDATE notes" in sql:
                new, note, topic, original = params
                assert (note, topic) == (42, 2)
                self.result = None
                if self.exists and self.content == original:
                    self.content = new
                    self.result = (42, new, "2026-11-02")
            else:
                self.result = (1,) if self.exists else None
            return self
        def fetchone(self): return self.result

    db = Database()
    monkeypatch.setattr(app, "connect", lambda: db)
    assert app.edit_note(2, 42, app.NoteEdit(content="Client one", original_content="Original note"))["content"] == "Client one"
    with pytest.raises(HTTPException) as conflict:
        app.edit_note(2, 42, app.NoteEdit(content="Client two", original_content="Original note"))
    assert conflict.value.status_code == 409
    assert db.content == "Client one"
    db.exists = False
    with pytest.raises(HTTPException) as missing:
        app.edit_note(2, 42, app.NoteEdit(content="Client two", original_content="Client one"))
    assert missing.value.status_code == 404
