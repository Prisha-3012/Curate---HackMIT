"""Budget is a constraint across the whole plan, enforced in the planner.

The rule under test: when a plan can't fit, needs are dropped to unmet — never
silently downgraded to a cheaper option on a later rung, because that would
invert the ladder to hit a number.
"""

import json

import pytest

from apps.api.config import SEED_DIR
from apps.api.models.schemas import Plan, Rung
from apps.api.services import planner

DEMO_USER = "00000000-0000-0000-0000-000000000001"
DOMAINS = json.loads((SEED_DIR / "data" / "domain_needs.json").read_text())

#: Needs deliberately chosen so nothing free satisfies them: the user owns no
#: business-casual shoes here, so every option costs money.
PAID_NEEDS = [
    {
        "id": "33333333-0000-4000-8000-000000000001",
        "label": "a warm layer",
        "rationale": "x",
        "category": "outerwear",
        "attrs": {"formality": "business-casual", "warmth": "medium"},
        "priority": 1,
    },
    {
        "id": "33333333-0000-4000-8000-000000000002",
        "label": "smart trousers",
        "rationale": "x",
        "category": "bottom",
        "attrs": {"formality": "business-casual"},
        "priority": 2,
    },
]


@pytest.fixture()
def plan_with(monkeypatch):
    def _build(rows, budget_cents):
        monkeypatch.setattr(planner, "needs_for_goal", lambda goal, **kw: (rows, "live"))
        return planner.build_plan("g", user_id=DEMO_USER, budget_cents=budget_cents)
    return _build


def _rec(need):
    return next((o for o in need.options if o.listing_id == need.recommended_listing_id), None)


def test_generous_budget_changes_nothing(plan_with):
    plan = plan_with(PAID_NEEDS, 100000)
    assert all(n.recommended_listing_id for n in plan.needs)


@pytest.mark.parametrize("budget", [6000, 4000, 1])
def test_plan_is_brought_within_budget(plan_with, budget):
    plan = plan_with(PAID_NEEDS, budget)
    assert plan.impact.plan_cents <= budget


def test_everything_drops_when_even_the_essential_is_unaffordable(plan_with):
    """$40 cannot buy the $55 layer. Reporting a plan anyway would be a lie."""
    plan = plan_with(PAID_NEEDS, 4000)
    assert all(n.recommended_listing_id is None for n in plan.needs)
    assert plan.impact.plan_cents == 0
    assert all(n.unmet_reason for n in plan.needs)


def test_nice_to_have_is_dropped_before_essential(plan_with):
    """priority 2 goes first. Dropping the essential need instead would make the
    plan cheaper and useless.

    $60 is chosen deliberately: the essential layer is $55 and the optional
    trousers $32, so exactly one of them can survive and the choice is forced.
    """
    plan = plan_with(PAID_NEEDS, 6000)
    by_label = {n.label: n for n in plan.needs}
    assert by_label["smart trousers"].recommended_listing_id is None
    assert by_label["a warm layer"].recommended_listing_id is not None


def test_budget_dropped_need_keeps_its_options(plan_with):
    """"Three options exist, none affordable" is different information from
    "nothing matched", and the UI should be able to say which."""
    plan = plan_with(PAID_NEEDS, 4000)
    dropped = next(n for n in plan.needs if n.recommended_listing_id is None)
    assert dropped.options, "options must survive so the UI can show them"
    assert dropped.unmet_reason
    assert "budget" in dropped.unmet_reason.lower()


def test_budget_dropped_need_is_excluded_from_impact(plan_with):
    """Counting an unaffordable option's retail price as 'saved' would claim a
    saving that never happened."""
    plan = plan_with(PAID_NEEDS, 4000)
    met = [n for n in plan.needs if n.recommended_listing_id]
    assert plan.impact.plan_cents == sum(_rec(n).price_cents for n in met)
    assert plan.impact.baseline_cents == sum(_rec(n).retail_cents for n in met)


def test_rung_is_never_downgraded_to_fit_a_budget(plan_with):
    """The cheapest option for a need is often NEW-on-sale. Taking it to hit a
    number would invert the product thesis."""
    generous = plan_with(PAID_NEEDS, 100000)
    tight = plan_with(PAID_NEEDS, 6000)  # tight enough to force a drop, not a wipeout
    for need in tight.needs:
        if need.recommended_listing_id is None:
            continue
        before = next(n for n in generous.needs if n.need_id == need.need_id)
        assert _rec(need).rung is _rec(before).rung


def test_paid_plans_respect_a_tiny_budget_without_downgrading(plan_with):
    """With BORROW removed, paid USED options cannot survive a tiny budget."""
    plan = plan_with(DOMAINS["dinner"], 100)
    assert plan.impact.plan_cents == 0
    assert any(n.recommended_listing_id is None for n in plan.needs)


def test_an_absent_budget_is_unconstrained(plan_with):
    """budget_cents=None means the user stated no budget, so nothing is enforced."""
    plan = plan_with(PAID_NEEDS, None)
    assert all(n.recommended_listing_id for n in plan.needs)


def test_zero_is_a_real_constraint_not_an_absent_budget(plan_with):
    """$0 means $0. These two were the same value until 2026-09-19, so a user
    who said they could spend nothing was handed a plan that spent money.

    Every PAID_NEEDS option costs something, so a $0 budget must meet none of
    them — and must say so rather than returning a cheaper-but-still-paid item.
    """
    plan = plan_with(PAID_NEEDS, 0)
    assert all(n.recommended_listing_id is None for n in plan.needs)
    assert all(n.unmet_reason for n in plan.needs)
    assert plan.impact.plan_cents == 0


def test_zero_budget_still_keeps_owned_options(plan_with):
    """$0 keeps free OWN options while dropping paid USED options."""
    plan = plan_with(DOMAINS["dinner"], 0)
    assert any(n.recommended_listing_id is None for n in plan.needs)
    assert any(
        n.recommended_listing_id
        and _rec(n).rung is Rung.OWN
        for n in plan.needs
    )
    assert plan.impact.plan_cents == 0


def test_zero_budget_reason_explains_the_constraint(plan_with):
    """Shown verbatim in the UI, so it has to read correctly at $0 rather than
    saying the plan is "already at the $0.00 budget"."""
    plan = plan_with(PAID_NEEDS, 0)
    reason = plan.needs[0].unmet_reason
    assert "$0" in reason
    assert "own or can borrow" in reason
