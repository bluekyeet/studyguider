"""Render extracted paper/schedule pages to PNG so a person can compare them.

The check screen needs the original page beside every parsed field. Only pages
that belong to a resource already in the database can be rendered.
"""
import threading
from pathlib import Path

import pymupdf
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

CACHE = {}
CACHE_LOCK = threading.Lock()
MAX_CACHE = 200
MAX_RENDER_PIXELS = 25_000_000
MAX_PAGE_POINTS = 14400  # 200 inches; real pages are far smaller


def safe_dpi(rect, dpi):
    """Lower `dpi` so a page or clip never rasterises beyond MAX_RENDER_PIXELS.

    A small PDF can declare an enormous page; refuse absurd sizes and scale the rest down.
    """
    width, height = float(rect.width), float(rect.height)
    if not (0 < width <= MAX_PAGE_POINTS and 0 < height <= MAX_PAGE_POINTS):
        raise HTTPException(422, "This page is too large to render")
    pixels = (width / 72 * dpi) * (height / 72 * dpi)
    return dpi if pixels <= MAX_RENDER_PIXELS else max(10, int(dpi * (MAX_RENDER_PIXELS / pixels) ** 0.5))


def page_router(connect, authorised):
    router = APIRouter(dependencies=[Depends(authorised)])

    @router.get("/resources/{resource_id}/pages/{page}/diagrams")
    def diagram_regions(resource_id: str, page: int):
        import uuid
        try:
            resource_id = str(uuid.UUID(resource_id))
        except ValueError:
            raise HTTPException(422, "Invalid resource id") from None
        with connect() as db:
            row = db.execute("SELECT filename FROM resources WHERE id = %s AND status != 'deleting'", (resource_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Resource not found")
        if Path(row[0]).suffix.lower() != ".pdf":
            raise HTTPException(422, "Diagrams require a PDF source")
        try:
            with pymupdf.open(Path(f"/data/uploads/{resource_id}")) as document:
                if not 1 <= page <= len(document):
                    raise HTTPException(404, "Page not found")
                source = document[page - 1]
                regions = [pymupdf.Rect(item["bbox"]) for item in source.get_image_info()]
                regions += list(source.cluster_drawings())
                # ponytail: geometric extraction, not semantic association; original page remains authoritative.
                regions = [r for r in regions if r.width >= 45 and r.height >= 35 and r.get_area() < source.rect.get_area() * 0.7]
                return {"regions": [{"x0": max(0, r.x0 - 8), "y0": max(0, r.y0 - 8), "x1": min(source.rect.width, r.x1 + 8), "y1": min(source.rect.height, r.y1 + 8)} for r in regions[:20]], "notice": "Automatically located diagram regions; check labels against the original page"}
        except HTTPException:
            raise
        except (OSError, RuntimeError, ValueError):
            raise HTTPException(422, "Could not extract PDF diagrams") from None

    @router.get("/resources/{resource_id}/pages/{page}/diagram-image")
    def diagram_image(resource_id: str, page: int, x0: float, y0: float, x1: float, y1: float):
        import math
        regions = diagram_regions(resource_id, page)["regions"]
        values = (x0, y0, x1, y1)
        if not all(math.isfinite(v) for v in values) or not any(all(abs(region[k] - v) < 0.1 for k, v in zip(("x0", "y0", "x1", "y1"), values)) for region in regions):
            raise HTTPException(422, "Select an extracted diagram region")
        with pymupdf.open(Path(f"/data/uploads/{resource_id}")) as document:
            clip = pymupdf.Rect(*values)
            data = document[page - 1].get_pixmap(clip=clip, dpi=safe_dpi(clip, 160)).tobytes("png")
        return Response(data, media_type="image/png")

    @router.get("/resources/{resource_id}/pages/{page}/image")
    def page_image(resource_id, page: int):
        with connect() as db:
            row = db.execute("SELECT filename FROM resources WHERE id = %s AND status != 'deleting'",
                             (resource_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Resource not found")
        if Path(row[0]).suffix.lower() != ".pdf":
            raise HTTPException(422, "Page images are only available for PDF resources")
        key = (str(resource_id), page)
        with CACHE_LOCK:
            cached = CACHE.get(key)
        if cached is None:
            path = Path(f"/data/uploads/{resource_id}")
            if not path.is_file():
                raise HTTPException(404, "Stored file missing; restore from backup")
            try:
                with pymupdf.open(path) as document:
                    if page < 1 or page > document.page_count:
                        raise HTTPException(404, "Page not found in this PDF")
                    target = document[page - 1]
                    cached = target.get_pixmap(dpi=safe_dpi(target.rect, 110)).tobytes("png")
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(500, "The original file could not be rendered")
            with CACHE_LOCK:
                if len(CACHE) >= MAX_CACHE:
                    CACHE.pop(next(iter(CACHE)))
                CACHE[key] = cached
        return Response(cached, media_type="image/png",
                        headers={"Cache-Control": "private, max-age=3600"})

    return router
