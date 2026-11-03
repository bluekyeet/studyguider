"""Original-page images for the question check screen.

The PDF is a small sample built here, not a real paper.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pymupdf
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pages


def sample_pdf(path, pages_count=2):
    document = pymupdf.open()
    for number in range(pages_count):
        page = document.new_page()
        page.insert_text((72, 72), f"Sample page {number + 1}")
    document.save(str(path))
    document.close()


class FakeConnect:
    def __init__(self, filename):
        self.filename = filename

    def __call__(self):
        connection = MagicMock()
        connection.__enter__.return_value.execute.return_value.fetchone.return_value = (
            (self.filename,) if self.filename else None)
        return connection


def endpoint(router):
    return next(item for item in router.routes
                if item.path == "/resources/{resource_id}/pages/{page}/image").endpoint


@pytest.fixture
def storage(tmp_path, monkeypatch):
    """Point the route at a temporary upload directory; the stored file is named by the resource id."""
    pages.CACHE.clear()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    yield tmp_path
    pages.CACHE.clear()


def test_page_image_renders_the_requested_page(storage):
    sample_pdf(storage / "id", 3)
    router = pages.page_router(FakeConnect("sample.pdf"), lambda: None)
    response = endpoint(router)("id", 2)
    assert response.media_type == "image/png"
    assert response.body.startswith(b"\x89PNG")


def test_page_beyond_the_document_is_a_404(storage):
    sample_pdf(storage / "id", 2)
    router = pages.page_router(FakeConnect("sample.pdf"), lambda: None)
    with pytest.raises(HTTPException) as error:
        endpoint(router)("id", 9)
    assert error.value.status_code == 404


def test_a_missing_stored_file_is_a_404(storage):
    router = pages.page_router(FakeConnect("sample.pdf"), lambda: None)
    with pytest.raises(HTTPException) as error:
        endpoint(router)("id", 1)
    assert error.value.status_code == 404


def test_missing_resource_is_a_404(storage):
    router = pages.page_router(FakeConnect(None), lambda: None)
    with pytest.raises(HTTPException) as error:
        endpoint(router)("id", 1)
    assert error.value.status_code == 404


def test_non_pdf_resources_have_no_page_images(storage):
    router = pages.page_router(FakeConnect("slides.pptx"), lambda: None)
    with pytest.raises(HTTPException) as error:
        endpoint(router)("id", 1)
    assert error.value.status_code == 422


def test_safe_dpi_scales_down_huge_pages_and_refuses_absurd_ones():
    a4 = pymupdf.Rect(0, 0, 595, 842)
    assert pages.safe_dpi(a4, 200) == 200
    big = pymupdf.Rect(0, 0, 10000, 10000)
    scaled = pages.safe_dpi(big, 200)
    assert scaled < 200 and (10000 / 72 * scaled) * (10000 / 72 * scaled) <= pages.MAX_RENDER_PIXELS * 1.05
    with pytest.raises(HTTPException) as raised:
        pages.safe_dpi(pymupdf.Rect(0, 0, 20000, 100), 110)
    assert raised.value.status_code == 422
