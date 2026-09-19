"""B contract stubs: get_or_create_user_by_phone, run_agent(user_id, message)."""

from __future__ import annotations

import uuid
from typing import Any

_phone_to_user: dict[str, str] = {}


def get_or_create_user_by_phone(phone: str) -> str:
    key = (phone or "").strip()
    if key not in _phone_to_user:
        _phone_to_user[key] = str(uuid.uuid4())
    return _phone_to_user[key]


def run_agent(user_id: str, message: str) -> dict[str, Any]:
    """Return a small fake Plan shaped like POST /api/mission."""
    listing_id = "lst_demo_jacket"
    return {
        "mission_id": str(uuid.uuid4()),
        "goal_text": (message or "Find a cheaper way to get this.").strip()[:200],
        "user_id": user_id,
        "needs": [
            {
                "need_id": "need_jacket",
                "query": "jacket",
                "options": [
                    {
                        "listing_id": listing_id,
                        "rung": "borrow",
                        "title": "Black puffer jacket",
                        "price": 0,
                    },
                    {
                        "listing_id": "lst_demo_thrift",
                        "rung": "thrift",
                        "title": "Used puffer at campus thrift",
                        "price": 1800,
                    },
                ],
                "recommended_listing_id": listing_id,
            }
        ],
        "impact": {"saved_cents": 4500},
    }
