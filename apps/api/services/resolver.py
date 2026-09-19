"""The ladder. ARCHITECTURE.md §1, §2.

For each need, walk OWN -> BORROW -> USED -> NEW and return ranked options.

Two rules, and the order matters:

  1. RUNG BEATS SCORE. The recommendation is the earliest rung holding a candidate
     that clears MATCH_THRESHOLD. A better-matching NEW shirt never displaces a
     borrowed one that does the job. This is the whole thesis of the app — the
     impact number counts items_reused, so a ranker that optimised for match
     quality or for price alone would quietly push people toward new production.
  2. WITHIN A RUNG, score decides.

Scoring is plain attribute overlap, no embeddings (per the build order):
  - category is a hard filter
  - each key in need.attrs is worth an equal share; a listing matches a key by
    equality, or by membership if the need states a list of acceptable values
  - user taste (users.prefs) then nudges the result within +/-PREF_WEIGHT

Taste is a nudge, never a veto: it breaks ties between things that already
satisfy the need, and it cannot promote something that doesn't.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from apps.api.models.schemas import Category, Option, Rung, needs_fitcheck_for

#: A candidate must clear this to be recommended for a need.
MATCH_THRESHOLD = 0.60

#: Below this a candidate isn't shown at all — a listing that matches nothing is
#: noise, and showing it makes the ladder look indiscriminate.
MIN_SCORE = 0.35

#: How far taste can move a score, up or down.
PREF_WEIGHT = 0.10

#: §1's order. Index = preference.
LADDER: tuple[Rung, ...] = (Rung.OWN, Rung.BORROW, Rung.USED, Rung.NEW)


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------


def attribute_overlap(need_attrs: dict[str, Any], listing_attrs: dict[str, Any]) -> float:
    """Share of the need's stated attributes this listing satisfies, 0..1.

    A need with no stated attributes is satisfied by anything in the category,
    which is why category is filtered separately and first.
    """
    if not need_attrs:
        return 1.0

    hits = 0.0
    for key, wanted in need_attrs.items():
        if key not in listing_attrs:
            continue
        got = listing_attrs[key]
        if isinstance(wanted, (list, tuple, set)):
            if got in wanted:
                hits += 1.0
        elif got == wanted:
            hits += 1.0
    return hits / len(need_attrs)


def preference_bonus(listing: dict[str, Any], prefs: dict[str, Any]) -> float:
    """Taste nudge in -1..1, scaled by PREF_WEIGHT at the call site.

    Reads users.prefs (added to §3 on 2026-09-19). Absent or empty prefs are
    neutral, so this is safe for users we know nothing about.
    """
    if not prefs:
        return 0.0

    attrs = listing.get("attrs") or {}
    color = attrs.get("color")
    material = attrs.get("material")
    brand = listing.get("brand")
    score = 0.0

    if color:
        if color in (prefs.get("avoid_colors") or []):
            score -= 1.0
        elif color in (prefs.get("colors") or []):
            score += 0.5
    if material and material in (prefs.get("materials_preferred") or []):
        score += 0.3
    if brand and brand in (prefs.get("avoid_brands") or []):
        score -= 1.0

    return max(-1.0, min(1.0, score))


def score_listing(
    listing: dict[str, Any],
    need: dict[str, Any],
    prefs: Optional[dict[str, Any]] = None,
) -> float:
    """Final 0..1 score. Taste can nudge but never rescue a bad match.

    Taste occupies a reserved PREF_WEIGHT slice of the range rather than being
    added on top of the overlap. Adding on top looks simpler but saturates: a
    listing that satisfies every stated attribute already scores 1.0, so the
    bonus clamps away and taste stops discriminating exactly where it is most
    needed — among several candidates that all satisfy the need.
    """
    base = attribute_overlap(need.get("attrs") or {}, listing.get("attrs") or {})
    if base <= 0:
        # Nothing about the need is satisfied. Taste is irrelevant.
        return 0.0
    # preference_bonus is -1..1; map to 0..1 so neutral taste sits mid-slice and
    # a disliked item scores below a neutral one rather than equal to it.
    taste = (preference_bonus(listing, prefs or {}) + 1.0) / 2.0
    adjusted = base * (1.0 - PREF_WEIGHT) + PREF_WEIGHT * taste
    return round(max(0.0, min(1.0, adjusted)), 2)


# --------------------------------------------------------------------------
# presentation
# --------------------------------------------------------------------------


def _owner_label(listing: dict[str, Any], users: dict[str, dict], viewer_id: str) -> str:
    rung = listing["rung"]
    if rung == Rung.OWN.value:
        return "you" if listing.get("owner_id") == viewer_id else "a friend"
    if rung == Rung.BORROW.value:
        owner = users.get(listing.get("owner_id") or "")
        return owner.get("display_name") if owner else "a friend"
    return listing.get("brand") or "retailer"


def _discount_pct(listing: dict[str, Any]) -> Optional[int]:
    retail, price = listing.get("retail_cents") or 0, listing.get("price_cents") or 0
    if retail <= 0 or price >= retail:
        return None
    return round((retail - price) / retail * 100)


def explain(listing: dict[str, Any], need: dict[str, Any], owner_label: str) -> str:
    """The `why` string §4 puts on every option.

    One sentence, specific to the rung, and truthful about why this rung is
    preferred — the UI shows this verbatim next to the price.
    """
    rung = listing["rung"]
    if rung == Rung.OWN.value:
        return "You already own these. They match the formality this goal needs."
    if rung == Rung.BORROW.value:
        return (
            f"{owner_label} has one you can borrow. "
            f"Costs nothing and risks no sizing gamble."
        )
    if rung == Rung.USED.value:
        pct = _discount_pct(listing)
        return f"Secondhand, {pct}% below retail." if pct else "Secondhand."
    return "Buy new only if the borrowed and secondhand options don't work out."


def to_option(
    listing: dict[str, Any],
    need: dict[str, Any],
    score: float,
    users: dict[str, dict],
    viewer_id: str,
) -> Option:
    owner_label = _owner_label(listing, users, viewer_id)
    return Option(
        listing_id=listing["id"],
        rung=Rung(listing["rung"]),
        title=listing["title"],
        owner_label=owner_label,
        price_cents=listing.get("price_cents") or 0,
        retail_cents=listing.get("retail_cents") or 0,
        image_url=listing.get("image_url"),
        match_score=score,
        why=explain(listing, need, owner_label),
        needs_fitcheck=needs_fitcheck_for(
            Category(need["category"]), Rung(listing["rung"])
        ),
    )


# --------------------------------------------------------------------------
# the walk
# --------------------------------------------------------------------------


def resolve_need(
    need: dict[str, Any],
    listings: Iterable[dict[str, Any]],
    *,
    users: Optional[dict[str, dict]] = None,
    viewer_id: str = "",
    prefs: Optional[dict[str, Any]] = None,
) -> tuple[list[Option], Optional[str]]:
    """Walk the ladder for one need.

    Returns (options, recommended_listing_id). Options are the best candidate on
    each rung, in ladder order — one choice per step of the ladder, which is what
    makes the UI legible. recommended is the earliest rung clearing the threshold.
    """
    users = users or {}
    wanted_category = need["category"]

    best_per_rung: dict[Rung, tuple[float, dict[str, Any]]] = {}
    for listing in listings:
        if listing.get("category") != wanted_category:
            continue  # hard filter
        score = score_listing(listing, need, prefs)
        if score < MIN_SCORE:
            continue
        rung = Rung(listing["rung"])
        current = best_per_rung.get(rung)
        # Deterministic: higher score wins; ties break on cheaper, then on id, so
        # the same seed always produces the same plan.
        key = (-score, listing.get("price_cents") or 0, listing["id"])
        if current is None or key < (-current[0], current[1].get("price_cents") or 0, current[1]["id"]):
            best_per_rung[rung] = (score, listing)

    options: list[Option] = []
    recommended: Optional[str] = None
    for rung in LADDER:  # rung beats score
        hit = best_per_rung.get(rung)
        if hit is None:
            continue
        score, listing = hit
        options.append(to_option(listing, need, score, users, viewer_id))
        if recommended is None and score >= MATCH_THRESHOLD:
            recommended = listing["id"]

    # Nothing cleared the bar but something was shown: recommend the best of it
    # rather than handing the UI a null it has no rule for.
    if recommended is None and options:
        recommended = max(options, key=lambda o: o.match_score).listing_id

    return options, recommended
