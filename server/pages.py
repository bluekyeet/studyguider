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


def page_router(connect, authorised):
    router = APIRouter(dependencies=[Depends(authorised)])

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
                    cached = document[page - 1].get_pixmap(dpi=110).tobytes("png")
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
