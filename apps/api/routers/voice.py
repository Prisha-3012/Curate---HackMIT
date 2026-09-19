"""Voice routes — ARCHITECTURE.md §4.

OWNERSHIP: §7 assigns voice.py to C. Reassigned to B (backend routes only) by
Prisha on 2026-09-19; C keeps the frontend mic capture and playback. §7 is stale
here — tell C before editing.

STEP 3: both routes return fixtures so C's mic UI has real shapes from hour 3.
STEP 9 wires Deepgram (the only provider ARCHITECTURE.md names, §8) behind a
timeout with these same fixtures as the fallback.
"""

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import Response

from apps.api import fixtures
from apps.api.models.schemas import SpeakRequest, TranscribeResponse

router = APIRouter(prefix="/api/voice", tags=["voice"])

#: 1-frame silent MP3. Placeholder so /speak returns real audio/mpeg bytes in
#: step 3; step 9 replaces this with Deepgram TTS output.
_SILENT_MP3 = bytes.fromhex("fffb90c40000000000000000000000000000000000")


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...)) -> TranscribeResponse:
    # STEP 3 stub. Read and discard so the client sees its upload consumed.
    await audio.read()
    return fixtures.load_as(fixtures.TRANSCRIPT, TranscribeResponse)


@router.post(
    "/speak",
    responses={200: {"content": {"audio/mpeg": {}}}},
    response_class=Response,
)
def speak(payload: SpeakRequest) -> Response:
    # STEP 3 stub. Returns audio/mpeg per §4, not JSON.
    return Response(content=_SILENT_MP3, media_type="audio/mpeg")
