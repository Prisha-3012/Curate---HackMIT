"""Are the credentials actually usable? Run before rehearsing.

    uv run python -m apps.api.preflight

/health reports whether a key is PRESENT, which is not the same question. Both
keys in this repo were present and valid and had zero credits behind them, and
the only symptom was every goal quietly decomposing into the seeded wardrobe
needs. This makes one minimal call per configured provider and prints what came
back, so that failure mode takes ten seconds to find instead of a demo.

Exit code is 1 if no LLM provider is usable, so CI or a pre-demo script can
gate on it.
"""

from __future__ import annotations

import sys

import httpx

from apps.api.config import get_settings
from apps.api.db import client, repo
from apps.api.services.decompose import PROVIDERS

OK, WARN, BAD = "ok  ", "warn", "FAIL"


def _probe_llm(name: str, key: str) -> tuple[str, str]:
    """(status, detail) for one provider, via the cheapest call it accepts."""
    cfg = PROVIDERS[name]
    model = get_settings().llm_model or cfg["model"]
    try:
        r = httpx.post(
            cfg["url"],
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "say ok"}],
                "max_tokens": 5,
            },
            timeout=20.0,
        )
    except httpx.HTTPError as exc:
        return BAD, f"{type(exc).__name__}: {exc}"

    if r.status_code == 200:
        return OK, f"{model} responded"

    try:
        payload = r.json()
        # Gemini returns errors as a LIST, not an object, so .get() is not safe.
        if isinstance(payload, dict):
            payload = payload.get("error", payload)
        detail = str(payload)
    except ValueError:
        detail = r.text
    hint = ""
    if r.status_code in (401, 403):
        hint = "  <- key rejected, or the account has no credit"
    elif r.status_code == 404:
        hint = f"  <- is {model!r} available to this key? set LLM_MODEL"
    elif r.status_code == 429:
        hint = "  <- out of quota or rate limited"
    return BAD, f"HTTP {r.status_code}: {detail[:160]}{hint}"


def main() -> int:
    s = get_settings()
    keys = {
        "gemini": (s.gemini_api_key or "").strip(),
        "openai": (s.openai_api_key or "").strip(),
        "xai": (s.xai_api_key or "").strip(),
    }

    print("LLM providers (decompose.py — goal_text -> needs)")
    usable = []
    for name in ("gemini", "openai", "xai"):
        key = keys[name]
        if not key:
            print(f"  {WARN}  {name:8} no key set")
            continue
        status, detail = _probe_llm(name, key)
        print(f"  {status}  {name:8} …{key[-6:]}  {detail}")
        if status == OK:
            usable.append(name)

    print("\nVoice (Deepgram)")
    dg = (s.deepgram_api_key or "").strip()
    if not dg:
        print(f"  {WARN}  deepgram   no key set; /transcribe returns the fixture "
              "transcript for ANY audio and /speak returns silence")
    else:
        try:
            r = httpx.post(
                "https://api.deepgram.com/v1/speak",
                params={"model": s.deepgram_tts_model},
                headers={"Authorization": f"Token {dg}",
                         "Content-Type": "application/json"},
                json={"text": "ready"},
                timeout=20.0,
            )
            if r.status_code == 200 and r.content:
                print(f"  {OK}  deepgram   {s.deepgram_tts_model} returned "
                      f"{len(r.content)} bytes of audio")
            else:
                print(f"  {BAD}  deepgram   HTTP {r.status_code}: {r.text[:120]}")
        except httpx.HTTPError as exc:
            print(f"  {BAD}  deepgram   {type(exc).__name__}: {exc}")

    print("\nData source")
    if not client.configured():
        print(f"  {WARN}  supabase   not configured; reading seed/data/*.json")
    else:
        print(f"  ok    supabase   {repo.source()}")
    print(f"  ok    listings   {len(repo.listings())} rows available to the resolver")

    print("\nDemo mode")
    print(f"  ok    DEMO_MODE={s.demo_mode}  ({'fixtures only' if s.demo else 'live pipeline'})")

    if not usable:
        print(
            "\nNo usable LLM provider. Missions will still return a plan, but every "
            "goal decomposes into the seeded wardrobe needs and the plan is "
            'labelled source="fixture".'
        )
        return 1
    print(f"\nDecomposition will use: {usable[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
