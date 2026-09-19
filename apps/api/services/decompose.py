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
from typing import Any, NamedTuple, Optional

import httpx

from apps.api.config import get_settings
from apps.api.db import repo

log = logging.getLogger(__name__)

#: All three speak the OpenAI chat-completions protocol, so one client covers
#: them. They differ in how they can be made to return JSON:
#:
#:   "schema" — response_format json_schema with strict:true. OpenAI's own
#:              feature; the API enforces the shape and cannot return prose.
#:   "object" — response_format json_object. Valid JSON is guaranteed, the
#:              SHAPE is not, so the schema is spelled out in the prompt and
#:              the parser below treats every field as untrusted.
#:
#: Compat layers routinely ACCEPT strict:true and ignore the enforcement, which
#: is worse than not supporting it: output silently degrades to prose and the
#: fixture fallback makes it look like the decomposer is working. So anything
#: that is not OpenAI itself is "object" until proven otherwise.
PROVIDERS = {
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "structured": "schema",
    },
    "xai": {
        "url": "https://api.x.ai/v1/chat/completions",
        "model": "grok-3-mini",
        "structured": "schema",
    },
    "gemini": {
        # Google's OpenAI-compatible endpoint, not the native generateContent API.
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        #: Model ids move — gemini-2.0-flash was retired and the API itself
        #: named this as the replacement. Override with LLM_MODEL when it ages
        #: out too; a wrong id surfaces as a 404 in preflight, and at runtime
        #: falls back to fixture needs.
        "model": "gemini-3.6-flash",
        "structured": "object",
    },
}

#: auto order. Gemini first because it is the one with a free tier, so it is
#: the key most likely to actually have credit behind it.
AUTO_ORDER = ("gemini", "xai", "openai")

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


def _coerce(value: Any) -> Any:
    """Scalar as the resolver needs it. It matches on ==, so "true" must not
    stay a string where True was meant."""
    if isinstance(value, bool) or isinstance(value, int):
        return value
    text = str(value)
    low = text.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    if low.isdigit():
        return int(low)
    return text


def _attrs_to_dict(raw: Any) -> dict[str, Any]:
    """Model attrs -> a flat dict, whichever shape arrived.

    OpenAI strict mode forbids free-form objects, so the schema asks for an
    array of {key, value} pairs. A provider in "object" mode is under no such
    constraint and will usually return a plain {"waterproof": true} object, so
    both are accepted — the alternative is discarding every attribute from a
    non-strict provider and silently resolving needs on category alone.
    """
    out: dict[str, Any] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(key, str) and value is not None:
                out[key] = _coerce(value)
        return out
    if not isinstance(raw, list):
        return out
    for pair in raw:
        if not isinstance(pair, dict):
            continue
        key, value = pair.get("key"), pair.get("value")
        if not isinstance(key, str) or value is None:
            continue
        out[key] = _coerce(value)
    return out


def _to_need_rows(payload: Any, mission_id: str) -> list[dict[str, Any]]:
    """Model output -> the need-row shape the resolver already consumes.

    Deliberately the same dict shape as seed/data/hero_needs.json, so the live
    path and the fixture path feed the resolver identically.

    Every field is treated as untrusted. Under "object" mode nothing enforces
    the schema, so a bare list instead of {"needs": [...]} is common enough to
    accept rather than throw away a decomposition over its envelope.
    """
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("needs")
        if not isinstance(items, list):
            # Some models wrap in a single unexpected key; take the first list.
            items = next(
                (v for v in payload.values() if isinstance(v, list)), []
            )
    else:
        items = []

    rows: list[dict[str, Any]] = []
    for item in items[:MAX_NEEDS]:
        if not isinstance(item, dict):
            continue
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


class Chosen(NamedTuple):
    name: str
    url: str
    model: str
    key: str
    #: "schema" or "object" — see PROVIDERS.
    structured: str


def pick_provider() -> Optional[Chosen]:
    """The provider to use, or None when no key is configured.

    'auto' walks AUTO_ORDER and takes the first key that is set. An explicitly
    named provider is honoured even if a different key is the one present, so a
    misconfigured LLM_PROVIDER fails visibly rather than silently billing the
    wrong account.
    """
    s = get_settings()
    keys = {
        "openai": (s.openai_api_key or "").strip(),
        "xai": (s.xai_api_key or "").strip(),
        "gemini": (s.gemini_api_key or "").strip(),
    }
    wanted = (s.llm_provider or "auto").strip().lower()

    if wanted in PROVIDERS:
        order: tuple[str, ...] = (wanted,)
    else:
        if wanted not in ("", "auto"):
            log.warning("unknown LLM_PROVIDER %r; falling back to auto", wanted)
        order = AUTO_ORDER

    for name in order:
        if keys.get(name):
            cfg = PROVIDERS[name]
            return Chosen(
                name=name,
                url=cfg["url"],
                model=s.llm_model or cfg["model"],
                key=keys[name],
                structured=cfg["structured"],
            )
    return None


def _response_format(structured: str) -> dict[str, Any]:
    if structured == "schema":
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "need_decomposition",
                "strict": True,
                "schema": NEEDS_SCHEMA,
            },
        }
    # json_object guarantees parseable JSON but not the shape, so the shape has
    # to be asked for in words. _to_need_rows validates whatever comes back.
    return {"type": "json_object"}


#: Appended to the prompt when the API cannot enforce the schema for us.
SHAPE_INSTRUCTION = """
Return ONLY a JSON object of exactly this shape, with no commentary:

{{"needs": [{{"label": "...", "rationale": "...", "category": "...",
  "priority": 1, "attrs": {{"some_key": "some_value"}}}}]}}

Between 2 and {max_needs} entries. `priority` is the integer 1 or 2. `attrs` is
a flat object of plain string, number or boolean values — never nested.
"""


def decompose(goal_text: str, *, mission_id: str) -> tuple[list[dict[str, Any]], str]:
    """Return (need_rows, source) where source is the provider name or "fixture".

    Never raises. A failure here must not take down /api/mission.
    """
    s = get_settings()
    chosen = pick_provider()
    if chosen is None:
        log.info("no LLM api key configured; using fixture needs")
        return repo.hero_needs(), "fixture"

    categories, vocabulary = catalogue_vocabulary()
    user_prompt = (
        f"Goal: {goal_text}\n\n"
        f"Known categories: {', '.join(categories)}\n"
        f"Known attributes: {json.dumps(vocabulary)}\n\n"
        "Decompose the goal into needs."
    )
    if chosen.structured != "schema":
        user_prompt += "\n" + SHAPE_INSTRUCTION.format(max_needs=MAX_NEEDS)

    body = {
        "model": chosen.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(max_needs=MAX_NEEDS)},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": _response_format(chosen.structured),
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {chosen.key}"}

    try:
        # Gemini load-sheds with a 503 often enough to matter: roughly one call
        # in three during testing. Without a retry that surfaces as a goal
        # randomly coming back in the seeded wardrobe needs, which reads as "the
        # decomposer is broken" rather than "the provider was busy". One retry
        # only, and only for 5xx — a 4xx is a real problem (bad key, dead model)
        # and repeating it just doubles the wait before the fixture fallback.
        for attempt in (1, 2):
            r = httpx.post(chosen.url, headers=headers, json=body, timeout=s.llm_timeout_s)
            if r.status_code < 500 or attempt == 2:
                break
            log.info(
                "%s returned %s; retrying once", chosen.name, r.status_code
            )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        rows = _to_need_rows(json.loads(content), mission_id)
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
        # Timeout, transport failure, malformed JSON, or a shape we didn't expect.
        log.warning(
            "decompose via %s (%s) failed (%s); falling back to fixture needs",
            chosen.name, chosen.model, exc,
        )
        return repo.hero_needs(), "fixture"

    if not rows:
        log.warning(
            "%s (%s) returned no usable needs; falling back to fixture",
            chosen.name, chosen.model,
        )
        return repo.hero_needs(), "fixture"

    return rows, chosen.name
