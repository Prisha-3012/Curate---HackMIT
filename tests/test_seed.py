"""The seed must satisfy the SQL constraints before Postgres sees it, and it must
be able to reproduce the hero plan.

That second one matters more than it looks: the hero fixture IS the demo. When
resolver.py goes live in step 5 it builds the plan from these listings instead of
from the fixture, so if the two disagree the demo silently changes.
"""

import json

import pytest

from seed.load import (
    DATA_DIR,
    check_hero_is_reproducible,
    validate,
)


@pytest.fixture(scope="module")
def users() -> list[dict]:
    return json.loads((DATA_DIR / "users.json").read_text())


@pytest.fixture(scope="module")
def listings() -> list[dict]:
    return json.loads((DATA_DIR / "listings.json").read_text())


def test_seed_satisfies_sql_constraints(users, listings) -> None:
    assert validate(users, listings) == []


def test_seed_reproduces_the_hero_plan(listings) -> None:
    assert check_hero_is_reproducible(listings) == []


def test_pool_is_big_enough_to_rank(listings) -> None:
    """A resolver with one candidate per rung isn't ranking, it's looking up."""
    assert len(listings) >= 12


def test_every_rung_is_represented(listings) -> None:
    assert {item["rung"] for item in listings} == {"OWN", "BORROW", "USED", "NEW"}


def test_validate_catches_a_rung_owner_mismatch(users, listings) -> None:
    """Guard the guard: a USED listing with an owner must be rejected."""
    broken = json.loads(json.dumps(listings))
    used = next(item for item in broken if item["rung"] == "USED")
    used["owner_id"] = users[0]["id"]
    errors = validate(users, broken)
    assert any("must not have an owner_id" in e for e in errors)


def test_validate_catches_a_malformed_uuid(users, listings) -> None:
    broken = json.loads(json.dumps(listings))
    broken[0]["id"] = "not-a-uuid"
    assert any("malformed uuid" in e for e in validate(users, broken))


def test_validate_catches_a_priced_own_listing(users, listings) -> None:
    """OWN and BORROW cost nothing — that's what the rung means."""
    broken = json.loads(json.dumps(listings))
    own = next(item for item in broken if item["rung"] == "OWN")
    own["price_cents"] = 1500
    assert any("must be price_cents 0" in e for e in validate(users, broken))
