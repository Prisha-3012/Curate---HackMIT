"""goal_text -> Need[]. ARCHITECTURE.md §2.

The model's job is NEED DECOMPOSITION, not product selection. A need names a
capability or problem to satisfy — "somewhere for guests to sit", "keep food
cold" — not a product. Choosing what satisfies a need is the resolver's job, and
keeping that boundary is what makes the ladder meaningful: if the LLM named
products, it would be choosing rungs implicitly and OWN/BORROW would never win.

Domain-agnostic on purpose. Nothing here assumes clothing.

§6: this is the one live call. 4s timeout, falls back to the fixture on timeout,
transport error, or malformed output.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

import httpx

from apps.api.config import get_settings
from apps.api.db import repo

log = logging.getLogger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

MAX_NEEDS = 6

SYSTEM_PROMPT = """You decompose a person's stated goal into the distinct NEEDS \
that must be satisfied for the goal to be met.

A need is a CAPABILITY or PROBLEM, never a product.
  good: "somewhere for 12 people to sit", "keep drinks cold", "a layer for cold offices"
  bad:  "12 folding chairs", "a cooler", "a navy blazer"

Something else decides what satisfies each need, preferring things the person
already owns or can borrow over buying. If you name products you remove that
choice, so describe the requirement and stop there.

Rules:
- Between 2 and {max_needs} needs. Fewer, larger needs beat many trivial ones.
- priority 1 = the goal fails without it. priority 2 = genuinely optional.
- `category` groups interchangeable solutions. PREFER a value from the known
  list you are given; invent a short lowercase token only if none fits.
- `attrs` are the properties a solution must have, as flat key/value pairs.
  Use values from the known attribute vocabulary where they apply.
- `rationale` is one sentence a person would find useful, explaining why this
  need exists. It is shown in the UI.
- If the goal implies a quantity ("dinner for 12"), put it in the label and in
  attrs, e.g. {{"serves": 12}}.
"""

NEEDS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["needs"],
    "properties": {
        "needs": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_NEEDS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "rationale", "category", "attrs", "priority"],
                "properties": {
                    "label": {"type": "string"},
                    "rationale": {"type": "string"},
                    "category": {"type": "string"},
                    "priority": {"type": "integer", "enum": [1, 2]},
                    "attrs": {
                        "type": "array",
                        "description": "Flat key/value pairs the solution must satisfy.",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["key", "value"],
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
    },
}


def catalogue_vocabulary() -> tuple[list[str], dict[str, list[str]]]:
    """What the resolver can actually match against.

    Grounding the model in the real catalogue is the difference between a need
    that resolves and one that is unmet on a token nobody uses. It is a hint,
    not a constraint — an honest unmet need beats a forced bad match.
    """
    listings = repo.listings()
    categories = sorted({str(item.get("category")) for item in listings if item.get("category")})

    values: dict[str, set[str]] = {}
    for item in listings:
        for key, value in (item.get("attrs") or {}).items():
            if isinstance(value, (str, int, float, bool)):
                values.setdefault(key, set()).add(str(value))
    vocabulary = {k: sorted(v)[:12] for k, v in sorted(values.items())}
    return categories, vocabulary


def _attrs_to_dict(raw: Any) -> dict[str, Any]:
    """The schema uses a key/value array because OpenAI strict mode forbids
    free-form objects. Convert back, coercing the obvious scalar types."""
    out: dict[str, Any] = {}
    if not isinstance(raw, list):
        return out
    for pair in raw:
        if not isinstance(pair, dict):
            continue
        key, value = pair.get("key"), pair.get("value")
        if not isinstance(key, str) or value is None:
            continue
        text = str(value)
        low = text.strip().lower()
        if low in ("true", "false"):
            out[key] = low == "true"
        elif low.isdigit():
            out[key] = int(low)
        else:
            out[key] = text
    return out


def _to_need_rows(payload: dict[str, Any], mission_id: str) -> list[dict[str, Any]]:
    """Model output -> the need-row shape the resolver already consumes.

    Deliberately the same dict shape as seed/data/hero_needs.json, so the live
    path and the fixture path feed the resolver identically.
    """
    rows: list[dict[str, Any]] = []
    for item in payload.get("needs", [])[:MAX_NEEDS]:
        label = (item.get("label") or "").strip()
        category = (item.get("category") or "other").strip().lower()
        if not label:
            continue
        priority = item.get("priority", 1)
        rows.append(
            {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{mission_id}/{label}")),
                "label": label,
                "rationale": (item.get("rationale") or "").strip(),
                "category": category or "other",
                "attrs": _attrs_to_dict(item.get("attrs")),
                "priority": priority if priority in (1, 2) else 1,
            }
        )
    return rows


def decompose(goal_text: str, *, mission_id: str) -> tuple[list[dict[str, Any]], str]:
    """Return (need_rows, source) where source is "openai" or "fixture".

    Never raises. A failure here must not take down /api/mission.
    """
    s = get_settings()
    key = (s.openai_api_key or "").strip()
    if not key:
        log.info("no OPENAI_API_KEY; using fixture needs")
        return repo.hero_needs(), "fixture"

    categories, vocabulary = catalogue_vocabulary()
    user_prompt = (
        f"Goal: {goal_text}\n\n"
        f"Known categories: {', '.join(categories)}\n"
        f"Known attributes: {json.dumps(vocabulary)}\n\n"
        "Decompose the goal into needs."
    )

    try:
        r = httpx.post(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT.format(max_needs=MAX_NEEDS)},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "need_decomposition",
                        "strict": True,
                        "schema": NEEDS_SCHEMA,
                    },
                },
                "temperature": 0.2,
            },
            timeout=s.openai_timeout_s,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        rows = _to_need_rows(json.loads(content), mission_id)
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
        # Timeout, transport failure, malformed JSON, or a shape we didn't expect.
        log.warning("decompose failed (%s); falling back to fixture needs", exc)
        return repo.hero_needs(), "fixture"

    if not rows:
        log.warning("decompose returned no usable needs; falling back to fixture")
        return repo.hero_needs(), "fixture"

    return rows, "openai"
