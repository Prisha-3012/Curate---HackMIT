-- 002: categories become free-form. ARCHITECTURE.md §3.
--
-- WHY: /api/mission is domain-agnostic as of 2026-09-19. A goal like "camping
-- with four friends" or "dinner for 12" decomposes into needs whose categories
-- ("shelter", "cookware", "cold-storage") cannot be known in advance, so a
-- closed enum of clothing categories is no longer meaningful.
--
-- The clothing values remain the convention for apparel, and needs_fitcheck_for()
-- still keys on them — an unknown category is simply not fit-checkable.
--
-- Idempotent. Paste into the Supabase SQL editor after 001_init.sql.

alter table listings drop constraint if exists listings_category_check;
alter table needs    drop constraint if exists needs_category_check;

-- Shape only: a short lowercase token. Stops empty strings and stray casing
-- without pretending we know the domain in advance.
alter table listings add constraint listings_category_shape
  check (category ~ '^[a-z][a-z0-9-]{1,31}$');

alter table needs add constraint needs_category_shape
  check (category ~ '^[a-z][a-z0-9-]{1,31}$');
