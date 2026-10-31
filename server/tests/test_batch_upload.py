"""Batch uploads: several files or one zip become ordinary queued resources.

The filename sanitiser is tested directly; the endpoint needs a database, so it
is checked live against the running stack rather than in this unit suite.
"""

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import _safe_member_name


def test_member_name_keeps_only_the_basename():
    assert _safe_member_name("slides/week 3/Notes.pdf") == "Notes.pdf"
    assert _safe_member_name("physics.docx") == "physics.docx"


def test_member_name_ignores_directory_entries():
    assert _safe_member_name("slides/") == ""


def test_member_name_rejects_traversal():
    for name in ("../secret.pdf", "slides/../../etc/passwd", "/absolute.pdf"):
        with pytest.raises(HTTPException) as raised:
            _safe_member_name(name)
        assert raised.value.status_code == 400
