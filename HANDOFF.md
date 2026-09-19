# ENOUGH — Backend handoff for the frontend lane

**Audience: C's Claude Code agent.** Paste this whole file into context. It
describes an API that is running and callable today, so build against it rather
than guessing. Where shapes appear below they are pasted verbatim from
`apps/api/models/schemas.py`, which is the source of truth.

If this file and `ARCHITECTURE.md` disagree, `ARCHITECTURE.md` wins — but §4 of
it was written before several changes landed, so read section 3 here first.

---

## 1. What the backend is, and what's live right now

A user states a **goal** ("business casual for my internship"). An agent
decomposes it into **needs**. For each need a resolver walks a ladder —
`OWN → BORROW → USED → NEW` — and returns ranked **options**. The whole thing is
one `Plan` object. You render that object. One **impact** number summarizes it.

Steps 1–6 of 9 are done and on the `backend` branch.

| Endpoint | State | Notes |
| :-- | :-- | :-- |
| `POST /api/mission` | **live** | Real resolver + real impact math. Returns a `Plan`. |
| `GET /api/mission/{id}` | **live** | Same `Plan` object. Exact replay once Supabase is connected; rebuilds otherwise. |
| `POST /api/fitcheck` | **stubbed** | Owned by A (CV). Returns a fixture with the real shape. Build against it. |
| `POST /api/checkout` | **stubbed** | Payment rail in progress. Returns an approved fixture. |
| `POST /api/voice/transcribe` | **stubbed** | Returns a canned transcript. Deepgram not wired yet. |
| `POST /api/voice/speak` | **stubbed** | Returns real `audio/mpeg` bytes (silent placeholder). |
| `GET /health` | **live** | Truthful even in demo mode. |

**With `DEMO_MODE=on`, every endpoint returns a fixture with no network calls at
all.** That is the mode you should develop in. The shapes are identical to
production, so nothing you build has to change when the live services land.

What is *not* built: `routers/ladder.py`. `ARCHITECTURE.md` §7 assigns it to the
backend lane but §4 defines no endpoint for it. **If your UI wants a "show me
more options for this need" interaction, say so and specify the shape** — it will
not be invented backend-side.

---

## 2. Every endpoint you touch

### `POST /api/mission`

Request:

```python
class MissionRequest(Base):
    user_id: str
    goal_text: str
    budget_cents: int = Field(ge=0)
```

Response is `Plan`:

```python
class Plan(Base):
    mission_id: str
    goal_text: str
    budget_cents: int = Field(ge=0)
    needs: list[Need]
    impact: Impact


class Need(Base):
    need_id: str
    label: str
    rationale: str
    priority: int = Field(ge=1, le=2)  # 1 = essential, 2 = nice-to-have
    options: list[Option]
    #: null when the need is unmet. See unmet_reason.
    recommended_listing_id: Optional[str] = None
    #: Set only when options is empty. Human-readable, shown in the UI.
    unmet_reason: Optional[str] = None


class Option(Base):
    listing_id: str
    rung: Rung
    title: str
    owner_label: str                      # "you", "Maya", "Uniqlo"
    price_cents: int = Field(ge=0)        # 0 for OWN and BORROW
    retail_cents: int = Field(ge=0)       # what it costs new
    image_url: Optional[str] = None       # OPTIONAL — may be absent
    match_score: float = Field(ge=0.0, le=1.0)
    why: str                              # one sentence, show verbatim
    needs_fitcheck: bool


class Impact(Base):
    baseline_cents: int = Field(ge=0)     # cost if every need were bought NEW
    plan_cents: int = Field(ge=0)         # cost of recommended options
    saved_cents: int
    items_reused: int = Field(ge=0)
    textile_kg_avoided: float = Field(ge=0.0)
    assumptions_note: str                 # show this; the number is an estimate


class Rung(str, Enum):
    OWN = "OWN"
    BORROW = "BORROW"
    USED = "USED"
    NEW = "NEW"
```

### `GET /api/mission/{mission_id}`

No request body. Returns the same `Plan` object.

### `POST /api/fitcheck`

`multipart/form-data`: `photo` (file), `height_cm` (float), `brand` (string),
`garment` (`"top"` or `"bottom"`).

```python
class FitCheckResult(Base):
    measurement_id: str
    measurements: Measurements
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_band: ConfidenceBand
    confidence_reason: str                # show this verbatim
    recommendation: SizeRecommendation


class Measurements(Base):
    chest_cm: MeasurementValue
    shoulder_cm: MeasurementValue
    waist_cm: MeasurementValue


class MeasurementValue(Base):
    """§4: never return a bare number. Always value + range."""
    value: float
    range: list[float] = Field(min_length=2, max_length=2)


class SizeRecommendation(Base):
    brand: str
    size_label: str
    alternate_size: Optional[str] = None
    note: str
    return_risk: Literal["low", "medium", "high"]


class ConfidenceBand(str, Enum):
    """HIGH >= 0.75 · MEDIUM 0.50-0.74 · LOW < 0.50"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
```

### `POST /api/checkout`

```python
class CheckoutRequest(Base):
    user_id: str
    listing_id: str
    measurement_id: Optional[str] = None  # null if non-apparel
    size_label: Optional[str] = None


class CheckoutResponse(Base):
    status: Literal["approved", "declined", "error"]
    txn_id: str
    amount_cents: int = Field(ge=0)
    receipt_url: Optional[str] = None     # OPTIONAL — may be absent
```

`status` has **three** values. `ARCHITECTURE.md` §4 shows only `"approved"`;
that is the happy path, not the only path. Handle all three.

### Voice

```python
# POST /api/voice/transcribe   multipart/form-data: audio (file)
class TranscribeResponse(Base):
    text: str

# POST /api/voice/speak        -> returns audio/mpeg bytes, NOT json
class SpeakRequest(Base):
    text: str
```

### `GET /health`

```json
{
  "ok": true,
  "demo_mode": "on",
  "credentials_present": {
    "openai": false, "supabase": false, "cybersource": true, "deepgram": false
  }
}
```

---

## 3. Contract changes since ARCHITECTURE.md §4 was written

These are the ones that change what you render. All are in the repo's
`ARCHITECTURE.md` changelog too.

### `recommended_listing_id` is now **nullable**

It was `str`. It is now `Optional[str]`. It is `null` exactly when the need is
unmet. **Anything dereferencing it must null-check first** — this is the change
most likely to throw in your code.

### `unmet_reason` — new field on `Need`

A need with no candidate on any rung **stays in the plan** rather than being
dropped, because dropping it would shrink the plan silently *and* inflate the
impact number. It arrives like this:

```json
{
  "need_id": "…",
  "label": "a tailcoat",
  "rationale": "The dress code says white tie.",
  "priority": 1,
  "options": [],
  "recommended_listing_id": null,
  "unmet_reason": "Found 4 item(s) in the right category, but none matched closely enough (best 0.00, need 0.35). Try relaxing the requirements for 'a tailcoat'."
}
```

The invariant, enforced server-side by a validator, keys on the
**recommendation**, not on `options`:

```
recommended_listing_id != null  ->  it is one of this need's options, no reason
recommended_listing_id == null  ->  unmet_reason is set; options MAY be non-empty
```

So there are **three** states, not two. **Branch on `unmet_reason`, never on
`options.length`:**

| State | Signal | Render |
| :- | :- | :- |
| Met | `recommended_listing_id` non-null | Normal card, highlight the recommendation |
| Unmet — nothing matched | `unmet_reason` set, `options: []` | Reason as the card body, no list |
| Unmet — unaffordable | `unmet_reason` set, `options` non-empty | Reason as the card body, **still list the options**, none recommended |

The third state is what budget enforcement produces: the options are kept on
purpose, because "three exist, none within your budget" is materially different
information from "nothing matched", and collapsing them would make the plan less
truthful. `unmet_reason` is written to be shown to the user directly.

### Empty `options` arrays are legal

`options: []` is valid and means unmet. Do not treat an empty array as a loading
state or an error.

### `needs_fitcheck` is top/bottom only

It is `true` only when the item's category is `top` or `bottom` **and** the rung
is `USED` or `NEW`. Footwear and outerwear are always `false`, even secondhand,
because `/api/fitcheck` only accepts `garment=top|bottom` and the size charts
cover only those. **§4's worked example shows a USED shoe with
`needs_fitcheck: true` — that is historical and no longer true.**

### `plan_json` and `prefs` columns (backend-only, context for you)

Two columns added to §3. Neither changes any response shape:

- `missions.plan_json` — stores the computed `Plan` so `GET /api/mission/{id}`
  is an exact replay rather than a re-derivation. **Implication for you:** once
  Supabase is connected, a GET is byte-identical to the POST that created it, so
  you can safely refetch. Until then a GET for an unknown id rebuilds and may
  return the hero plan.
- `users.prefs` — personal taste (colors, brands to avoid, preferred materials),
  used as a resolver scoring input. **Implication for you:** none today, but if
  you ever build a preferences screen, that is where it lands.

---

## 4. Local setup — you need no API keys

`DEMO_MODE=on` returns fixtures from disk with **no network calls and no
Supabase**. Leave every value in `.env` blank.

```bash
git clone https://github.com/Prisha-3012/ENOUGH---HackMIT.git
cd ENOUGH---HackMIT
git checkout backend

# Python 3.11 via uv. If you don't have uv:
#   curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.11
uv sync

cp .env.example .env     # leave every value blank; DEMO_MODE=on is already set

uv run uvicorn apps.api.main:app --reload --port 8000
```

- API: **http://localhost:8000**
- **Interactive docs: http://localhost:8000/docs** — every shape above is
  browsable and callable there. This is the fastest way to see real responses.
- Health: http://localhost:8000/health

Smoke test:

```bash
curl -X POST http://localhost:8000/api/mission \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"00000000-0000-0000-0000-000000000001",
       "goal_text":"business casual for my internship",
       "budget_cents":15000}'
```

Responses in demo mode carry an `X-Demo-Fixture` header naming the fixture used.

**CORS is already configured** for `http://localhost:3000`, `http://127.0.0.1:3000`,
`http://localhost:3001`, and `https://*.vercel.app`, with credentials allowed. If
your dev server lands on another port, say so and it gets added.

If a route ever returns **503 with "no fixture is registered"**, that is
deliberate — it means demo mode has no fixture for that path and is refusing to
run live code rather than silently hitting the network.

---

## 5. States the UI has to handle

Four of these are easy to miss because the happy path hides them.

**1. A need with zero options.** `options: []`. Render `unmet_reason` as the
body of the card. Do not render an empty option list, a spinner, or an error —
this is a successful response describing a real outcome. The need still has a
`label`, `rationale` and `priority` worth showing.

**2. `recommended_listing_id` is null.** **Not** always paired with
`options: []` — a need dropped for affordability keeps its options. Any code
doing `options.find(o => o.listing_id === need.recommended_listing_id)` must
null-check the id first or it will throw on unmet needs, and any code treating
a null recommendation as "nothing to show" will silently discard real options.

**3. An option with `needs_fitcheck: true`.** This option **cannot be checked
out** until FitCheck has produced a `measurement_id` for the user. The CTA should
route into the FitCheck flow rather than straight to checkout, and
`POST /api/checkout` should then carry that `measurement_id`. `false` means
checkout directly. In the hero fixture exactly two options are flagged, both
shirts (`USED` and `NEW`), and no footwear or outerwear ever is.

**4. Confidence bands, and measurements that are never bare numbers.** Every
measurement is `{"value": 98.2, "range": [94.1, 102.3]}`. **Render the range, not
just the value** — this is a deliberate product decision, not a debug field. Show
the band too:

| Band | Range | UI |
| :-- | :-- | :-- |
| `HIGH` | ≥ 0.75 | Show the size confidently |
| `MEDIUM` | 0.50–0.74 | Show the size with the range visible and the caveat |
| `LOW` | < 0.50 | Say so plainly and **offer a retake** |

`confidence_reason` is a human sentence explaining the score ("Both shoulders
clearly visible. Slight body rotation reduced waist precision.") — show it
verbatim. The project's stated position is that **a LOW result shown honestly
beats a fake HIGH**, so do not round a LOW up or hide the range to make the UI
look tidier.

Two smaller ones: `image_url` is optional and may be absent on any option, so
have a placeholder; and `receipt_url` on a checkout response is optional too.

---

## 6. The demo moment to design around

This is the thing that makes ENOUGH different from a shopping app, and it needs
to be **visible on screen**, not buried in a sorted list.

On need 2 of the hero plan, the recommended option has a **lower match score
than two options below it**:

```
two collared shirts you can rotate
  -> BORROW   0.83   Light blue oxford shirt, M   (Maya, your roommate)   $0.00
     USED     0.86   J.Crew cotton oxford, M                              $26.00
     NEW      0.88   Uniqlo easy-care oxford, M                           $39.90
```

The borrowed shirt scores **0.83** and still wins over options scoring **0.86**
and **0.88**. That is not a bug and must not be "fixed" by sorting on
`match_score`.

**Rung beats score.** The resolver walks `OWN → BORROW → USED → NEW` and
recommends the first rung that clears a quality threshold. A better-matching new
shirt never displaces a borrowed one that does the job, because the product
thesis is buying less, not buying better. The impact number counts
`items_reused`, so a UI that re-sorted by score would be arguing against the
app's own headline figure.

**Design implication:** do not present options as a flat ranked list ordered by
`match_score`. Present them as **rungs of a ladder**, in the array order the API
returns them, with the recommended one marked. The array is already in ladder
order — `OWN`, then `BORROW`, then `USED`, then `NEW` — so rendering it in order
is correct. Showing *why* the cheaper, lower-scoring option won is the moment
worth building for; each option's `why` string is written to carry exactly that.

One note on numbers: the figures above are from `hero_plan.json`, which is what
`DEMO_MODE=on` serves and therefore what you will see. The live resolver produces
slightly different scores for the same plan (`0.97` BORROW versus `0.99` for both
others) because it factors in user preferences. **The ordering and the
recommendation are identical either way** — only the decimals move. Don't
hard-code any score value.

Also worth surfacing: for the hero plan, **two of three needs cost $0** and the
impact block reads `baseline 37800 − plan 5500 = saved 32300`, `items_reused: 3`,
`textile_kg_avoided: 9.4`. `assumptions_note` should be shown near that number —
it is an estimate and says so.
