"""Fixture loading. §6: the hero path replays in <100ms with no network.

Fixtures are cached after first read, so repeated demo requests never touch disk
twice. Every fixture is validated against schemas.py on load — a fixture that has
drifted from the contract fails here, loudly, and not on stage.
"""

import json
from functools import lru_cache
from typing import Any, TypeVar

from pydantic import BaseModel

from apps.api.config import FIXTURE_DIR

T = TypeVar("T", bound=BaseModel)


class FixtureError(RuntimeError):
    """A fixture is missing or no longer matches schemas.py."""


@lru_cache
def _read(name: str) -> str:
    path = FIXTURE_DIR / name
    if not path.exists():
        raise FixtureError(f"fixture not found: {path}")
    return path.read_text()


def load_fixture(name: str) -> Any:
    """Raw JSON, no validation. Prefer load_as()."""
    try:
        return json.loads(_read(name))
    except json.JSONDecodeError as exc:
        raise FixtureError(f"fixture {name} is not valid JSON: {exc}") from exc


def load_as(name: str, model: type[T]) -> T:
    """Load and validate against a schemas.py model."""
    return model.model_validate(load_fixture(name))


HERO_PLAN = "hero_plan.json"
FITCHECK_RESULT = "fitcheck_result.json"
CHECKOUT_APPROVED = "checkout_approved.json"
TRANSCRIPT = "transcript.json"
