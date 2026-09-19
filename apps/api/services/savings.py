"""The impact number. ARCHITECTURE.md §4.

    baseline_cents  - what this plan would cost if every need were bought NEW
    plan_cents      - what the recommended options actually cost
    saved_cents     - the difference
    items_reused    - recommended options not on the NEW rung
    textile_kg_avoided - reuse converted to material not manufactured

One honest number beats a big one. §4 puts `assumptions_note` on the object
precisely so the figure carries its own caveat, and §5's "a LOW result shown
honestly beats a fake HIGH" is the same instinct applied to sizing.

BASELINE CHOICE, worth knowing when reading the number: baseline is the sum of
the recommended options' retail_cents — what that same wardrobe costs at full
price. The alternative, summing each need's cheapest NEW option, flatters the
result whenever no NEW listing exists for a need, because the need then
contributes nothing to the baseline while still contributing to the plan. Retail
is the stabler comparison and it is what §3 says retail_cents is for.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Iterable, Optional

from apps.api.config import SEED_DIR
from apps.api.models.schemas import Impact, Need, Option, Rung

CONSTANTS_PATH = SEED_DIR / "impact_constants.json"

#: Used when impact_constants.json is missing or malformed. Conservative on
#: purpose: a missing constants file should understate impact, never inflate it.
_FALLBACK_KG = {"top": 2.1, "bottom": 3.4, "outerwear": 5.9, "footwear": 1.4, "other": 1.0}

ASSUMPTIONS_NOTE = "Estimates. See seed/impact_constants.json for sources."


@lru_cache
def constants() -> dict[str, Any]:
    try:
        return json.loads(CONSTANTS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {"textile_kg_per_category": dict(_FALLBACK_KG)}


def textile_kg_for(category: str) -> float:
    """Textile avoided by NOT buying one new item in this category.

    Returns 0.0 for anything that isn't a garment. Categories are free-form
    since 2026-09-19, so a plan can be about camping stoves or stockpots —
    crediting those with an "other" fallback would report textile avoided for
    borrowing a saucepan, which is the kind of inflated number the impact block
    exists to avoid. Unknown category means unknown impact, and the honest
    answer to that is zero.
    """
    table = constants().get("textile_kg_per_category") or _FALLBACK_KG
    return float(table.get(category, 0.0))


def recommended_options(needs: Iterable[Need]) -> list[tuple[Need, Option]]:
    """The one option per need that the plan actually recommends.

    A need whose recommendation isn't among its own options is a resolver bug,
    not something to paper over — it's skipped here and caught by the contract
    test rather than silently costed as zero.
    """
    out: list[tuple[Need, Option]] = []
    for need in needs:
        if need.recommended_listing_id is None:
            # Unmet — nothing was acquired, so it contributes to neither the
            # plan cost nor the baseline. A budget-dropped need still carries
            # its options; counting those would claim savings never realised.
            continue
        match = next(
            (o for o in need.options if o.listing_id == need.recommended_listing_id),
            None,
        )
        if match is not None:
            out.append((need, match))
    return out


def compute(
    needs: Iterable[Need],
    *,
    categories: Optional[dict[str, str]] = None,
) -> Impact:
    """Build the Impact block from a resolved plan.

    `categories` maps need_id -> category. §4 doesn't serialize need.category, so
    the caller passes it through from the needs rows. A category with no textile
    constant contributes 0.0 — see textile_kg_for.
    """
    categories = categories or {}
    chosen = recommended_options(needs)

    baseline = sum(opt.retail_cents for _, opt in chosen)
    plan = sum(opt.price_cents for _, opt in chosen)
    reused = sum(1 for _, opt in chosen if opt.rung is not Rung.NEW)

    kg = 0.0
    for need, opt in chosen:
        if opt.rung is Rung.NEW:
            continue  # a new garment is manufactured; nothing is avoided
        kg += textile_kg_for(categories.get(need.need_id, "other"))

    return Impact(
        baseline_cents=baseline,
        plan_cents=plan,
        saved_cents=baseline - plan,
        items_reused=reused,
        textile_kg_avoided=round(kg, 1),
        assumptions_note=ASSUMPTIONS_NOTE,
    )
