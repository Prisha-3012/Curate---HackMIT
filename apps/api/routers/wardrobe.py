"""Photo analysis and process-local wardrobe inventory; no fixture substitution."""

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from apps.api.services import wardrobe

router = APIRouter(prefix="/api", tags=["wardrobe"])


def _response(items: list[dict], source: str) -> JSONResponse:
    return JSONResponse(
        content={"items": items, "count": len(items), "source": source},
        headers={"X-Wardrobe-Source": source},
    )


@router.post("/wardrobe")
async def upload_wardrobe(
    user_id: str = Form(...), image: UploadFile = File(...)
) -> JSONResponse:
    raw = await image.read()
    items, source = await run_in_threadpool(
        wardrobe.analyze_wardrobe, raw, content_type=image.content_type
    )
    # Only successful detections replace the user's stored inventory.
    if items:
        wardrobe.set_wardrobe(user_id, items, source)
    return _response(items, source)


@router.get("/wardrobe/{user_id}")
def read_wardrobe(user_id: str) -> JSONResponse:
    meta = wardrobe.get_wardrobe_meta(user_id) or {"items": [], "source": "none"}
    return _response(meta["items"], meta["source"])
