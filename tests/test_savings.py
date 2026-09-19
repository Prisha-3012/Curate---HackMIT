"""The impact number must be arithmetic, not decoration."""

import json

import pytest

from apps.api import fixtures
from apps.api.config import SEED_DIR
from apps.api.models.schemas import Plan, Rung
from apps.api.services import savings


@pytest.fixture(scope="module")
def plan() -> Plan:
    return fixtures.load_as(fixtures.HERO_PLAN, Plan)


@pytest.fixture(scope="module")
def categories() -> dict:
    rows = json.loads((SEED_DIR / "data" / "hero_needs.json").read_text())
    return {r["id"]: r["category"] for r in rows}


def test_computed_impact_matches_the_hand_written_fixture(plan, categories):
    """Step 2 wrote the impact block by hand; step 6 computes it. If these ever
    disagree the demo shows one number and the code believes another."""
    assert savings.compute(plan.needs, categories=categories) == plan.impact


def test_saved_is_baseline_minus_plan(plan, categories):
    i = savings.compute(plan.needs, categories=categories)
    assert i.saved_cents == i.baseline_cents - i.plan_cents


def test_items_reused_excludes_new(plan, categories):
    i = savings.compute(plan.needs, categories=categories)
    chosen = savings.recommended_options(plan.needs)
    assert i.items_reused == sum(1 for _, o in chosen if o.rung is not Rung.NEW)


def test_a_new_purchase_avoids_no_textile(plan, categories):
    """Buying new manufactures a garment; nothing is avoided."""
    all_new = plan.model_copy(deep=True)
    for need in all_new.needs:
        for opt in need.options:
            opt.rung = Rung.NEW
    i = savings.compute(all_new.needs, categories=categories)
    assert i.textile_kg_avoided == 0.0
    assert i.items_reused == 0


def test_an_empty_plan_is_all_zeros():
    i = savings.compute([])
    assert (i.baseline_cents, i.plan_cents, i.saved_cents, i.items_reused) == (0, 0, 0, 0)


def test_unknown_category_falls_back_rather_than_crashing(plan):
    i = savings.compute(plan.needs, categories={})
    assert i.textile_kg_avoided > 0


def test_constants_file_is_the_source_of_the_weights():
    table = savings.constants()["textile_kg_per_category"]
    assert savings.textile_kg_for("outerwear") == table["outerwear"]


def test_missing_recommendation_is_skipped_not_costed_as_zero(plan, categories):
    """A need recommending a listing that isn't among its options is a resolver
    bug. It must not silently contribute 0 to the plan cost."""
    broken = plan.model_copy(deep=True)
    broken.needs[0].recommended_listing_id = "not-a-real-listing"
    assert len(savings.recommended_options(broken.needs)) == len(plan.needs) - 1
