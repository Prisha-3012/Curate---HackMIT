-- ENOUGH — initial schema. ARCHITECTURE.md §3.
-- Six tables. Resist adding a seventh.
--
-- Run: paste into the Supabase SQL editor (Dashboard -> SQL Editor -> New query).
-- Idempotent, so re-running after a seed wipe is safe.
--
-- TWO ADDITIVE COLUMNS beyond §3, both agreed with Prisha. Both are columns, not
-- tables, so the "resist a seventh" rule holds:
--   missions.plan_json  (2026-09-19) — §4 says GET /api/mission/{id} "returns the
--     same object", but nothing in §3 stores a computed Plan: no table holds an
--     option's match_score, why, or ranked ordering. Storing the serialized Plan
--     makes GET an exact replay instead of a re-derivation that could drift.
--   users.prefs         (2026-09-19) — personal taste (colors, brands to avoid,
--     fit) as a resolver input. §3 models what the GOAL requires (needs.attrs)
--     but not what the PERSON likes.
-- Both need circulating to the team before anyone codes against them.

create extension if not exists "pgcrypto";

-- people ---------------------------------------------------------------------
create table if not exists users (
  id            uuid primary key default gen_random_uuid(),
  display_name  text,
  height_cm     numeric,          -- needed for FitCheck scale (§5)
  prefs         jsonb not null default '{}'::jsonb,  -- ADDED, see header
  created_at    timestamptz not null default now()
);

-- everything that can satisfy a need, on any rung -----------------------------
create table if not exists listings (
  id            uuid primary key default gen_random_uuid(),
  title         text not null,
  category      text not null check (category in ('top','bottom','outerwear','footwear','other')),
  rung          text not null check (rung in ('OWN','BORROW','USED','NEW')),
  owner_id      uuid null references users(id) on delete set null,  -- set for OWN and BORROW
  brand         text null,
  size_label    text null,        -- 'M', '32x30'
  condition     text null check (condition is null or condition in ('new','excellent','good','fair')),
  price_cents   int not null default 0 check (price_cents >= 0),    -- 0 for OWN and BORROW
  retail_cents  int not null default 0 check (retail_cents >= 0),   -- savings baseline
  image_url     text,
  attrs         jsonb not null default '{}'::jsonb  -- {color, formality, warmth, ...}
);

-- OWN and BORROW are somebody's; USED and NEW are the market's.
alter table listings drop constraint if exists listings_owner_matches_rung;
alter table listings add constraint listings_owner_matches_rung check (
  (rung in ('OWN','BORROW') and owner_id is not null)
  or (rung in ('USED','NEW') and owner_id is null)
);

create index if not exists listings_rung_category_idx on listings (rung, category);
create index if not exists listings_attrs_idx on listings using gin (attrs);

-- a stated goal ---------------------------------------------------------------
create table if not exists missions (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references users(id) on delete cascade,
  goal_text     text not null,
  budget_cents  int not null default 0 check (budget_cents >= 0),
  plan_json     jsonb null,       -- ADDED, see header
  created_at    timestamptz not null default now()
);

create index if not exists missions_user_idx on missions (user_id, created_at desc);

-- LLM output: goal broken into real needs --------------------------------------
create table if not exists needs (
  id            uuid primary key default gen_random_uuid(),
  mission_id    uuid not null references missions(id) on delete cascade,
  label         text not null,    -- "a pair of non-sneaker shoes"
  rationale     text not null,    -- why this need exists, shown in UI
  category      text not null check (category in ('top','bottom','outerwear','footwear','other')),
  attrs         jsonb not null default '{}'::jsonb,  -- matched against listings.attrs
  priority      int not null default 1 check (priority in (1,2))  -- 1 essential, 2 nice-to-have
);

create index if not exists needs_mission_idx on needs (mission_id);

-- FitCheck output (A's lane; we only read it to gate checkout) ------------------
create table if not exists measurements (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references users(id) on delete cascade,
  height_cm         numeric,
  chest_cm          numeric,
  shoulder_cm       numeric,
  waist_cm          numeric,
  torso_cm          numeric,
  confidence        numeric check (confidence between 0 and 1),
  confidence_band   text check (confidence_band in ('HIGH','MEDIUM','LOW')),
  landmark_quality  jsonb,        -- raw mediapipe visibility, for debugging
  created_at        timestamptz not null default now()
);

create index if not exists measurements_user_idx on measurements (user_id, created_at desc);

-- post-purchase -----------------------------------------------------------------
create table if not exists purchases (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references users(id) on delete cascade,
  listing_id      uuid not null references listings(id),
  measurement_id  uuid null references measurements(id),  -- null if non-apparel
  size_bought     text,
  amount_cents    int not null check (amount_cents >= 0),
  txn_id          text,           -- Cybersource transaction id
  created_at      timestamptz not null default now()
);

create index if not exists purchases_user_idx on purchases (user_id, created_at desc);
create unique index if not exists purchases_txn_idx on purchases (txn_id) where txn_id is not null;

-- Brand size charts live in seed/size_charts/*.json, not the DB. They're static (§3).
