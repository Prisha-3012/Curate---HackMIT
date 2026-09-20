"""The pipeline must work for goals that aren't about clothes.

Success is explicitly NOT "the wardrobe fixture still passes". These exercise
camping and dinner-hosting through the real resolver, real budget enforcement
and real impact maths. Only the OpenAI call is stubbed — with output shaped
exactly as decompose.py emits it.
"""

import json

import pytest

from apps.api.config import SEED_DIR
from apps.api.models.schemas import Plan, Rung
from apps.api.services import planner

DEMO_USER = "00000000-0000-0000-0000-000000000001"
DOMAINS = json.loads((SEED_DIR / "data" / "domain_needs.json").read_text())


@pytest.fixture()
def plan_for(monkeypatch):
    def _build(domain: str, budget_cents: int) -> Plan:
        monkeypatch.setattr(
            planner, "needs_for_goal", lambda goal, **kw: (DOMAINS[domain], "live")
        )
        return planner.build_plan(
            f"{domain} goal", user_id=DEMO_USER, budget_cents=budget_cents
        )
    return _build


def _rec(need):
    return next((o for o in need.options if o.listing_id == need.recommended_listing_id), None)


# --- camping ---------------------------------------------------------------


def test_camping_plan_resolves(plan_for):
    plan = plan_for("camping", 20000)
    Plan.model_validate(plan.model_dump())
    met = [n for n in plan.needs if n.recommended_listing_id]
    assert len(met) == 4, "every camping need should resolve against the seed"


def test_camping_prefers_owned_and_used(plan_for):
    plan = plan_for("camping", 20000)
    rungs = {n.label: _rec(n).rung for n in plan.needs if n.recommended_listing_id}
    assert rungs["shelter for five people"] is Rung.OWN
    assert rungs["stay warm overnight"] is Rung.OWN
    assert rungs["cook hot food"] is Rung.USED
    assert Rung.NEW not in rungs.values()


def test_camping_ladder_beats_score(plan_for):
    """A USED stove wins even though the NEW option scores at least as well."""
    plan = plan_for("camping", 20000)
    need = next(n for n in plan.needs if n.label == "cook hot food")
    rec = _rec(need)
    assert rec.rung is Rung.USED
    later = [o for o in need.options if o.rung is Rung.NEW]
    assert later, "seed should offer paid stoves for this to prove anything"
    assert max(o.match_score for o in later) >= rec.match_score


# --- dinner ----------------------------------------------------------------


def test_dinner_plan_resolves(plan_for):
    plan = plan_for("dinner", 15000)
    Plan.model_validate(plan.model_dump())
    assert [n for n in plan.needs if n.recommended_listing_id]


def test_dinner_uses_owned_and_used_first(plan_for):
    plan = plan_for("dinner", 15000)
    rungs = {n.label: _rec(n).rung for n in plan.needs if n.recommended_listing_id}
    assert rungs["cook for a crowd"] is Rung.OWN          # user's stockpot
    assert rungs["somewhere for twelve people to sit"] is Rung.USED
    assert rungs["keep food and drinks cold"] is Rung.USED


def test_dinner_impact_reflects_used_purchases(plan_for):
    """Without BORROW, the dinner needs backed only by USED options cost money."""
    plan = plan_for("dinner", 15000)
    assert plan.impact.plan_cents == 6000
    assert plan.impact.saved_cents == (
        plan.impact.baseline_cents - plan.impact.plan_cents
    )


# --- domains don't leak into each other ------------------------------------


def test_categories_are_hard_filtered_across_domains(plan_for):
    """A tent must never be offered as an answer to "somewhere to sit"."""
    plan = plan_for("dinner", 15000)
    titles = {o.title for n in plan.needs for o in n.options}
    assert not any("tent" in t.lower() for t in titles)
    assert not any("sleeping" in t.lower() for t in titles)


def test_impact_is_domain_agnostic(plan_for):
    """textile_kg constants are clothing-specific; a camping plan must still
    produce a coherent impact block rather than crashing or inventing weight."""
    plan = plan_for("camping", 20000)
    assert plan.impact.baseline_cents > 0
    assert plan.impact.saved_cents == plan.impact.baseline_cents - plan.impact.plan_cents
    assert plan.impact.items_reused >= 1


# --- honesty across domains -------------------------------------------------


def test_why_text_makes_no_clothing_assumptions(plan_for):
    """Regression: a tent was described as matching "the formality this goal
    needs", and a cooler as risking "no sizing gamble"."""
    banned = ("formality", "sizing", "fit", "wear", "size")
    for domain in ("camping", "dinner"):
        plan = plan_for(domain, 20000)
        for need in plan.needs:
            for opt in need.options:
                low = opt.why.lower()
                assert not any(w in low for w in banned), (
                    f"{domain}: {opt.title!r} why-text assumes clothing: {opt.why!r}"
                )


def test_no_textile_claimed_for_non_textile_categories(plan_for):
    """Borrowing a camp stove avoids no textile. Claiming otherwise inflates the
    one number that must never be inflated."""
    plan = plan_for("camping", 20000)
    assert plan.impact.textile_kg_avoided == 0.0
    assert plan.impact.saved_cents > 0, "money saved is still real and reported"


def test_clothing_still_earns_textile_credit():
    from apps.api.services import savings
    assert savings.textile_kg_for("outerwear") > 0
    assert savings.textile_kg_for("shelter") == 0.0
    assert savings.textile_kg_for("nonsense-token") == 0.0


# --- a domain the catalogue does not cover ---------------------------------

#: Defined here, not in seed/data, on purpose. The seed pool is not expanded to
#: chase new domains — a goal the catalogue cannot answer SHOULD come back
#: unmet, and that honesty is the behaviour under test.
BIKE_NEEDS = [
    {
        "id": "44444444-0000-4000-8000-000000000001",
        "label": "keep the drivetrain running",
        "rationale": "A seized chain ends the ride regardless of anything else.",
        "category": "bike-maintenance",
        "attrs": {"tool": "chain", "portable": True},
        "priority": 1,
    },
    {
        "id": "44444444-0000-4000-8000-000000000002",
        "label": "be visible after sunset",
        "rationale": "The ride finishes in the dark and drivers need to see you.",
        "category": "lighting",
        "attrs": {"portable": True},
        "priority": 1,
    },
]


def test_an_uncovered_domain_decomposes_and_reports_unmet_honestly(plan_for, monkeypatch):
    """A goal outside the catalogue must NOT be quietly answered with whatever
    is lying around. The need survives into the plan, says why it failed, and
    contributes nothing to the impact number.

    This is the shape of every non-wardrobe goal the seed does not cover, and
    getting it wrong is worse than having no answer: a fabricated match sends
    someone to buy a thing that does not meet their need.
    """
    monkeypatch.setattr(planner, "needs_for_goal", lambda goal, **kw: (BIKE_NEEDS, "live"))
    plan = planner.build_plan(
        "get my bike road-ready", user_id=DEMO_USER, budget_cents=10000
    )
    Plan.model_validate(plan.model_dump())

    by_label = {n.label: n for n in plan.needs}
    assert len(by_label) == 2, "both needs stay in the plan; neither is dropped"

    # Nothing in the catalogue is bike-maintenance, so this one cannot resolve.
    orphan = by_label["keep the drivetrain running"]
    assert orphan.options == []
    assert orphan.recommended_listing_id is None
    assert orphan.unmet_reason
    assert "bike-maintenance" in orphan.unmet_reason, (
        "the reason must name what was missing, not just say nothing matched"
    )

    # 'lighting' exists in the catalogue, so the same goal partly resolves.
    lit = by_label["be visible after sunset"]
    assert lit.recommended_listing_id is not None
    assert lit.unmet_reason is None


def test_an_uncovered_need_never_inflates_the_impact_number(plan_for, monkeypatch):
    """Impact counts met needs only. An unmet need that contributed to
    baseline_cents would claim a saving the user never made."""
    monkeypatch.setattr(planner, "needs_for_goal", lambda goal, **kw: (BIKE_NEEDS, "live"))
    plan = planner.build_plan(
        "get my bike road-ready", user_id=DEMO_USER, budget_cents=10000
    )
    met = [n for n in plan.needs if n.recommended_listing_id]
    assert plan.impact.baseline_cents == sum(_rec(n).retail_cents for n in met)
    assert plan.impact.plan_cents == sum(_rec(n).price_cents for n in met)
    assert plan.impact.saved_cents == plan.impact.baseline_cents - plan.impact.plan_cents


def test_a_wholly_uncovered_goal_returns_no_recommendations_at_all(monkeypatch):
    """The strongest form: nothing in the catalogue fits, so the plan recommends
    nothing and says so, rather than reaching for the nearest wardrobe item."""
    orphan_only = [BIKE_NEEDS[0]]
    monkeypatch.setattr(planner, "needs_for_goal", lambda goal, **kw: (orphan_only, "live"))
    plan = planner.build_plan(
        "get my bike road-ready", user_id=DEMO_USER, budget_cents=10000
    )
    assert all(n.recommended_listing_id is None for n in plan.needs)
    assert all(n.unmet_reason for n in plan.needs)
    assert plan.impact.plan_cents == 0
    assert plan.impact.baseline_cents == 0
    assert plan.impact.saved_cents == 0
    assert plan.impact.items_reused == 0


def test_fixture_needs_make_the_whole_plan_a_fixture(monkeypatch):
    """Without a working API key, decompose returns the seeded WARDROBE needs
    for every goal — so a camping goal comes back with collared shirts.

    Resolution is live, but the plan answers a different question than the one
    asked, and labelling it source="live" is the same lie as serving the hero
    fixture unlabelled. Regression: it did exactly that, because needs_for_goal
    discarded decompose's provenance.
    """
    monkeypatch.setattr(
        planner, "needs_for_goal", lambda goal, **kw: (DOMAINS["camping"], "fixture")
    )
    plan = planner.build_plan(
        "something entirely unrelated", user_id=DEMO_USER, budget_cents=20000
    )
    assert plan.source == "fixture"


def test_a_real_decomposition_is_labelled_live(monkeypatch):
    monkeypatch.setattr(
        planner, "needs_for_goal", lambda goal, **kw: (DOMAINS["camping"], "openai")
    )
    plan = planner.build_plan("a camping trip", user_id=DEMO_USER, budget_cents=20000)
    assert plan.source == "live", "a real provider answered; this plan is live"
