"""End to end, with the live resolver and savings rather than the fixture."""

from unittest.mock import patch

import pytest

from apps.api import fixtures
from apps.api.models.schemas import Plan, Rung
from apps.api.db import repo
from apps.api.services import planner, products

DEMO_USER = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def built() -> Plan:
    with patch.object(products, "fetch_products", return_value=[]):
        return planner.build_plan(
            "business casual for my internship", user_id=DEMO_USER, budget_cents=15000
        )


@pytest.fixture(autouse=True)
def no_live_product_search(monkeypatch):
    monkeypatch.setattr(products, "fetch_products", lambda *args, **kwargs: [])


def test_built_plan_validates_against_the_contract(built):
    Plan.model_validate(built.model_dump())


def test_built_plan_matches_the_fixture_where_it_counts(built):
    """Live pipeline and hero fixture must agree on rungs, prices and the
    recommendation — otherwise the demo changes when DEMO_MODE flips."""
    fixture = fixtures.load_as(fixtures.HERO_PLAN, Plan)

    assert [n.label for n in built.needs] == [n.label for n in fixture.needs]
    for live, fixed in zip(built.needs, fixture.needs):
        assert live.recommended_listing_id == fixed.recommended_listing_id
        assert [o.rung for o in live.options] == [o.rung for o in fixed.options]
        assert [o.price_cents for o in live.options] == [o.price_cents for o in fixed.options]


def test_built_impact_matches_the_fixture(built):
    assert built.impact == fixtures.load_as(fixtures.HERO_PLAN, Plan).impact


def test_plan_comes_in_under_budget(built):
    assert built.impact.plan_cents <= built.budget_cents


def test_recommendations_prefer_the_lower_rungs(built):
    rungs = {
        n.label: next(o.rung for o in n.options if o.listing_id == n.recommended_listing_id)
        for n in built.needs
    }
    assert Rung.NEW not in rungs.values(), "nothing here needs buying new"


def test_build_is_deterministic():
    a = planner.build_plan("x", user_id=DEMO_USER, budget_cents=1000, mission_id="m")
    b = planner.build_plan("x", user_id=DEMO_USER, budget_cents=1000, mission_id="m")
    assert a == b


def test_unknown_user_still_gets_a_plan():
    """No prefs on file is neutral, not a crash."""
    p = planner.build_plan("x", user_id="00000000-0000-0000-0000-00000000dead", budget_cents=1000)
    assert p.needs


# --- unmet needs stay in the plan ------------------------------------------


def test_unmet_need_stays_in_the_plan_and_does_not_inflate_impact(monkeypatch):
    """The whole reason for keeping unmet needs: an impact number computed over
    a silently shortened plan overstates what the user achieved."""
    from apps.api.services import planner as mod

    real = repo.hero_needs()
    impossible = {
        "id": "00000000-0000-0000-0000-0000000000ff",
        "label": "a tailcoat",
        "rationale": "The dress code says white tie.",
        "category": "outerwear",
        "attrs": {"formality": "white-tie", "style": "tailcoat"},
        "priority": 1,
    }
    monkeypatch.setattr(mod, "needs_for_goal", lambda goal, **kw: (real + [impossible], "live"))

    plan = mod.build_plan("x", user_id=DEMO_USER, budget_cents=15000)

    unmet = [n for n in plan.needs if not n.options]
    assert len(unmet) == 1, "the unmet need must survive into the plan"
    assert unmet[0].label == "a tailcoat"
    assert unmet[0].recommended_listing_id is None
    assert unmet[0].unmet_reason

    # Impact is unchanged by the presence of an unmet need.
    fixture_impact = fixtures.load_as(fixtures.HERO_PLAN, Plan).impact
    assert plan.impact == fixture_impact
