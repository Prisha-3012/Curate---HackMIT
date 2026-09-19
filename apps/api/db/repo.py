"""Reads, each with a fallback to the seed files.

Standing rule: every external call gets a timeout and a fixture fallback. A
Supabase outage degrades the plan to seeded data instead of taking the demo down,
and `source()` reports which path was taken so /health and the logs can't lie
about it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional

from apps.api.config import SEED_DIR
from apps.api.db import client

DATA_DIR = SEED_DIR / "data"


@lru_cache
def _seed(name: str) -> list[dict[str, Any]]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    return json.loads(path.read_text())


def listings(*, category: Optional[str] = None) -> list[dict[str, Any]]:
    """All listings, or those in one category."""
    try:
        params = {"category": f"eq.{category}"} if category else None
        rows = client.select("listings", params=params)
        if rows:
            return rows
    except client.DBUnavailable:
        pass
    rows = _seed("listings.json")
    return [r for r in rows if category is None or r.get("category") == category]


def users_by_id() -> dict[str, dict[str, Any]]:
    try:
        rows = client.select("users")
        if rows:
            return {r["id"]: r for r in rows}
    except client.DBUnavailable:
        pass
    return {r["id"]: r for r in _seed("users.json")}


def prefs_for(user_id: str) -> dict[str, Any]:
    """users.prefs — taste, added to §3 on 2026-09-19. Empty is a valid answer."""
    user = users_by_id().get(user_id)
    return (user or {}).get("prefs") or {}


def hero_needs() -> list[dict[str, Any]]:
    """The decomposed needs behind the hero goal.

    §4 does not serialize need.category or need.attrs, so they live here rather
    than in hero_plan.json. This is also decompose.py's fallback in step 7.
    """
    return _seed("hero_needs.json")


def source() -> str:
    """Which path a read would take right now. For /health and logging."""
    if not client.configured():
        return "seed (no credentials)"
    try:
        client.select("listings", params={"limit": "1"}, timeout=2.0)
        return "supabase"
    except client.DBUnavailable:
        return "seed (supabase unreachable)"
