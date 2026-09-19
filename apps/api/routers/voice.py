"""Voice routes — ARCHITECTURE.md §4.

OWNERSHIP: §7 assigns voice.py to C. Reassigned to B (backend routes only) by
Prisha on 2026-09-19; C keeps the frontend mic capture and playback. §7 is stale
here — tell C before editing.

STEP 9 (2026-09-19): both routes now call Deepgram via services/voice.py, with
the step-3 fixtures as the fallback. Shapes are unchanged, so C's mic UI needs
no change to keep working.
"""

import logging

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response

from apps.api.models.schemas import SpeakRequest, TranscribeResponse
from apps.api.services import voice

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...)) -> Response:
    raw = await audio.read()
    text, source = voice.transcribe(raw, content_type=audio.content_type)
    # §4 fixes the body to {"text": ...}. Provenance goes in a header so a
    # caller can tell a real transcript from the canned one without the shape
    # changing — the same reason Plan.source exists.
    return Response(
        content=TranscribeResponse(text=text).model_dump_json(),
        media_type="application/json",
        headers={"X-Voice-Source": source},
    )


@router.post(
    "/speak",
    responses={200: {"content": {"audio/mpeg": {}}}},
    response_class=Response,
)
def speak(payload: SpeakRequest) -> Response:
    audio, source = voice.speak(payload.text)
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"X-Voice-Source": source},
    )
