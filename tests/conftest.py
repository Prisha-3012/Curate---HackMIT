"""Suite-wide guarantee: no test talks to an LLM or speech provider.

decompose.py picks a provider from whatever keys are in the real .env, so the
moment a working key existed, every test that called planner.build_plan without
stubbing started making real API calls — slow, costed, rate-limited, and
non-deterministic, with three planner tests failing because a live
decomposition legitimately does not reproduce the hero needs.

Blanking the keys for every test makes pick_provider return None, so decompose
falls back to the seeded needs and the suite behaves identically whether or not
the machine running it has credentials. Tests that exercise provider selection
patch decompose.get_settings themselves and override this.
"""

from types import SimpleNamespace

import pytest

from apps.api.config import get_settings
from apps.api.services import decompose, voice


@pytest.fixture(autouse=True, scope="session")
def _no_live_llm_calls():
    """Session-scoped deliberately. Higher-scoped fixtures are set up FIRST, so
    a function-scoped guard is applied too late for a module-scoped fixture like
    test_planner's `built`, which calls build_plan at setup time."""
    real = get_settings()
    keyless = SimpleNamespace(
        **{
            **{k: getattr(real, k) for k in type(real).model_fields},
            "openai_api_key": None,
            "xai_api_key": None,
            "gemini_api_key": None,
            "groq_api_key": None,
            "deepgram_api_key": None,
        }
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(decompose, "get_settings", lambda: keyless)
        # voice.py reads the Deepgram key the same way, and a real key in .env
        # would send every voice test to the network.
        mp.setattr(voice, "get_settings", lambda: keyless)
        yield
