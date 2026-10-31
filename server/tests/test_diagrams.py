"""SVG sanitising for AI diagrams, plus the usage summary shape.

The SVG samples are written for this test.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from diagrams import _sanitise

SAFE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect x="1" y="1" width="20" height="20" fill="#1E3A8A"/>'
        '<text x="5" y="40">Force</text></svg>')


def test_safe_svg_is_kept_verbatim():
    assert _sanitise(SAFE) == SAFE


def test_fenced_svg_is_unwrapped():
    assert _sanitise("```svg\n" + SAFE + "\n```") == SAFE


def test_prose_around_the_svg_is_dropped():
    assert _sanitise("Here is the diagram:\n" + SAFE + "\nLet me know!") == SAFE


@pytest.mark.parametrize("svg", [
    SAFE.replace("<text", "<script>alert(1)</script><text"),
    SAFE.replace("<rect", '<rect onclick="alert(1)"'),
    SAFE.replace("<svg", '<svg xmlns:xlink="http://www.w3.org/1999/xlink"><image xlink:href="https://e.invalid/a.png"/>'),
    '<!DOCTYPE svg [<!ENTITY x "y">]>' + SAFE,
    SAFE.replace("<text", "<iframe/><text"),
])
def test_unsafe_svg_is_rejected(svg):
    with pytest.raises(ValueError):
        _sanitise(svg)


def test_a_reply_without_svg_is_rejected():
    with pytest.raises(ValueError):
        _sanitise("I cannot draw that.")


def test_oversized_svg_is_rejected():
    with pytest.raises(ValueError):
        _sanitise(SAFE.replace("Force", "x" * 500_001))
