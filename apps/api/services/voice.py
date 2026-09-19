"""Speech in, speech out. ARCHITECTURE.md §4.

Deepgram is the only provider §8 names. Two calls, both with a timeout and both
falling back to the step-3 fixtures (the standing rule): a voice outage must
degrade to a typed demo, never take /api/mission down with it.

ONE DELIBERATE EXCEPTION to "fall back on failure": silence transcribes to an
empty string, and an empty string is returned as-is rather than replaced with
the hero goal. Answering silence with "business casual for my internship" is the
same class of lie as serving the hero fixture unlabelled — the caller asked what
was said, and the truthful answer is "nothing".

smart_format is on for a reason beyond punctuation: it renders spoken amounts as
digits, so "my budget is one hundred dollars" arrives as "My budget is $100."
and the frontend's budget parser can read it. Without it the goal text carries
no parseable figure and every spoken mission looks budget-less.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from apps.api import fixtures
from apps.api.config import get_settings
from apps.api.models.schemas import TranscribeResponse

log = logging.getLogger(__name__)

LISTEN_URL = "https://api.deepgram.com/v1/listen"
SPEAK_URL = "https://api.deepgram.com/v1/speak"

#: 1-frame silent MP3. What /speak returns when TTS is unavailable, so the
#: client still receives audio/mpeg rather than a JSON error it cannot play.
SILENT_MP3 = bytes.fromhex("fffb90c40000000000000000000000000000000000")


def _key() -> str:
    return (get_settings().deepgram_api_key or "").strip()


def transcribe(audio: bytes, *, content_type: Optional[str] = None) -> tuple[str, str]:
    """(text, source) where source is "deepgram" or "fixture". Never raises."""
    key = _key()
    if not key:
        log.info("no DEEPGRAM_API_KEY; using fixture transcript")
        return _fixture_transcript(), "fixture"
    if not audio:
        log.warning("empty audio upload; nothing to transcribe")
        return "", "deepgram"

    s = get_settings()
    headers = {"Authorization": f"Token {key}"}
    # Pass the browser's own content type through. MediaRecorder produces
    # audio/webm;codecs=opus, which Deepgram handles natively — transcoding it
    # here would add a dependency and a failure mode for no benefit.
    if content_type:
        headers["Content-Type"] = content_type

    try:
        r = httpx.post(
            LISTEN_URL,
            params={"model": s.deepgram_stt_model, "smart_format": "true"},
            headers=headers,
            content=audio,
            timeout=s.deepgram_timeout_s,
        )
        r.raise_for_status()
        alt = r.json()["results"]["channels"][0]["alternatives"][0]
        text = (alt.get("transcript") or "").strip()
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
        log.warning("transcribe failed (%s); using fixture transcript", exc)
        return _fixture_transcript(), "fixture"

    log.info("transcribed %d bytes, confidence %s", len(audio), alt.get("confidence"))
    return text, "deepgram"


def speak(text: str) -> tuple[bytes, str]:
    """(mp3 bytes, source) where source is "deepgram" or "fixture". Never raises."""
    key = _key()
    if not key:
        return SILENT_MP3, "fixture"
    if not text.strip():
        # Nothing to say. Synthesising an empty string wastes a call and some
        # voices error on it.
        return SILENT_MP3, "fixture"

    s = get_settings()
    try:
        r = httpx.post(
            SPEAK_URL,
            params={"model": s.deepgram_tts_model},
            headers={"Authorization": f"Token {key}", "Content-Type": "application/json"},
            json={"text": text},
            timeout=s.deepgram_timeout_s,
        )
        r.raise_for_status()
        audio = r.content
    except httpx.HTTPError as exc:
        log.warning("speak failed (%s); returning silent audio", exc)
        return SILENT_MP3, "fixture"

    if not audio:
        log.warning("speak returned no audio; returning silent audio")
        return SILENT_MP3, "fixture"
    return audio, "deepgram"


def _fixture_transcript() -> str:
    return fixtures.load_as(fixtures.TRANSCRIPT, TranscribeResponse).text
