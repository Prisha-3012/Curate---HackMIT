# ENOUGH — Architecture

Single source of truth for the 24h build. If code and this doc disagree, fix the code or fix the doc — don't leave them apart.

> **This file is the contract.** It was a Google Doc until 2026-09-19; the Doc is now
> dead. Edit this file directly whenever a shape changes, in the same commit as the
> code change. See the changelog at the bottom.

---

## 1. The one-paragraph version

A user states a **goal** (not a product). The **agent** decomposes it into **needs**. For each need, the **resolver** walks a ladder — OWN → BORROW → USED → NEW — and returns ranked **options**. The whole thing is one Plan object. If the chosen option is on the NEW or USED rung and it's apparel, **FitCheck** gates it with a size + confidence score before **checkout** fires. One **impact** number summarizes the plan.

Everything is that one Plan object. Frontend renders it, voice reads it, checkout consumes one option out of it.

---

## 2. System map

```
                    ┌─────────────────────────────┐
  mic ──STT──►      │  POST /api/mission          │
  text ──────►      │  { goal, budget_cents }     │
                    └────────────┬────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  decompose.py  (OpenAI) │  goal → Need[]
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  resolver.py            │  per need, walk ladder
                    │  OWN→BORROW→USED→NEW    │  query seeded pool
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  savings.py             │  baseline − actual
                    └────────────┬────────────┘
                                 │
                            ┌────▼────┐
                            │  Plan   │ ──TTS──► speaker
                            └────┬────┘
                                 │  user picks a NEW/USED apparel option
                    ┌────────────▼────────────┐
                    │  POST /api/fitcheck     │  photo + height
                    │  pose → measure → size  │  → size + confidence
                    └────────────┬────────────┘
                                 │  confidence gate
                    ┌────────────▼────────────┐
                    │  POST /api/checkout     │  Stripe test mode
                    └────────────┬────────────┘
                                 │
                            purchases row  (post-purchase stage)
```

---

## 3. Data model (Postgres / Supabase)

Six tables. Resist adding a seventh.

```sql
-- people
users (
  id            uuid pk,
  display_name  text,
  height_cm     numeric,          -- needed for FitCheck scale
  prefs         jsonb,            -- ADDED 2026-09-19: personal taste, see below
  created_at    timestamptz
)

-- everything that can satisfy a need, on any rung
listings (
  id            uuid pk,
  title         text,
  category      text,             -- 'top' | 'bottom' | 'outerwear' | 'footwear' | 'other'
  rung          text,             -- 'OWN' | 'BORROW' | 'USED' | 'NEW'
  owner_id      uuid null,        -- set for OWN and BORROW
  brand         text null,
  size_label    text null,        -- 'M', '32x30'
  condition     text null,        -- 'new' | 'excellent' | 'good' | 'fair'
  price_cents   int,              -- 0 for OWN, 0 for BORROW
  retail_cents  int,              -- what it costs new; used for savings baseline
  image_url     text,
  attrs         jsonb             -- {color, formality, warmth, ...} for matching
)

-- a stated goal
missions (
  id            uuid pk,
  user_id       uuid fk,
  goal_text     text,
  budget_cents  int,
  plan_json     jsonb null,       -- ADDED 2026-09-19: the computed Plan, see below
  created_at    timestamptz
)

-- LLM output: goal broken into real needs
needs (
  id            uuid pk,
  mission_id    uuid fk,
  label         text,             -- "a pair of non-sneaker shoes"
  rationale     text,             -- why this need exists, shown in UI
  category      text,
  attrs         jsonb,            -- desired attributes, matched against listings.attrs
  priority      int               -- 1 = essential, 2 = nice-to-have
)

-- FitCheck output
measurements (
  id                uuid pk,
  user_id           uuid fk,
  height_cm         numeric,
  chest_cm          numeric,
  shoulder_cm       numeric,
  waist_cm          numeric,
  torso_cm          numeric,
  confidence        numeric,      -- 0..1
  confidence_band   text,         -- 'HIGH' | 'MEDIUM' | 'LOW'
  landmark_quality  jsonb,        -- raw mediapipe visibility scores, for debugging
  created_at        timestamptz
)

-- post-purchase
purchases (
  id              uuid pk,
  user_id         uuid fk,
  listing_id      uuid fk,
  measurement_id  uuid null fk,   -- null if non-apparel
  size_bought     text,
  amount_cents    int,
  txn_id          text,           -- payment processor transaction id
  created_at      timestamptz
)
```

**Two columns added 2026-09-19.** Both are columns, not tables, so "resist a seventh" holds.

- `missions.plan_json` — §4 says `GET /api/mission/{id}` "returns the same object", but nothing here stored a computed Plan: no table held an option's `match_score`, `why`, or ranked ordering. This makes GET an exact replay rather than a re-derivation that can drift.
- `users.prefs` — personal taste as a resolver input, e.g. `{"colors":["navy"],"avoid_colors":["neon"],"materials_preferred":["wool"]}`. The rest of the model captures what the *goal* requires (`needs.attrs`) but not what the *person* likes. Taste is a nudge, never a veto: it breaks ties between candidates that already satisfy the need and cannot promote one that doesn't.

Brand size charts live in `seed/size_charts/*.json`, not the DB. They're static.

```json
// seed/size_charts/uniqlo_mens_tops.json
{
  "brand": "Uniqlo",
  "garment": "top",
  "unit": "cm",
  "sizes": [
    { "label": "S",  "chest": [88, 96],   "shoulder": [41, 43] },
    { "label": "M",  "chest": [96, 104],  "shoulder": [43, 45] },
    { "label": "L",  "chest": [104, 112], "shoulder": [45, 47] }
  ]
}
```

---

## 4. API contract

**This is the part that unblocks parallel work.** Everyone codes against these shapes from hour 0, using fixtures, before any of it is real.

### POST /api/mission

```json
// request
{ "user_id": "uuid", "goal_text": "business casual for my internship", "budget_cents": 15000 }
```

```json
// response — the Plan object. Everything downstream renders this.
{
  "mission_id": "uuid",
  "goal_text": "business casual for my internship",
  "budget_cents": 15000,
  "needs": [
    {
      "need_id": "uuid",
      "label": "a pair of non-sneaker shoes",
      "rationale": "Most business-casual dress codes rule out athletic sneakers.",
      "priority": 1,
      "options": [
        {
          "listing_id": "uuid",
          "rung": "OWN",
          "title": "Brown leather oxfords",
          "owner_label": "you",
          "price_cents": 0,
          "retail_cents": 9000,
          "image_url": "/seed/oxfords.jpg",
          "match_score": 0.91,
          "why": "You already own these. They match the formality this goal needs.",
          "needs_fitcheck": false
        },
        {
          "listing_id": "uuid",
          "rung": "USED",
          "title": "Cole Haan loafers, size 9",
          "owner_label": "Poshmark seller",
          "price_cents": 4200,
          "retail_cents": 16000,
          "match_score": 0.78,
          "why": "Secondhand, 74% below retail.",
          "needs_fitcheck": false
        }
      ],
      "recommended_listing_id": "uuid",
      "unmet_reason": null
    }
  ],
  "impact": {
    "baseline_cents": 48000,
    "plan_cents": 11200,
    "saved_cents": 36800,
    "items_reused": 3,
    "textile_kg_avoided": 8.4,
    "assumptions_note": "Estimates. See seed/impact_constants.json for sources."
  }
}
```

`GET /api/mission/{id}` returns the same object.

#### Field notes

- `image_url` is **optional** on an option.
- `match_score` is 0..1. `priority` is 1 or 2.
- `budget_cents` is **nullable** (2026-09-19). `null` means no budget was stated and nothing is enforced; `0` is a real zero-dollar constraint meaning only free options (OWN, BORROW) may be recommended. These were the same value until 2026-09-19, so a user who said they could spend nothing was handed a plan that spent money.
- `source` is `"live"` or `"fixture"` (2026-09-19). `"fixture"` means the plan is canned data standing in for one we could not compute — `DEMO_MODE=on`, or the live pipeline failing behind the standing never-take-the-demo-down rule. **A fixture plan does not describe the goal that was asked for**: the hero fixture is a wardrobe plan and will be returned for a camping goal. Consumers must never present it as a real result.
- `baseline_cents` is the sum of the recommended options' `retail_cents` — what the same wardrobe costs at full price. Summing each need's cheapest NEW option instead would flatter the result, because a need with no NEW listing contributes nothing to the baseline while still contributing to the plan.
- The `needs` rows carry `category` and `attrs`, but the Plan **does not serialize them**. They stay server-side for the resolver.

#### `needs_fitcheck` — top and bottom only

FitCheck gates NEW and USED apparel, but `POST /api/fitcheck` accepts `garment=top|bottom` and the size charts cover only those. A flagged shoe is a promise the API cannot keep, so:

```
needs_fitcheck = category in (top, bottom) AND rung in (USED, NEW)
```

Footwear, outerwear and other are always `false`. **Note:** the worked example above is historical — it originally marked the USED shoe `true`. It does not any more. If footwear sizing ever lands, revisit this.

#### Unmet needs (added 2026-09-19)

A need with no candidate anywhere on the ladder **stays in the plan**:

```json
{
  "need_id": "uuid",
  "label": "a tailcoat",
  "rationale": "The dress code says white tie.",
  "priority": 1,
  "options": [],
  "recommended_listing_id": null,
  "unmet_reason": "Found 4 item(s) in the right category, but none matched closely enough (best 0.00, need 0.35). Try relaxing the requirements for 'a tailcoat'."
}
```

- `recommended_listing_id` is **nullable**. Anything rendering it must handle null.
- `unmet_reason` is set **exactly** when `recommended_listing_id` is null, and is null otherwise. It is keyed on the recommendation, not on `options`.
- A need is met (a recommendation, which is one of its own options) or unmet (no recommendation, **plus** a reason). An unmet need **may still carry options**: budget enforcement (§4, planner) drops a need to unmet while keeping what it found, because "three exist, none affordable" is different information from "nothing matched". Consumers branch on `unmet_reason`, never on `len(options)`.
- **Impact counts only met needs.** Dropping unmet needs instead would shrink the plan silently *and* flatter the impact number, since a need contributing nothing to `plan_cents` would also stop contributing to `baseline_cents`. The impact number must never overstate what the user achieved.

### POST /api/fitcheck

`multipart/form-data`: `photo` (file), `height_cm` (float), `brand` (string), `garment` (`top|bottom`)

```json
{
  "measurement_id": "uuid",
  "measurements": {
    "chest_cm":    { "value": 98.2, "range": [94.1, 102.3] },
    "shoulder_cm": { "value": 44.0, "range": [42.5, 45.5] },
    "waist_cm":    { "value": 82.5, "range": [77.0, 88.0] }
  },
  "confidence": 0.72,
  "confidence_band": "MEDIUM",
  "confidence_reason": "Both shoulders clearly visible. Slight body rotation reduced waist precision.",
  "recommendation": {
    "brand": "Uniqlo",
    "size_label": "M",
    "alternate_size": "L",
    "note": "M fits your chest; size up to L if you prefer a looser fit.",
    "return_risk": "low"
  }
}
```

**Never return a bare number.** Always value + range + band. This is both honest and the thing judges remember.

### POST /api/checkout

```json
// request
{ "user_id": "uuid", "listing_id": "uuid", "measurement_id": "uuid|null", "size_label": "M" }
```

```json
// response
{ "status": "approved", "txn_id": "pi_3...", "amount_cents": 4200, "receipt_url": "..." }
```

- `status` is `"approved" | "declined" | "error"`. The happy path is not the only path.
- `receipt_url` is **optional** — not every processor returns one, and we synthesize a local `/receipt/{txn_id}` when it doesn't.

### Voice

- `POST /api/voice/transcribe` — audio blob → `{ "text": "..." }`
- `POST /api/voice/speak` — `{ "text": "..." }` → `audio/mpeg`

---

## 5. Confidence model

Don't hand-wave this — it's a differentiator. Three inputs:

```python
def confidence(landmarks, height_given: bool) -> float:
    # 1. how clearly did MediaPipe see the joints that matter?
    key = [LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP]
    visibility = mean(landmarks[i].visibility for i in key)      # 0..1

    # 2. is the person square to the camera? asymmetry = rotation = error
    symmetry = 1 - min(1, abs(left_width - right_width) / max(left_width, right_width))

    # 3. without height we have no pixel→cm scale at all
    scale = 1.0 if height_given else 0.35

    return round(visibility * 0.4 + symmetry * 0.3 + scale * 0.3, 2)
```

Bands: HIGH >= 0.75 · MEDIUM 0.50–0.74 · LOW < 0.50

Range width scales inversely with confidence: ± (1 - confidence) * 12cm.

If LOW, the UI says so plainly and offers a retake. **A LOW result shown honestly beats a fake HIGH.**

---

## 6. Demo-safety: fixture replay

Non-negotiable, built in from hour 0.

```python
# apps/api/main.py
DEMO_MODE = os.getenv("DEMO_MODE", "off")
```

**`DEMO_MODE=on` short-circuits EVERY route to fixtures, unconditionally** (changed 2026-09-19; it was originally gated on a fuzzy match against the hero goal string). On stage, nothing should be able to reach the network — the original rule let an off-script goal fall through to the live pipeline, which is exactly the moment you least want a live pipeline.

Implemented as middleware, not a per-router dependency, so the short-circuit lands before any handler body runs and a router added later cannot forget to opt in. An `/api/` route with no registered fixture returns **503 rather than running live code**, so a missing fixture surfaces in rehearsal instead of on stage.

Hero path replays in <100ms with no network. Currently 0.78ms.

Write `seed/fixtures/hero_plan.json` **by hand, in hour 1**, before any real code. It defines the contract *and* it's the safety net.

---

## 7. Module → owner map

```
apps/api/services/
  pose.py          measure.py      sizing.py         → A
  decompose.py     resolver.py     savings.py        → B
  payments.py                                        → D
  voice.py                                           → B   (was C, moved 2026-09-19)
apps/api/routers/
  fitcheck.py   → A      mission.py, ladder.py → B
  checkout.py   → D      voice.py              → B   (was C, moved 2026-09-19)
apps/web/app/
  fitcheck/     → A      page.tsx, plan/       → C      checkout/ → D
seed/                                                  → D  (B also writes fixtures + loader)
apps/api/models/schemas.py                             → shared, ping before editing
```

One person per file. `main.py` is written once in hour 0 and never touched again.

**`routers/ladder.py` is assigned to B but §4 defines no endpoint for it.** It is unbuilt on purpose. If the UI wants "show me more options for this need", C specifies the shape first.

---

## 8. Build order

| Hours | Milestone |
| :- | :- |
| 0–1.5 | Schemas locked, hero_plan.json hand-written, hello-world deployed, **payment signup submitted** |
| 1.5–5 | Spine clickable end to end, every service faked |
| 5–9 | D: real checkout (timebox 3h) |
| 5–14 | A: real pose+measure · B: real decompose+resolver · C: real UI + Deepgram |
| 14–17 | Join lanes: NEW rung → FitCheck gate → checkout. Impact number live |
| 17–20 | Seed the world, polish, cache hero path |
| 20–22 | Demo script, rehearse 3× out loud |
| 22–24 | **Freeze.** Bugs only |

---

## Changelog

Everything below changed after the original Doc was written. Each entry says why.

### 2026-09-19 — Gemini as a third provider, and a preflight check

`decompose.py` now knows three providers — Gemini, OpenAI, xAI — all over the
OpenAI chat-completions protocol. `LLM_PROVIDER=auto` takes the first key that
is set, Gemini first, because it is the one with a free tier.

They differ in how JSON can be demanded. `strict: true` inside a `json_schema`
response format is OpenAI's own feature: the API enforces the shape. Compat
layers commonly **accept the field and ignore the enforcement**, which is worse
than not supporting it — the model returns prose, parsing fails, and the fixture
fallback makes it look like decomposition is working. So each provider declares
`structured: "schema" | "object"`; under `"object"` the shape is spelled out in
the prompt and every field is parsed defensively (a bare list, needs under an
unexpected key, `attrs` as a plain object rather than a key/value array).

`python -m apps.api.preflight` makes one minimal call per configured provider
and prints what came back. `/health` reports whether a key is PRESENT, which is
a different question: both keys in this repo were present, valid, and had zero
credits, and the only symptom was every goal quietly decomposing into the seeded
wardrobe needs.

### 2026-09-19 — `budget_cents` nullable, and `Plan.source`

Two fields on the §4 contract, both because the API could not previously tell
the truth about something.

`budget_cents` was `int` with `0` meaning "unstated", so a stated $0 budget was
indistinguishable from no budget and was silently ignored. It is now `Optional[int]`:
`null` is unstated, `0` is a real constraint. Enforcement lives in the planner
and now falls through to the drop loop at `0`, which keeps free (OWN/BORROW)
recommendations and drops every paid one.

`Plan.source` did not exist. `POST /api/mission` catches any planner exception
and returns `hero_plan.json` at **200** so the demo cannot go down — but it
returned it unlabelled, so canned wardrobe data was indistinguishable from a
real answer to whatever was asked. The field is set in the fixture file itself,
so it covers the `DEMO_MODE` path and the failure path alike, and it is
persisted to `missions.plan_json` so `GET` replays stay honest.

### 2026-09-19 — Cybersource → Stripe test mode
Cybersource sandbox credentials and HTTP Signature auth were verified working (real transaction ids returned), but every request — auth-only, no-CVV, `capture:false`, multiple amounts — returned `502 SERVER_ERROR / SYSTEM_ERROR`. That is account provisioning, not code. Switched to §8's documented fallback, Stripe test mode, behind the unchanged §4 `/api/checkout` shape. Visa Developer's Authorization API is being attempted as a second implementation behind the same interface, timeboxed.

Two Cybersource gotchas recorded in case anyone returns to it: `Accept` must be `application/hal+json` (with `application/json` the edge returns a misleading plain-text 404), and `host` must be part of the signing string but must **not** be sent as a request header.

### 2026-09-19 — Unmet needs stay in the plan
`recommended_listing_id` became nullable and `unmet_reason` was added. See §4. Dropping unmet needs shrank the plan silently and flattered the impact number.

### 2026-09-19 — `users.prefs` and `missions.plan_json`
Two columns, not tables. See §3.

### 2026-09-19 — `needs_fitcheck` restricted to top/bottom
`/api/fitcheck` cannot size footwear, so it is no longer flagged for it. See §4.

### 2026-09-19 — `DEMO_MODE` short-circuits unconditionally
Was a fuzzy match on the hero goal. See §6.

### 2026-09-19 — voice backend routes moved from C to B
C keeps frontend mic capture and playback. See §7.

### 2026-09-19 — this file moved from Google Docs into the repo
The Doc could not be diffed alongside the code, which made §0's "fix the code or fix the doc" impossible to honour. The Doc is now dead; this file is the contract.
