"""Wardrobe understanding: a photo of the closet -> the items the person owns.

This feeds the resolver's OWN rung. The whole app already prefers what you own
(§1); this just makes "what you own" real instead of seeded. Two outputs:

  - OWN listings, injected into the ladder so a need the closet already covers
    resolves to "you already own this" at $0 instead of a purchase.
  - owned signatures, so the resolver won't recommend BUYING something the
    person effectively already has (a sixth white tee).

Same standing rule as the rest of the backend: one external call, a timeout, and
a fixture fallback. No vision key, a timeout, or malformed output degrades to a
sample wardrobe, honestly labelled source="fixture", so the flow always works on
the demo floor. Real detection turns on the moment a GEMINI/OPENAI key is set.

Storage is deliberately in-memory and per-process: a mission is stateless and the
DB is optional, so the closet lives beside the running app for the length of the
session. Persisting it is a later step, not a demo blocker.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from typing import Any, Optional

import httpx

from apps.api.config import get_settings
from apps.api.services import decompose

log = logging.getLogger(__name__)

#: Vision-capable models per provider. All read images through the same
#: OpenAI-compatible chat endpoint decompose.py already targets, via an
#: image_url content part.
#:
#: Groq's DEFAULT model (gpt-oss) is text-only, so vision uses a Llama 4
#: multimodal id here instead. Groq retires ids regularly (the codebase warns of
#: this), so if this one 404s the upload degrades to the fixture and the UI says
#: so — override it by setting LLM_MODEL, or add a Gemini key.
VISION_MODELS = {
    "gemini": "gemini-3.6-flash",                        # multimodal
    "openai": "gpt-4o-mini",                             # vision
    "groq": "meta-llama/llama-4-scout-17b-16e-instruct", # multimodal
    "xai": "grok-2-vision-1212",
}
#: Gemini/OpenAI first (known-good vision), then Groq so an existing Groq key is
#: used before asking for a new one, then xAI.
VISION_ORDER = ("gemini", "openai", "groq", "xai")

#: Mirrors schemas.Category. Anything the model returns outside this set becomes
#: "other", which is not fit-checkable and simply never blocks a recommendation.
CATEGORIES = ("top", "bottom", "outerwear", "footwear", "other")

#: Rough new-price baseline per category, in cents, for OWN items so the savings
#: line ("buying the equivalent new would cost $X") has something honest to show.
#: These are owned, so price_cents is always 0; only the retail baseline matters.
RETAIL_DEFAULTS = {
    "top": 4000,
    "bottom": 5500,
    "outerwear": 9000,
    "footwear": 8000,
    "other": 3000,
}

SYSTEM_PROMPT = """You identify the distinct clothing items visible in a photo of \
someone's wardrobe, closet, or a pile of their clothes.

For each item you can clearly see, report:
  - category: EXACTLY one of top, bottom, outerwear, footwear, other
  - color: the dominant color, one or two words (e.g. "white", "navy", "olive")
  - style: the specific type (e.g. "t-shirt", "oxford shirt", "chinos", "jeans",
    "hoodie", "sneakers"). Keep it short.
  - formality: one of casual, business-casual, formal, athletic
  - material: if obvious (e.g. cotton, denim, wool, leather); omit if unsure

Rules:
  - Report only items you can actually see. Do not invent a full wardrobe.
  - Fold near-identical duplicates into one entry, but keep genuinely different
    items separate (a white tee and a black tee are two items).
  - Ignore hangers, shelves, the person, and the background.
"""

USER_PROMPT = """List the clothing items in this wardrobe photo.

Return ONLY a JSON object of exactly this shape, no commentary:

{"items": [{"category": "top", "color": "white", "style": "t-shirt",
  "formality": "casual", "material": "cotton"}]}

Every category must be one of: top, bottom, outerwear, footwear, other.
"""


# --------------------------------------------------------------------------
# in-memory per-user store
# --------------------------------------------------------------------------

_WARDROBE: dict[str, dict[str, Any]] = {}


def set_wardrobe(user_id: str, items: list[dict[str, Any]], source: str) -> None:
    _WARDROBE[user_id] = {"items": items, "source": source}


def get_wardrobe(user_id: str) -> list[dict[str, Any]]:
    """The detected items for a user, or [] when none has been uploaded."""
    return _WARDROBE.get(user_id, {}).get("items", [])


def get_wardrobe_meta(user_id: str) -> Optional[dict[str, Any]]:
    """{"items": [...], "source": ...} or None. For the GET route and debugging."""
    return _WARDROBE.get(user_id)


def clear_wardrobe(user_id: str) -> None:
    _WARDROBE.pop(user_id, None)


# --------------------------------------------------------------------------
# provider selection
# --------------------------------------------------------------------------


def _pick_vision_provider() -> Optional[tuple[str, str, str, str]]:
    """(name, url, model, key) for the first vision-capable key set, or None.

    Honors LLM_PROVIDER when it names a vision-capable provider; otherwise walks
    VISION_ORDER. A groq-only or keyless setup returns None -> fixture fallback.
    """
    s = get_settings()
    keys = {
        "gemini": (s.gemini_api_key or "").strip(),
        "openai": (s.openai_api_key or "").strip(),
        "groq": (s.groq_api_key or "").strip(),
        "xai": (s.xai_api_key or "").strip(),
    }
    wanted = (s.llm_provider or "auto").strip().lower()
    order: tuple[str, ...] = (wanted,) if wanted in VISION_MODELS else VISION_ORDER
    for name in order:
        if keys.get(name):
            return name, decompose.PROVIDERS[name]["url"], VISION_MODELS[name], keys[name]
    return None


# --------------------------------------------------------------------------
# detection
# --------------------------------------------------------------------------


def _normalize_item(raw: Any) -> Optional[dict[str, Any]]:
    """One model item -> {category, attrs, title}, or None if unusable.

    Every field is untrusted (json_object mode enforces valid JSON, not shape).
    """
    if not isinstance(raw, dict):
        return None
    category = str(raw.get("category") or "other").strip().lower()
    if category not in CATEGORIES:
        category = "other"
    color = str(raw.get("color") or "").strip().lower()
    style = str(raw.get("style") or "").strip().lower()
    attrs: dict[str, Any] = {}
    if color:
        attrs["color"] = color
    if style:
        attrs["style"] = style
    for key in ("formality", "material", "pattern"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            attrs[key] = value.strip().lower()
    # An item with neither a color nor a style is too vague to own or dedup on.
    if not color and not style:
        return None
    title = " ".join(w for w in (color, style) if w) or category
    return {"category": category, "attrs": attrs, "title": title.strip()}


def _parse_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("items")
        if not isinstance(items, list):
            items = next((v for v in payload.values() if isinstance(v, list)), [])
    else:
        items = []
    out: list[dict[str, Any]] = []
    for raw in items:
        item = _normalize_item(raw)
        if item:
            out.append(item)
    return out


def analyze_wardrobe(
    image_bytes: bytes, *, content_type: Optional[str] = None
) -> tuple[list[dict[str, Any]], str]:
    """(items, source) where source is the provider name or "fixture".

    Never raises. A failure here must not take down the upload route.
    """
    if not image_bytes:
        log.warning("empty wardrobe upload; using fixture wardrobe")
        return _fixture_items(), "fixture"

    chosen = _pick_vision_provider()
    if chosen is None:
        log.info("no vision-capable LLM key; using fixture wardrobe")
        return _fixture_items(), "fixture"

    name, url, model, key = chosen
    mime = content_type or "image/jpeg"
    data_uri = f"data:{mime};base64," + base64.b64encode(image_bytes).decode()
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }
    headers = {"Authorization": f"Bearer {key}"}

    try:
        r = httpx.post(url, headers=headers, json=body, timeout=get_settings().llm_timeout_s)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        items = _parse_items(json.loads(content))
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
        log.warning("wardrobe vision via %s (%s) failed (%s); using fixture", name, model, exc)
        return _fixture_items(), "fixture"

    if not items:
        log.warning("%s (%s) detected no items; using fixture wardrobe", name, model)
        return _fixture_items(), "fixture"

    log.info("wardrobe: detected %d item(s) via %s", len(items), name)
    return items, name


# --------------------------------------------------------------------------
# conversion for the resolver
# --------------------------------------------------------------------------


def to_own_listings(items: list[dict[str, Any]], user_id: str) -> list[dict[str, Any]]:
    """Detected items -> OWN listings the resolver already consumes.

    Same dict shape as an OWN row in seed/data/listings.json, so the resolver
    treats a photographed shirt exactly like a seeded one: rung OWN, owned by
    this viewer, free.
    """
    out: list[dict[str, Any]] = []
    for item in items:
        category = item.get("category") or "other"
        attrs = item.get("attrs") or {}
        title = item.get("title") or category
        out.append(
            {
                "id": str(
                    uuid.uuid5(uuid.NAMESPACE_URL, f"wardrobe/{user_id}/{category}/{title}")
                ),
                "title": title,
                "category": category,
                "rung": "OWN",
                "owner_id": user_id,
                "brand": attrs.get("brand") or "your closet",
                "size_label": None,
                "condition": "owned",
                "price_cents": 0,
                "retail_cents": RETAIL_DEFAULTS.get(category, 3000),
                "image_url": None,
                "attrs": attrs,
            }
        )
    return out


def _fixture_items() -> list[dict[str, Any]]:
    """A believable sample closet for when no vision key is set.

    Chosen to overlap the seeded business-casual demo so the dedup is visible:
    the user already owns white and light-blue tops, so the plan should stop
    recommending another plain oxford and reach for what is missing.
    """
    return [
        {"category": "top", "attrs": {"color": "white", "style": "t-shirt", "formality": "casual", "material": "cotton"}, "title": "white t-shirt"},
        {"category": "top", "attrs": {"color": "white", "style": "oxford shirt", "formality": "business-casual", "material": "cotton"}, "title": "white oxford shirt"},
        {"category": "top", "attrs": {"color": "light blue", "style": "oxford shirt", "formality": "business-casual", "material": "cotton"}, "title": "light blue oxford shirt"},
        {"category": "bottom", "attrs": {"color": "khaki", "style": "chinos", "formality": "business-casual", "material": "cotton"}, "title": "khaki chinos"},
        {"category": "bottom", "attrs": {"color": "blue", "style": "jeans", "formality": "casual", "material": "denim"}, "title": "blue jeans"},
        {"category": "footwear", "attrs": {"color": "white", "style": "sneakers", "formality": "casual"}, "title": "white sneakers"},
    ]
