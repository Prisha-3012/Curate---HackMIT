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
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    cybersource_merchant_id: Optional[str] = None
    cybersource_key_id: Optional[str] = None
    cybersource_secret_key: Optional[str] = None
    #: Sandbox by default; production is api.cybersource.com.
    cybersource_environment: str = "apitest.cybersource.com"

    deepgram_api_key: Optional[str] = None

    #: §6: the one live call keeps a 4s timeout and falls back to the fixture.
    openai_timeout_s: float = 4.0
    cybersource_timeout_s: float = 8.0
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
