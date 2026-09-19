"""Supabase access over PostgREST.

No psycopg and no supabase-py: the REST interface needs only httpx, which is
already a dependency, and it works with the URL + anon/service key you get from
the dashboard without a direct Postgres connection string.

Every call has a timeout and every read has a fallback (the standing rule). A DB
that is down degrades to fixtures rather than taking the demo with it.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from apps.api.config import get_settings


class DBUnavailable(RuntimeError):
    """Supabase is unreachable, unconfigured, or returned an error."""


def configured() -> bool:
    s = get_settings()
    return bool(s.supabase_url and s.supabase_key)


def _headers(extra: Optional[dict] = None) -> dict:
    s = get_settings()
    h = {
        "apikey": s.supabase_key or "",
        "Authorization": f"Bearer {s.supabase_key or ''}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _base() -> str:
    s = get_settings()
    if not s.supabase_url:
        raise DBUnavailable("SUPABASE_URL is not set")
    return s.supabase_url.rstrip("/") + "/rest/v1"


def select(
    table: str,
    *,
    params: Optional[dict] = None,
    timeout: float = 5.0,
) -> list[dict[str, Any]]:
    if not configured():
        raise DBUnavailable("Supabase credentials are not configured")
    q = {"select": "*"}
    q.update(params or {})
    try:
        r = httpx.get(f"{_base()}/{table}", headers=_headers(), params=q, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as exc:
        raise DBUnavailable(f"select {table}: {exc}") from exc


def upsert(
    table: str,
    rows: list[dict[str, Any]],
    *,
    on_conflict: str = "id",
    timeout: float = 15.0,
) -> list[dict[str, Any]]:
    if not configured():
        raise DBUnavailable("Supabase credentials are not configured")
    if not rows:
        return []
    try:
        r = httpx.post(
            f"{_base()}/{table}",
            headers=_headers(
                {"Prefer": "resolution=merge-duplicates,return=representation"}
            ),
            params={"on_conflict": on_conflict},
            json=rows,
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as exc:
        detail = ""
        if isinstance(exc, httpx.HTTPStatusError):
            detail = f" — {exc.response.text[:400]}"
        raise DBUnavailable(f"upsert {table}: {exc}{detail}") from exc
