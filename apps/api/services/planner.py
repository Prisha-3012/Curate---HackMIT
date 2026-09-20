"""Assembles the Plan: goal -> needs -> resolver -> budget -> savings.

This is the seam §2 draws between decompose, resolver and savings.

BUDGET BELONGS HERE, not in the resolver. The resolver answers "what satisfies
this need, cheapest-impact first"; the budget is a constraint across the WHOLE
plan and cannot be evaluated one need at a time. Pushing it into the resolver
would also corrupt rung-beats-score, because the cheapest option for a need is
frequently on a later rung than the right one.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from apps.api.db import repo
from apps.api.models.schemas import Need, Plan, Rung
from apps.api.services import decompose, products, resolver, savings

log = logging.getLogger(__name__)


def needs_for_goal(
    goal_text: str, *, mission_id: str = ""
) -> tuple[list[dict[str, Any]], str]:
    """Goal -> (need rows, provenance), via an LLM with a fixture fallback.

    The provenance is returned, not discarded. When decompose falls back — no
    API key, a timeout, a 403 — the rows are the SEEDED WARDROBE needs whatever
    the goal was, so a camping goal comes back with "two collared shirts". That
    plan does not describe what was asked for and the caller has to be able to
    say so.
    """
    return decompose.decompose(goal_text, mission_id=mission_id or goal_text)


def _cost_of(need: Need) -> int:
    """What this need's recommendation costs. Zero if unmet."""
    if need.recommended_listing_id is None:
        return 0
    match = next(
        (o for o in need.options if o.listing_id == need.recommended_listing_id), None
    )
    return match.price_cents if match else 0


def enforce_budget(needs: list[Need], budget_cents: Optional[int]) -> list[Need]:
    """Bring the plan within budget, truthfully.

    Needs are dropped to unmet — nice-to-have (priority 2) first, most expensive
    first within a priority — until the total fits. Their options are KEPT so the
    UI can show what existed and say it was unaffordable, which is different
    information from "nothing matched".

    Deliberately does NOT swap in a cheaper option on a later rung. A discounted
    NEW item is often cheaper than the USED one the ladder chose, and silently
    taking it would invert the product thesis to hit a number. Going without is
    the honest answer, and it is the answer ENOUGH exists to give.
    """
    # None means no budget was stated, so there is nothing to enforce. ZERO IS
    # NOT NONE: a stated $0 budget is a real constraint meaning "only what is
    # free", and it falls through to the loop below, which drops every need
    # whose recommendation costs anything. Treating the two alike (as this did
    # until 2026-09-19) silently spent money the user said they did not have.
    if budget_cents is None:
        return needs

    total = sum(_cost_of(n) for n in needs)
    if total <= budget_cents:
        return needs

    # Most droppable first: priority 2 before 1, dearest before cheapest.
    order = sorted(
        (n for n in needs if n.recommended_listing_id is not None),
        key=lambda n: (-n.priority, -_cost_of(n)),
    )

    dropped: dict[str, str] = {}
    for need in order:
        if total <= budget_cents:
            break
        cost = _cost_of(need)
        if cost <= 0:
            continue  # free: dropping it saves nothing
        total -= cost
        # A stated $0 budget reads badly through the general sentence
        # ("already at the $0.00 budget"), and this string is shown verbatim.
        if budget_cents == 0:
            dropped[need.need_id] = (
                f"Found {len(need.options)} option(s), but the cheapest costs "
                f"${cost / 100:,.2f} and your budget is $0, so only things you "
                f"already own or can borrow can be used. Shown here so you can "
                f"decide, not counted in the totals."
            )
        else:
            dropped[need.need_id] = (
                f"Found {len(need.options)} option(s), but the cheapest that meets "
                f"this need costs ${cost / 100:,.2f} and the plan is already at the "
                f"${budget_cents / 100:,.2f} budget. Shown here so you can decide, "
                f"not counted in the totals."
            )

    if total > budget_cents:
        log.warning(
            "plan still over budget after dropping everything droppable "
            "(%d > %d); the remaining needs are all free", total, budget_cents
        )

    return [
        n.model_copy(
            update={"recommended_listing_id": None, "unmet_reason": dropped[n.need_id]}
        )
        if n.need_id in dropped
        else n
        for n in needs
    ]


def build_plan(
    goal_text: str,
    *,
    user_id: str,
    budget_cents: Optional[int] = None,
    mission_id: Optional[str] = None,
) -> Plan:
    mid = mission_id or str(uuid.uuid4())

    listings = repo.listings()
    users = repo.users_by_id()
    prefs = repo.prefs_for(user_id)

    need_rows, needs_source = needs_for_goal(goal_text, mission_id=mid)
    live_listings = products.fetch_products(goal_text, need_rows)
    if live_listings:
        listings = listings + live_listings
    needs: list[Need] = []
    categories: dict[str, str] = {}

    for row in need_rows:
        options, recommended, unmet_reason = resolver.resolve_need(
            row, listings, users=users, viewer_id=user_id, prefs=prefs
        )
        categories[row["id"]] = row["category"]
        needs.append(
            Need(
                need_id=row["id"],
                label=row["label"],
                rationale=row["rationale"],
                priority=row["priority"],
                options=options,
                recommended_listing_id=recommended,
                unmet_reason=unmet_reason,
            )
        )

    needs = enforce_budget(needs, budget_cents)

    return Plan(
        mission_id=mid,
        goal_text=goal_text,
        budget_cents=budget_cents,
        needs=needs,
        impact=savings.compute(needs, categories=categories),
        # Resolution was live either way, but if the NEEDS are canned then the
        # plan answers a different question than the one asked, which is exactly
        # what source="fixture" exists to declare.
        source="live" if needs_source != "fixture" else "fixture",
    )
