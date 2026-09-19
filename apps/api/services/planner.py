"""Assembles the Plan: needs -> resolver -> savings -> one object.

This is the seam §2 draws between decompose, resolver and savings. Keeping it in
one place means the mission router stays thin and step 7 can swap the needs
source without touching routing or the response shape.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from apps.api.db import repo
from apps.api.models.schemas import Need, Plan
from apps.api.services import resolver, savings


def needs_for_goal(goal_text: str) -> list[dict[str, Any]]:
    """Goal -> need rows.

    STEP 7 replaces this with decompose.py (OpenAI tool-calling, 4s timeout,
    falling back to exactly this). Until then every goal resolves to the hero
    needs, which is honest for a spine and keeps the demo path identical.
    """
    return repo.hero_needs()


def build_plan(
    goal_text: str,
    *,
    user_id: str,
    budget_cents: int,
    mission_id: Optional[str] = None,
) -> Plan:
    listings = repo.listings()
    users = repo.users_by_id()
    prefs = repo.prefs_for(user_id)

    need_rows = needs_for_goal(goal_text)
    needs: list[Need] = []
    categories: dict[str, str] = {}

    for row in need_rows:
        options, recommended = resolver.resolve_need(
            row, listings, users=users, viewer_id=user_id, prefs=prefs
        )
        if not options:
            # No candidate anywhere on the ladder. Dropping the need is wrong —
            # it would silently shrink the plan and flatter the impact number —
            # but §4 has no shape for an unmet need, so surface it and move on.
            # TODO: raise with the team; the UI may want an "unmet" state.
            continue
        categories[row["id"]] = row["category"]
        needs.append(
            Need(
                need_id=row["id"],
                label=row["label"],
                rationale=row["rationale"],
                priority=row["priority"],
                options=options,
                recommended_listing_id=recommended,
            )
        )

    return Plan(
        mission_id=mission_id or str(uuid.uuid4()),
        goal_text=goal_text,
        budget_cents=budget_cents,
        needs=needs,
        impact=savings.compute(needs, categories=categories),
    )
