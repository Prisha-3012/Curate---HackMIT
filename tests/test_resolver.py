"""The ladder must behave, and it must reproduce the hero plan.

That second property is the one that protects the demo: when resolver.py goes
live the plan is built from seeded listings instead of hero_plan.json, and if the
two disagree the demo silently changes between rehearsal and stage.
"""

import pytest

from apps.api.db import repo
from apps.api.models.schemas import Rung
from apps.api.services.resolver import (
    LADDER,
    MATCH_THRESHOLD,
    attribute_overlap,
    preference_bonus,
    resolve_need,
    score_listing,
)


@pytest.fixture(scope="module")
def listings():
    return repo.listings()


@pytest.fixture(scope="module")
def needs():
    return repo.hero_needs()


@pytest.fixture(scope="module")
def users():
    return repo.users_by_id()


DEMO_USER = "00000000-0000-0000-0000-000000000001"


def _resolve_full(need, listings, users):
    return resolve_need(
        need,
        listings,
        users=users,
        viewer_id=DEMO_USER,
        prefs=repo.prefs_for(DEMO_USER),
    )


def _resolve(need, listings, users):
    """(options, recommended) — drops the unmet reason, which met needs never have."""
    options, recommended, _reason = _resolve_full(need, listings, users)
    return options, recommended


# --- scoring primitives ----------------------------------------------------


def test_overlap_is_the_share_of_need_attrs_satisfied():
    need = {"formality": "business-casual", "collar": True}
    assert attribute_overlap(need, {"formality": "business-casual", "collar": True}) == 1.0
    assert attribute_overlap(need, {"formality": "business-casual", "collar": False}) == 0.5
    assert attribute_overlap(need, {"formality": "casual", "collar": False}) == 0.0


def test_overlap_accepts_a_list_of_acceptable_values():
    need = {"formality": ["business-casual", "formal"]}
    assert attribute_overlap(need, {"formality": "formal"}) == 1.0
    assert attribute_overlap(need, {"formality": "athletic"}) == 0.0


def test_a_need_with_no_attrs_is_satisfied_by_anything():
    assert attribute_overlap({}, {"color": "navy"}) == 1.0


def test_missing_key_counts_as_a_miss_not_a_crash():
    assert attribute_overlap({"warmth": "medium"}, {"color": "navy"}) == 0.0


# --- taste nudges but never vetoes -----------------------------------------


def test_preference_bonus_rewards_liked_colors_and_punishes_avoided():
    prefs = {"colors": ["navy"], "avoid_colors": ["neon"]}
    assert preference_bonus({"attrs": {"color": "navy"}}, prefs) > 0
    assert preference_bonus({"attrs": {"color": "neon"}}, prefs) < 0
    assert preference_bonus({"attrs": {"color": "beige"}}, prefs) == 0


def test_empty_prefs_are_neutral():
    assert preference_bonus({"attrs": {"color": "navy"}}, {}) == 0.0


def test_taste_cannot_rescue_a_listing_that_matches_nothing():
    """A loved colour on the wrong garment is still the wrong garment."""
    need = {"category": "top", "attrs": {"formality": "business-casual"}}
    listing = {"attrs": {"formality": "athletic", "color": "navy"}, "brand": "X"}
    assert score_listing(listing, need, {"colors": ["navy"]}) == 0.0


def test_taste_breaks_ties_between_equally_good_matches():
    need = {"category": "top", "attrs": {"formality": "business-casual"}}
    liked = {"attrs": {"formality": "business-casual", "color": "navy"}, "brand": "X"}
    plain = {"attrs": {"formality": "business-casual", "color": "beige"}, "brand": "X"}
    assert score_listing(liked, need, {"colors": ["navy"]}) > score_listing(plain, need, {"colors": ["navy"]})


# --- the ladder ------------------------------------------------------------


def test_ladder_order_is_the_doc_order():
    assert LADDER == (Rung.OWN, Rung.BORROW, Rung.USED, Rung.NEW)


def test_rung_beats_score(listings, needs, users):
    """The whole thesis: a better-matching NEW item must not displace a borrowed
    one that clears the bar."""
    shirts = next(n for n in needs if n["category"] == "top")
    options, recommended = _resolve(shirts, listings, users)

    rec = next(o for o in options if o.listing_id == recommended)
    assert rec.rung is Rung.BORROW

    new_opts = [o for o in options if o.rung is Rung.NEW]
    assert new_opts, "seed should offer a NEW shirt for this to be a real test"
    assert max(o.match_score for o in new_opts) >= rec.match_score, (
        "the NEW option should score at least as well, which is exactly why "
        "rung-first matters"
    )


def test_options_are_returned_in_ladder_order(listings, needs, users):
    for need in needs:
        options, _ = _resolve(need, listings, users)
        positions = [LADDER.index(o.rung) for o in options]
        assert positions == sorted(positions)


def test_one_option_per_rung(listings, needs, users):
    for need in needs:
        options, _ = _resolve(need, listings, users)
        rungs = [o.rung for o in options]
        assert len(rungs) == len(set(rungs))


def test_recommended_is_always_one_of_the_options(listings, needs, users):
    for need in needs:
        options, recommended = _resolve(need, listings, users)
        assert recommended in {o.listing_id for o in options}


def test_wrong_category_is_never_offered(listings, needs, users):
    """Sneakers must not turn up as an answer to 'collared shirts'."""
    shirts = next(n for n in needs if n["category"] == "top")
    options, _ = _resolve(shirts, listings, users)
    titles = {o.title for o in options}
    assert "White canvas sneakers" not in titles
    assert "Grey hoodie" not in titles, "a hoodie has no collar and isn't business-casual"


def test_the_neon_windbreaker_is_rejected(listings, needs, users):
    """It's athletic, it's the wrong warmth, and the user's prefs avoid neon.
    Seeded specifically so the resolver can be seen declining something."""
    layer = next(n for n in needs if n["category"] == "outerwear")
    options, _ = _resolve(layer, listings, users)
    assert "Neon windbreaker, M" not in {o.title for o in options}


def test_own_and_borrow_options_are_free(listings, needs, users):
    for need in needs:
        options, _ = _resolve(need, listings, users)
        for o in options:
            if o.rung in (Rung.OWN, Rung.BORROW):
                assert o.price_cents == 0


def test_resolution_is_deterministic(listings, needs, users):
    """Same seed, same plan — every time, or GET/POST disagree."""
    for need in needs:
        first = _resolve(need, listings, users)
        second = _resolve(need, listings, users)
        assert first == second


# --- it reproduces the hero plan -------------------------------------------


HERO_RECOMMENDATIONS = {
    "a pair of non-sneaker shoes": "1c4d7e20-8a9b-4c3d-9e51-6f2a8b0c4d71",  # OWN oxfords
    "two collared shirts you can rotate": "3e6f9a42-0c1d-4e5f-9a73-8b4c0d2e6f93",  # BORROW Maya
    "one layer for over-air-conditioned offices": "6192cd75-3f40-4b82-8da6-1e7f305092c6",  # USED blazer
}


def test_resolver_reproduces_hero_recommendations(listings, needs, users):
    for need in needs:
        _, recommended = _resolve(need, listings, users)
        assert recommended == HERO_RECOMMENDATIONS[need["label"]], (
            f"live resolver picks a different option for {need['label']!r} than "
            f"the hero fixture — the demo would change under us"
        )


def test_resolver_reproduces_hero_option_counts(listings, needs, users):
    expected = {
        "a pair of non-sneaker shoes": 2,
        "two collared shirts you can rotate": 3,
        "one layer for over-air-conditioned offices": 2,
    }
    for need in needs:
        options, _ = _resolve(need, listings, users)
        assert len(options) == expected[need["label"]]


def test_recommended_options_clear_the_threshold(listings, needs, users):
    for need in needs:
        options, recommended = _resolve(need, listings, users)
        rec = next(o for o in options if o.listing_id == recommended)
        assert rec.match_score >= MATCH_THRESHOLD


def test_why_text_quotes_a_real_discount(listings, needs, users):
    """§4's 'Secondhand, 74% below retail.' — the number must be true."""
    shoes = next(n for n in needs if n["category"] == "footwear")
    options, _ = _resolve(shoes, listings, users)
    used = next(o for o in options if o.rung is Rung.USED)
    pct = round((used.retail_cents - used.price_cents) / used.retail_cents * 100)
    assert f"{pct}%" in used.why


def test_fitcheck_gate_applied_to_live_options(listings, needs, users):
    shoes = next(n for n in needs if n["category"] == "footwear")
    options, _ = _resolve(shoes, listings, users)
    assert not any(o.needs_fitcheck for o in options), "footwear is never fit-checkable"

    shirts = next(n for n in needs if n["category"] == "top")
    options, _ = _resolve(shirts, listings, users)
    flagged = {o.rung for o in options if o.needs_fitcheck}
    assert flagged == {Rung.USED, Rung.NEW}


# --- unmet needs (§4 extension, 2026-09-19) --------------------------------


def test_a_need_with_no_candidates_is_unmet_not_dropped(listings, users):
    """Dropping it would shrink the plan silently and flatter the impact number."""
    impossible = {
        "id": "00000000-0000-0000-0000-0000000000ff",
        "label": "a tailcoat",
        "rationale": "The dress code says white tie.",
        "category": "outerwear",
        "attrs": {"formality": "white-tie", "style": "tailcoat"},
        "priority": 1,
    }
    options, recommended, reason = _resolve_full(impossible, listings, users)
    assert options == []
    assert recommended is None
    assert reason


def test_unmet_reason_is_specific_enough_to_act_on(listings, users):
    """'Nothing matched' tells the user nothing they can do about it."""
    impossible = {
        "id": "00000000-0000-0000-0000-0000000000fe",
        "label": "a tailcoat",
        "rationale": "x",
        "category": "outerwear",
        "attrs": {"formality": "white-tie", "style": "tailcoat"},
        "priority": 1,
    }
    _, _, reason = _resolve_full(impossible, listings, users)
    assert "a tailcoat" in reason
    assert any(tok in reason for tok in ("best", "category"))


def test_empty_category_says_so(listings, users):
    need = {
        "id": "00000000-0000-0000-0000-0000000000fd",
        "label": "a hat",
        "rationale": "x",
        "category": "other",
        "attrs": {"formality": "business-casual"},
        "priority": 2,
    }
    _, _, reason = _resolve_full(need, listings, users)
    assert "nothing to rank" in reason


def test_met_needs_carry_no_unmet_reason(listings, needs, users):
    for need in needs:
        _, _, reason = _resolve_full(need, listings, users)
        assert reason is None
