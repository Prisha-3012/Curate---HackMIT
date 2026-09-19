"""Seed loader.

    uv run python -m seed.load            # load users + listings into Supabase
    uv run python -m seed.load --check    # validate the seed files, touch nothing

--check needs no credentials and is what CI / a pre-demo sanity pass should run:
it catches malformed uuids, bad enum values, and the owner_id/rung rule before
Postgres does, plus verifies the seed can actually reproduce the hero plan.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from apps.api.config import FIXTURE_DIR, SEED_DIR
from apps.api.db import client

DATA_DIR = SEED_DIR / "data"

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
CATEGORIES = {"top", "bottom", "outerwear", "footwear", "other"}
RUNGS = {"OWN", "BORROW", "USED", "NEW"}
CONDITIONS = {"new", "excellent", "good", "fair"}
OWNED_RUNGS = {"OWN", "BORROW"}


def _read(name: str) -> list[dict[str, Any]]:
    path = DATA_DIR / name
    if not path.exists():
        raise SystemExit(f"seed file missing: {path}")
    return json.loads(path.read_text())


def validate(users: list[dict], listings: list[dict]) -> list[str]:
    """Mirror the SQL constraints in 001_init.sql, but with readable errors."""
    errors: list[str] = []
    user_ids = {u["id"] for u in users}

    for u in users:
        if not UUID_RE.match(u["id"]):
            errors.append(f"user {u.get('display_name')!r}: malformed uuid {u['id']!r}")

    seen: set[str] = set()
    for item in listings:
        tag = item.get("title", item.get("id", "?"))
        lid = item.get("id", "")

        if not UUID_RE.match(lid):
            errors.append(f"{tag}: malformed uuid {lid!r}")
        if lid in seen:
            errors.append(f"{tag}: duplicate id {lid}")
        seen.add(lid)

        if item.get("category") not in CATEGORIES:
            errors.append(f"{tag}: bad category {item.get('category')!r}")
        if item.get("rung") not in RUNGS:
            errors.append(f"{tag}: bad rung {item.get('rung')!r}")
        cond = item.get("condition")
        if cond is not None and cond not in CONDITIONS:
            errors.append(f"{tag}: bad condition {cond!r}")

        # listings_owner_matches_rung
        owner, rung = item.get("owner_id"), item.get("rung")
        if rung in OWNED_RUNGS and not owner:
            errors.append(f"{tag}: rung {rung} requires an owner_id")
        if rung in {"USED", "NEW"} and owner:
            errors.append(f"{tag}: rung {rung} must not have an owner_id")
        if owner and owner not in user_ids:
            errors.append(f"{tag}: owner_id {owner} is not a seeded user")

        # OWN and BORROW cost nothing, by definition of the rung.
        if rung in OWNED_RUNGS and item.get("price_cents", 0) != 0:
            errors.append(f"{tag}: rung {rung} must be price_cents 0")

    return errors


def check_hero_is_reproducible(listings: list[dict]) -> list[str]:
    """The hero fixture is the demo. If the seed can't reproduce it, the moment
    the resolver goes live in step 5 the demo changes under us."""
    hero_path = FIXTURE_DIR / "hero_plan.json"
    if not hero_path.exists():
        return [f"hero fixture missing: {hero_path}"]

    plan = json.loads(hero_path.read_text())
    by_id = {item["id"]: item for item in listings}
    errors: list[str] = []

    for need in plan["needs"]:
        for opt in need["options"]:
            row = by_id.get(opt["listing_id"])
            if row is None:
                errors.append(
                    f"hero option {opt['title']!r} ({opt['listing_id']}) "
                    f"has no matching seeded listing"
                )
                continue
            for field in ("rung", "price_cents", "retail_cents"):
                if row.get(field) != opt.get(field):
                    errors.append(
                        f"hero option {opt['title']!r}: {field} is {opt.get(field)!r} "
                        f"in the fixture but {row.get(field)!r} in the seed"
                    )
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed the ENOUGH database.")
    ap.add_argument("--check", action="store_true", help="validate only, write nothing")
    args = ap.parse_args()

    users = _read("users.json")
    listings = _read("listings.json")

    errors = validate(users, listings) + check_hero_is_reproducible(listings)
    if errors:
        print(f"✗ {len(errors)} seed problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"✓ seed valid: {len(users)} users, {len(listings)} listings")
    print("✓ hero plan is reproducible from the seeded listings")

    if args.check:
        return 0

    if not client.configured():
        print(
            "\n✗ SUPABASE_URL / SUPABASE_KEY are not set, so there is nothing to load.\n"
            "  1. Create a Supabase project\n"
            "  2. Paste seed/migrations/001_init.sql into the SQL editor and run it\n"
            "  3. Put the project URL and service_role key in .env\n"
            "  4. Re-run: uv run python -m seed.load",
            file=sys.stderr,
        )
        return 1

    try:
        # Users first: listings.owner_id references them.
        client.upsert("users", users)
        print(f"✓ upserted {len(users)} users")
        client.upsert("listings", listings)
        print(f"✓ upserted {len(listings)} listings")
    except client.DBUnavailable as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    print("\nDone. Flip DEMO_MODE=off to run against real data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
