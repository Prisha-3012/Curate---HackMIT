"""Live retailer search and normalization for market listings.

The resolver only receives normalized rows. Search results without a direct
retailer URL or an observable price are discarded rather than presented as
buyable recommendations.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

from apps.api.config import demo_mode_enabled, get_settings

log = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
PRICE_RE = re.compile(r"(?:\$|USD\s*)(\d{1,5}(?:\.\d{2})?)", re.IGNORECASE)
USED_RE = re.compile(r"\b(used|secondhand|second-hand|pre-owned|preowned)\b", re.IGNORECASE)
EDITORIAL_PATH_RE = re.compile(
    r"/(?:blog|article|articles|news|magazine|journal)(?:/|$)", re.IGNORECASE
)
INFORMATIONAL_TITLE_RE = re.compile(
    r"\b(?:how\s+to|what\s+to\s+wear|buying\s+guide|style\s+guide)\b",
    re.IGNORECASE,
)
LISTICLE_TITLE_RE = re.compile(
    r"\b(?:these|the)\s+\d+\b|\b\d+\s+(?:ways|tips|ideas|things|steps)\b",
    re.IGNORECASE,
)
#: A query param that pins ONE specific product or variant (…?sku=9500-0030).
PRODUCT_PARAM_RE = re.compile(
    r"[?&](?:sku|variant|variant_id|pid|productid|product_id|itemid|item_id|prod|dwvar|id)=",
    re.IGNORECASE,
)
#: A path token that marks a single product / single listing page.
PRODUCT_PATH_RE = re.compile(
    r"/(?:dp|gp/product|itm|products?|p|pd|listings?|items?|prod)/[\w%-]",
    re.IGNORECASE,
)
#: A pure search URL — never one product.
SEARCH_URL_RE = re.compile(
    r"/(?:search|sch|browse|s-cat)(?:/|$)|[?&](?:_nkw|q|query|keyword|search|k)=",
    re.IGNORECASE,
)
#: Title/snippet wording of a collection or results page ("Shop All Lanterns
#: (59 Products)"), not one item.
COLLECTION_TEXT_RE = re.compile(
    r"\bshop\s+all\b|\bshop\s+by\b|\ball\s+products\b|\bsearch\s+results\b"
    r"|\(\s*\d+\s+products?\s*\)|\b\d+\s+products?\b|\b\d+\s+results?\b",
    re.IGNORECASE,
)


def is_single_product_url(url: Any, title: str = "", content: str = "") -> bool:
    """True only when this clearly points at ONE product, not a search, category
    or collection page.

    Uses positive signals — a product/variant query param, or a product path
    token — because listing URLs come in too many shapes to blocklist (a
    /c/lighting/lanterns/ category page and a /c/lighting/lanterns/denison/?sku=…
    product page share a prefix). Prefers a false negative (no link) over
    linking a page the user has to search again.
    """
    if not isinstance(url, str) or not url:
        return False
    if SEARCH_URL_RE.search(url):
        return False
    if COLLECTION_TEXT_RE.search(title) or COLLECTION_TEXT_RE.search(content):
        return False
    return bool(PRODUCT_PARAM_RE.search(url) or PRODUCT_PATH_RE.search(url))


def _valid_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _price_cents(result: dict[str, Any]) -> int | None:
    for key in ("price_cents", "price"):
        value = result.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            return round(float(value) * 100) if key == "price" else int(value)
    text = " ".join(str(result.get(key) or "") for key in ("title", "content", "raw_content"))
    match = PRICE_RE.search(text)
    return round(float(match.group(1)) * 100) if match else None


def _looks_editorial(result: dict[str, Any]) -> bool:
    """Reject clear article pages, while allowing varied product URL shapes."""
    title = str(result.get("title") or "")
    url = result.get("url") or result.get("product_url")
    path = urlparse(url).path if isinstance(url, str) else ""
    return bool(
        EDITORIAL_PATH_RE.search(path)
        or INFORMATIONAL_TITLE_RE.search(title)
        or LISTICLE_TITLE_RE.search(title)
    )


def normalize_result(
    result: Any,
    *,
    category: str,
    provider: str = "tavily",
    need_attrs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Convert one provider result into a resolver listing, or reject it."""
    if not isinstance(result, dict):
        return None
    title = str(result.get("title") or "").strip()
    url = result.get("url") or result.get("product_url")
    price_cents = _price_cents(result)
    snippet = " ".join(str(result.get(k) or "") for k in ("title", "content", "raw_content"))
    if (
        not title
        or not _valid_url(url)
        or price_cents is None
        or _looks_editorial(result)
        or not is_single_product_url(url, title, snippet)  # must be ONE product page
    ):
        return None

    external_id = str(result.get("id") or url).strip()
    listing_id = "live-" + hashlib.sha256(f"{provider}:{external_id}".encode()).hexdigest()[:24]
    text = " ".join(str(result.get(key) or "") for key in ("title", "content", "raw_content"))
    rung = "USED" if USED_RE.search(text) else "NEW"
    result_attrs = result.get("attrs")
    attrs = result_attrs if isinstance(result_attrs, dict) and result_attrs else dict(need_attrs or {})
    return {
        "id": listing_id,
        "title": title,
        "category": category,
        "rung": rung,
        "owner_id": None,
        "brand": result.get("brand") or "retailer",
        "size_label": result.get("size_label"),
        "condition": "used" if rung == "USED" else "new",
        "price_cents": price_cents,
        "retail_cents": int(result.get("retail_cents") or price_cents),
        "image_url": result.get("image_url") if _valid_url(result.get("image_url")) else None,
        "product_url": url,
        "provider": provider,
        "external_id": external_id,
        "attrs": attrs,
    }


def _query(goal_text: str, need: dict[str, Any]) -> str:
    attrs = " ".join(f"{key} {value}" for key, value in (need.get("attrs") or {}).items())
    return (
        f"{goal_text}; {need.get('label', '')}; {attrs}; "
        "buy online retailer product direct product page buy now current price"
    )


def _request(query: str) -> list[dict[str, Any]]:
    settings = get_settings()
    if demo_mode_enabled() or not settings.tavily_api_key:
        return []
    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": settings.tavily_max_results,
        "include_images": True,
    }
    for attempt in range(2):
        try:
            response = httpx.post(TAVILY_URL, json=payload, timeout=settings.tavily_timeout_s)
            if response.status_code >= 500 and attempt == 0:
                continue
            response.raise_for_status()
            data = response.json()
            return data.get("results", []) if isinstance(data, dict) else []
        except (httpx.HTTPError, ValueError):
            if attempt == 1:
                log.exception("live product search failed")
                return []
    return []


def fetch_products(goal_text: str, needs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch and normalize live candidates for the current goal."""
    if demo_mode_enabled():
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for need in needs:
        category = str(need.get("category") or "other").strip().lower()
        for result in _request(_query(goal_text, need)):
            row = normalize_result(
                result,
                category=category,
                need_attrs=need.get("attrs") if isinstance(need.get("attrs"), dict) else None,
            )
            if row is None or row["product_url"] in seen:
                continue
            seen.add(row["product_url"])
            rows.append(row)
    return rows