"""Secondhand marketplace links for USED recommendations.

NEW items get a link because they come from the live retail web search
(products.py, via Tavily), which returns a product_url. USED items come from the
seed catalogue, which has none, so they rendered without a "where to buy" link.
This attaches links to every USED option:

  - `marketplaces`: ready-to-open search links to eBay, Depop, Poshmark, Facebook
    Marketplace and Mercari for the item. Constructed, so they need no API key
    and always work — the user lands on live secondhand results for that item.
  - `product_url`: a specific secondhand listing found by the SAME web-search
    method the app already uses (Tavily), scoped to those marketplaces, when a
    TAVILY_API_KEY is set. Falls back to the eBay search link otherwise.

Standing rule, same as the rest of the backend: the network call has a timeout
and degrades to the constructed links. It never raises, so a USED option always
comes out with somewhere to buy it.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx

from apps.api.config import demo_mode_enabled, get_settings
from apps.api.models.schemas import MarketplaceLink, Option, Rung
from apps.api.services import products

log = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"

#: The web search is scoped to these when looking for a specific listing.
SECONDHAND_DOMAINS = [
    "ebay.com",
    "depop.com",
    "poshmark.com",
    "facebook.com",
    "mercari.com",
    "thredup.com",
]

#: name -> search-URL template. {q} is filled with a url-encoded query.
#: eBay's LH_ItemCondition=3000 pins the results to used items.
_MARKETPLACES: tuple[tuple[str, str], ...] = (
    ("eBay", "https://www.ebay.com/sch/i.html?_nkw={q}&LH_ItemCondition=3000"),
    ("Depop", "https://www.depop.com/search/?q={q}"),
    ("Poshmark", "https://poshmark.com/search?query={q}"),
    ("Facebook Marketplace", "https://www.facebook.com/marketplace/search/?query={q}"),
    ("Mercari", "https://www.mercari.com/search/?keyword={q}"),
)


def marketplace_links(query: str) -> list[MarketplaceLink]:
    """Constructed secondhand search links for the item. Needs no API key."""
    q = quote_plus(query.strip())
    return [MarketplaceLink(name=name, url=tpl.format(q=q)) for name, tpl in _MARKETPLACES]


def _search_query(option: Option, need: dict[str, Any]) -> str:
    """What to search for. The option title when it is specific, else a phrase
    built from the need (color + style + label), so a generic seed title like
    "top" doesn't send the user to a useless search."""
    title = (option.title or "").strip()
    category = str(need.get("category") or "").strip().lower()
    if title and title.lower() != category:
        return title
    attrs = need.get("attrs") or {}
    parts = [str(attrs.get("color") or ""), str(attrs.get("style") or ""), str(need.get("label") or "")]
    phrase = " ".join(p for p in parts if p).strip()
    return phrase or title or category or "clothing"


def find_listing_url(query: str) -> Optional[str]:
    """A specific secondhand listing URL via Tavily, or None.

    None whenever there is no key, the demo is on, or the call fails — the caller
    then falls back to the constructed marketplace links.
    """
    settings = get_settings()
    if demo_mode_enabled() or not settings.tavily_api_key:
        return None
    payload = {
        "api_key": settings.tavily_api_key,
        "query": f"{query} used secondhand for sale",
        "search_depth": "basic",
        "max_results": 5,
        "include_domains": SECONDHAND_DOMAINS,
    }
    try:
        response = httpx.post(TAVILY_URL, json=payload, timeout=settings.tavily_timeout_s)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", []) if isinstance(data, dict) else []
    except (httpx.HTTPError, ValueError):
        log.warning("secondhand search failed for %r; using marketplace links", query)
        return None
    # Keep only URLs that point at ONE item (eBay /itm/, Depop /products/, …),
    # never a search or category page — that is the whole point of this change.
    for result in results:
        if not isinstance(result, dict):
            continue
        url = result.get("url")
        title = str(result.get("title") or "")
        content = str(result.get("content") or "")
        if products.is_single_product_url(url, title, content):
            return url
    return None


def enrich_used_options(options: list[Option], need: dict[str, Any]) -> list[Option]:
    """Point every USED option at a specific secondhand listing where possible.

    product_url is set ONLY to a real single-product page (a live listing already
    on the option, or one found by the scoped web search). It is left None when
    no single item is found, rather than a search page — the UI then shows the
    `marketplaces` browse links instead. OWN/BORROW/NEW pass through untouched.
    """
    out: list[Option] = []
    for option in options:
        if option.rung != Rung.USED:
            out.append(option)
            continue
        query = _search_query(option, need)
        product_url = option.product_url or find_listing_url(query)
        out.append(
            option.model_copy(
                update={"marketplaces": marketplace_links(query), "product_url": product_url}
            )
        )
    return out
