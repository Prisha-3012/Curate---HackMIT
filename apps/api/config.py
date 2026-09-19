"""Environment config. Every external credential is optional at import time so the
app boots with an empty .env — DEMO_MODE=on needs none of them."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "seed"
FIXTURE_DIR = SEED_DIR / "fixtures"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", extra="ignore", case_sensitive=False
    )

    #: §6 uses the literal strings "on"/"off", not a bool. Kept verbatim.
    demo_mode: str = "off"

    #: Seeded demo user. §4 requires user_id on POST /api/mission but no endpoint
    #: creates one, so it comes from the seed.
    demo_user_id: str = "00000000-0000-0000-0000-000000000001"

    openai_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None
    #: Google AI Studio. Uses Gemini's OpenAI-compatible endpoint.
    gemini_api_key: Optional[str] = None
    #: Groq. Also OpenAI-compatible; far higher free-tier limits than Gemini's
    #: 20 requests/day/model, which is what makes multi-turn dialogue viable.
    groq_api_key: Optional[str] = None
    #: 'xai' | 'openai' | 'auto'. auto prefers whichever key is present,
    #: xAI first.
    llm_provider: str = "auto"
    #: Overrides the provider's default model id.
    llm_model: Optional[str] = None
    #: Model for /api/converse turns. Conversation needs latency over depth —
    #: a lite model answers in ~0.5s where the decomposition model takes 6-9s,
    #: and an 8-second gap between turns is not a conversation. Falls back to
    #: the provider default when unset.
    llm_dialogue_model: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    cybersource_merchant_id: Optional[str] = None
    cybersource_key_id: Optional[str] = None
    cybersource_secret_key: Optional[str] = None
    #: Sandbox by default; production is api.cybersource.com.
    cybersource_environment: str = "apitest.cybersource.com"

    stripe_secret_key: Optional[str] = None

    deepgram_api_key: Optional[str] = None
    #: Deepgram model ids. Overridable for the same reason as LLM_MODEL: they
    #: move, and a retired id is a 4xx that degrades to the fixture silently.
    deepgram_stt_model: str = "nova-3"
    deepgram_tts_model: str = "aura-asteria-en"

    #: §6 specified 4s. Measured: gemini-3.6-flash takes 6-9s for a real
    #: decomposition, so 4s timed out EVERY live call and fell back to fixture
    #: needs — indistinguishable from having no key at all. Demo safety comes
    #: from DEMO_MODE=on (no live call whatsoever), not from this number, so
    #: this is now set to what the work actually costs. Override with
    #: LLM_TIMEOUT_S.
    llm_timeout_s: float = 20.0
    cybersource_timeout_s: float = 8.0
    stripe_timeout_s: float = 8.0
    deepgram_timeout_s: float = 6.0

    @property
    def demo(self) -> bool:
        return self.demo_mode.strip().lower() == "on"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def demo_mode_enabled() -> bool:
    """Read through to the env each call so tests can flip it with monkeypatch."""
    raw = os.getenv("DEMO_MODE")
    if raw is not None:
        return raw.strip().lower() == "on"
    return get_settings().demo
