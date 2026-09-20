"""Photo-detected wardrobe items for the existing OWN resolver rung.

Inventory is per user, in process memory, and replaced by each upload.
Detection failures never substitute sample items or invent ownership.
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

#: Vision models use the providers' existing OpenAI-compatible endpoints.
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
  - pattern: if obvious (e.g. solid, striped, checked); omit if unsure

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
    VISION_ORDER. A keyless setup returns None.
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
    if any(raw.get(key) is not None and not isinstance(raw[key], str)
           for key in ("category", "color", "style", "formality", "material", "pattern")):
        return None
    category = str(raw.get("category") or "other").strip().lower()
    if category not in CATEGORIES:
        category = "other"
    color = raw.get("color")
    style = raw.get("style")
    color = color.strip().lower() if isinstance(color, str) else ""
    style = style.strip().lower() if isinstance(style, str) else ""
    attrs: dict[str, Any] = {}
    if color:
        attrs["color"] = color
    if style:
        attrs["style"] = style
    for key in ("formality", "material", "pattern"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            attrs[key] = value.strip().lower()
    # An item with neither a color nor a style is too vague to identify.
    if not color and not style:
        return None
    title = " ".join(w for w in (color, style) if w) or category
    return {"category": category, "attrs": attrs, "title": title.strip()}


def _parse_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("Vision response must contain an items array")
    items = payload["items"]
    out = [_normalize_item(raw) for raw in items]
    if any(item is None for item in out):
        raise ValueError("Vision response contains an invalid item")
    return [item for item in out if item is not None]


def analyze_wardrobe(
    image_bytes: bytes, *, content_type: Optional[str] = None
) -> tuple[list[dict[str, Any]], str]:
    """(items, source) where source is the provider name, "none", or "error".

    Never raises. A failure here must not take down the upload route.
    """
    if not image_bytes:
        log.info("empty wardrobe upload; no items detected")
        return [], "none"

    chosen = _pick_vision_provider()
    if chosen is None:
        log.info("no vision-capable LLM key; no items detected")
        return [], "none"

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
        log.warning("wardrobe vision via %s (%s) failed (%s); no items stored", name, model, type(exc).__name__)
        return [], "error"

    if not items:
        log.info("%s (%s) detected no items", name, model)
        return [], "none"

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
