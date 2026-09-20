"""Wardrobe routes — the closet photo that feeds the OWN rung.

A's lane (CV), wired into the backend so the resolver can prefer what the person
already owns and stop recommending duplicates of it. Detection lives in
services/wardrobe.py; this is just the HTTP door.

Shapes are kept small and header-tagged the same way voice.py is: the body is the
detected items, and X-Wardrobe-Source says whether they came from a vision model
or the fixture, so the UI can tell a real closet from the demo one.
"""

import json
import logging

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from apps.api.services import wardrobe

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["wardrobe"])


@router.post("/wardrobe")
async def upload_wardrobe(
    user_id: str = Form(...),
    image: UploadFile = File(...),
) -> JSONResponse:
    """Analyze a wardrobe photo and remember what the user owns.

    The detected items are stored per user and picked up automatically by the
    next POST /api/mission, so the plan prefers the closet and skips buying
    duplicates of it.
    """
    raw = await image.read()
    items, source = wardrobe.analyze_wardrobe(raw, content_type=image.content_type)
    wardrobe.set_wardrobe(user_id, items, source)
    return JSONResponse(
        content={"items": items, "count": len(items), "source": source},
        headers={"X-Wardrobe-Source": source},
    )


@router.get("/wardrobe/{user_id}")
def read_wardrobe(user_id: str) -> JSONResponse:
    """What we currently have on file for this user's closet. [] if none."""
    meta = wardrobe.get_wardrobe_meta(user_id) or {"items": [], "source": "none"}
    return JSONResponse(
        content={
            "items": meta["items"],
            "count": len(meta["items"]),
            "source": meta["source"],
        },
        headers={"X-Wardrobe-Source": meta["source"]},
    )
