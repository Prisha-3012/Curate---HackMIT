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


@pytest.mark.parametrize("from_database", [False, True])
@pytest.mark.parametrize("scan_state", ["success", "none", "failed-first", "failed-rescan", "other-user"])
def test_scan_excludes_only_current_users_seeded_own(monkeypatch, from_database, scan_state):
    from apps.api.services import wardrobe
    monkeypatch.setattr(wardrobe, "_WARDROBE", {})
    seed = repo._seed("listings.json")
    seeded = next(row for row in seed if row["rung"] == "OWN" and row["owner_id"] == DEMO_USER)
    genuine = {**seeded, "id": "genuine-owned", "title": "Actual possession"}
    other = {**seeded, "id": "other-owned", "owner_id": "other-user"}
    # Even a known seed ID is retained if either the rung or owner differs.
    other_seed_owner = {**seeded, "owner_id": "other-user"}
    changed_rung = {**seeded, "rung": "USED", "owner_id": None}
    base = [seeded, genuine, other, other_seed_owner, changed_rung] + [
        row for row in seed if row["rung"] in ("USED", "NEW")
    ]
    if not from_database:
        base = seed
    monkeypatch.setattr(repo.client, "select", lambda table, **kw: base if from_database and table == "listings" else [])
    item = {"category": "footwear", "title": "Scanned pumps", "attrs": {"formality": "business-casual"}}
    if scan_state in ("success", "failed-rescan"):
        wardrobe.set_wardrobe(DEMO_USER, [item], "gemini")
    elif scan_state == "other-user":
        wardrobe.set_wardrobe("other-user", [item], "gemini")
    # Failed scans do not write inventory; existing route tests verify this.
    monkeypatch.setattr(planner, "needs_for_goal", lambda *a, **kw: ([
        {"id": "need", "label": "Footwear", "rationale": "For the goal", "category": "footwear", "attrs": {}, "priority": 1}
    ], "live"))
    captured = []
    def capture(need, listings, **kwargs):
        captured.extend(listings)
        return [], None, "No candidates"
    monkeypatch.setattr(planner.resolver, "resolve_need", capture)
    planner.build_plan("A goal", user_id=DEMO_USER)
    expected = list(base)
    if scan_state in ("success", "failed-rescan"):
        ids = repo.seeded_own_listing_ids()
        expected = [row for row in expected if not (
            row["id"] in ids and row["rung"] == "OWN" and row.get("owner_id") == DEMO_USER)]
        expected += wardrobe.to_own_listings([item], DEMO_USER)
        assert seeded not in captured
    else:
        assert seeded in captured
    assert captured == expected
    if from_database:
        assert all(row in captured for row in [genuine, other, other_seed_owner, changed_rung])
    assert base[0] == seeded  # Filtering must not mutate repository data.


def test_seeded_own_ids_identify_only_seed_possessions():
    expected = {row["id"] for row in repo._seed("listings.json") if row["rung"] == "OWN"}
    assert repo.seeded_own_listing_ids() == expected
    assert expected
