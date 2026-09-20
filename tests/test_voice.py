"""Deepgram in, fixtures on failure. ARCHITECTURE.md §4, §8.

Nothing here reaches the network: httpx.post is stubbed throughout and
conftest blanks the key, so these behave the same on a machine with
credentials and one without.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

from apps.api import fixtures
from apps.api.main import app
from apps.api.models.schemas import TranscribeResponse
from apps.api.services import voice

AUDIO = b"\x00\x01\x02 pretend this is opus"


def _settings(**overrides):
    from types import SimpleNamespace
    base = {
        "deepgram_api_key": "dg-key",
        "deepgram_stt_model": "nova-3",
        "deepgram_tts_model": "aura-asteria-en",
        "deepgram_timeout_s": 6.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture()
def with_key(monkeypatch):
    def _apply(**overrides):
        monkeypatch.setattr(voice, "get_settings", lambda: _settings(**overrides))
    return _apply


def _listen_response(transcript, confidence=0.98):
    return httpx.Response(
        200,
        json={"results": {"channels": [{"alternatives": [
            {"transcript": transcript, "confidence": confidence}
        ]}]}},
        request=httpx.Request("POST", voice.LISTEN_URL),
    )


# --- transcribe ------------------------------------------------------------


def test_without_a_key_the_fixture_transcript_is_used():
    text, source = voice.transcribe(AUDIO)
    assert source == "fixture"
    assert text == fixtures.load_as(fixtures.TRANSCRIPT, TranscribeResponse).text


def test_a_real_transcript_is_returned_and_labelled(with_key, monkeypatch):
    with_key()
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: _listen_response("a dinner for twelve")
    )
    text, source = voice.transcribe(AUDIO)
    assert (text, source) == ("a dinner for twelve", "deepgram")


def test_smart_format_is_requested(with_key, monkeypatch):
    """It renders spoken amounts as digits, so "one hundred dollars" arrives as
    "$100" and the frontend budget parser can read it. Without it every spoken
    mission looks budget-less."""
    with_key()
    seen = {}

    def _capture(url, **kwargs):
        seen["url"] = url
        seen.update(kwargs)
        return _listen_response("My budget is $100.")

    monkeypatch.setattr(httpx, "post", _capture)
    voice.transcribe(AUDIO, content_type="audio/webm;codecs=opus")

    assert seen["url"] == voice.LISTEN_URL
    assert seen["params"]["smart_format"] == "true"
    assert seen["params"]["model"] == "nova-3"
    assert seen["headers"]["Authorization"] == "Token dg-key"
    # The browser's own container type is passed straight through.
    assert seen["headers"]["Content-Type"] == "audio/webm;codecs=opus"
    assert seen["content"] == AUDIO


def test_silence_stays_silent_rather_than_becoming_the_hero_goal(with_key, monkeypatch):
    """The caller asked what was said. Answering silence with "business casual
    for my internship" is the same lie as an unlabelled hero fixture."""
    with_key()
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _listen_response(""))
    text, source = voice.transcribe(AUDIO)
    assert text == ""
    assert source == "deepgram"


def test_an_empty_upload_is_not_sent_to_deepgram(with_key, monkeypatch):
    with_key()

    def _boom(*a, **k):
        raise AssertionError("should not call Deepgram with no audio")

    monkeypatch.setattr(httpx, "post", _boom)
    assert voice.transcribe(b"") == ("", "deepgram")


@pytest.mark.parametrize(
    "failure",
    [
        lambda *a, **k: (_ for _ in ()).throw(httpx.TimeoutException("slow")),
        lambda *a, **k: httpx.Response(401, json={"err": "bad key"},
                                       request=httpx.Request("POST", voice.LISTEN_URL)),
        lambda *a, **k: httpx.Response(200, json={"unexpected": "shape"},
                                       request=httpx.Request("POST", voice.LISTEN_URL)),
    ],
    ids=["timeout", "rejected", "bad-shape"],
)
def test_transcribe_failures_fall_back_to_the_fixture(with_key, monkeypatch, failure):
    with_key()
    monkeypatch.setattr(httpx, "post", failure)
    text, source = voice.transcribe(AUDIO)
    assert source == "fixture"
    assert text


# --- speak -----------------------------------------------------------------


def test_without_a_key_speak_returns_silent_audio():
    audio, source = voice.speak("hello")
    assert (audio, source) == (voice.SILENT_MP3, "fixture")


def test_real_audio_is_returned_and_labelled(with_key, monkeypatch):
    with_key()
    mp3 = b"ID3fake-mp3-bytes"
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **k: httpx.Response(200, content=mp3,
                                       request=httpx.Request("POST", voice.SPEAK_URL)),
    )
    audio, source = voice.speak("your plan saves you $275")
    assert (audio, source) == (mp3, "deepgram")


def test_empty_text_is_not_sent_for_synthesis(with_key, monkeypatch):
    with_key()

    def _boom(*a, **k):
        raise AssertionError("should not synthesise an empty string")

    monkeypatch.setattr(httpx, "post", _boom)
    assert voice.speak("   ") == (voice.SILENT_MP3, "fixture")


def test_speak_failure_still_returns_playable_audio(with_key, monkeypatch):
    """A JSON error body would be handed to an <audio> element that cannot play
    it. Silent MP3 keeps the contract."""
    with_key()
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **k: httpx.Response(500, json={"err": "down"},
                                       request=httpx.Request("POST", voice.SPEAK_URL)),
    )
    audio, source = voice.speak("anything")
    assert (audio, source) == (voice.SILENT_MP3, "fixture")


# --- routes ----------------------------------------------------------------


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "off")
    return TestClient(app)


def test_transcribe_route_keeps_the_contract_and_labels_provenance(client):
    r = client.post("/api/voice/transcribe", files={"audio": ("clip.webm", AUDIO, "audio/webm")})
    assert r.status_code == 200
    assert set(r.json()) == {"text"}, "§4 fixes the body to {text}"
    assert r.headers["X-Voice-Source"] == "fixture"


def test_speak_route_returns_audio_not_json(client):
    r = client.post("/api/voice/speak", json={"text": "your plan saves you $275"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content
    assert r.headers["X-Voice-Source"] == "fixture"
