# ENOUGH

Use what exists. Buy what matters.

## Development

Node 20.20 or later. Run `npm install`, then `npm run dev` and open http://localhost:3000.

Validation: `npm run lint`, `npm run typecheck`, `npm run build`, `npm run test:e2e`.
Browser tests use installed Google Chrome; run `npx playwright install chrome` if needed.
To exercise a production build, start it with `npm run start` before running the browser suite.

## Two local fixtures

- `/` — Boston room setup. The original $731 retail → $314 plan / $417 savings demo, with six display groups and eight individually resolved needs.
- `/?fixture=camping&demoControls=true` — hand-authored UI development fixture, not AI-generated. Four sources, no location/distance/category metadata, a lower-scoring borrowed recommendation, one illustrated image, a FitCheck metadata flag, and an unmet navigation need. No FitCheck interaction is implemented.

`?demoControls=true` exposes stage shortcuts and the local fixture selector. Shortcuts hold their screen for inspection. Normal playback advances automatically after mission confirmation. Reset keeps mission text; changing fixtures clears it. The existing microphone button remains a labeled transcript simulation, with no microphone access.

Both fixtures are deterministic and need no external network, fonts, or image service. Editing mission text does not generate new needs: the selected local fixture is always used, as the UI disclosure states.

## Architecture

Next.js App Router, TypeScript, React, Tailwind CSS, Lucide icons, CSS animations.

- `lib/types.ts`: presentation models, including per-need options, recommendation and optional selection, match score, source/rung, explanations, image, FitCheck requirement, unmet reason, and impact assumptions.
- `lib/fixtures/`: all scenario-specific content. Boston and camping supply their own source ladders, labels, resource data, and optional comparison need.
- `lib/plan.ts`: pure grouping, candidate collection, selection, and local fixture accounting. Optional groups preserve Boston's six-card layout; ungrouped needs render independently. Recommendations are never sorted by score.
- `lib/services/enoughService.ts`: one `prepareMission(input, signal)` operation returns a complete `MissionExperience`. The controller reveals that result through Understanding → Search → Optimization → Plan. The single-result shape is ready for a future adapter; none is connected now.
- `lib/services/mockEnoughService.ts`: cancellable deterministic fixture preparation. `DEMO_MODE` stays true. Disabling it fails explicitly; the obsolete three-endpoint API adapter has been removed.
- `components/ResourceVisual.tsx`: optional image with a failure fallback to a deterministic illustrated inventory tag. Motifs are visual hints from fixture data, not inferred resource categories. The camping image is a local authored SVG asset.
- `components/ResourceCard.tsx`: scouting, comparison, and plan presentations of the same resource.

Components do not infer missing category, location, distance, preferences, or duration. An empty options array with an unmet reason is a legitimate outcome, not a loading state. Unmet needs remain visible; incomplete-plan savings are explicitly scoped to matched resources.

## Local accounting

Dollar values are summed as integer cents. Display preserves fractional prices (e.g. $39.90) without adding .00 to whole-dollar amounts. Retail equivalents are estimates per selected resource. New purchases avoided counts selected non-new resources. Existing reuse counts owned, borrowed, and shared selections, preserving the original Boston definitions. Nearby counts known distances of at most one mile; when no distances are supplied, the metric is omitted. A future backend adapter must retain the backend's own impact definitions rather than recomputing them with these local rules.

Zero budgets/baselines, negative savings, all-unmet plans, and empty need arrays have explicit render behavior. Invalid recommendation references fail rather than disappearing from the plan.

## Demo timing and accessibility

Preparation takes 900 ms. After confirmation, scouting begins with 1,000 ms followed by 850 ms per supplied source. Optimization takes 1,400 ms, followed by the 900 ms savings reveal. Reset, edit, and fixture switching cancel pending delays. Reduced-motion preferences disable decorative movement and number counting. Buttons and form controls support keyboard use, visible focus, and status announcements.

## Current scope

Frontend-only local fixture rendering. No live backend request/proxy, inventory scanning, checkout, FitCheck flow, actual voice, authentication, ownership graph, or marketplace scraping. The Boston fixture remains the default.

Next.js's PostCSS dependency is overridden to the compatible patched 8.5 series; keep the override until Next.js updates its own dependency.

### Backend adapter (opt-in)

Offline Boston/camping fixtures remain the default and make no API requests.
Copy `.env.example` to `.env.local`, configure the public API base URL (including
`/api`) and seeded user ID, and set `NEXT_PUBLIC_DEMO_MODE=false` to opt into the
backend service. Restart/rebuild Next after changing public environment variables.
No credentials belong in `NEXT_PUBLIC_*` values. Live requests require exactly
one explicit dollar budget in the mission text (including `$0`); no default cap
is inferred. The service sends one `POST /api/mission`, validates its response,
and adapts it to `MissionExperience`. Subsequent screens reveal that result with
local timing, without further requests. Failures remain errors; there is no
silent local fixture fallback.

DTOs live in `lib/api/plan.ts`; `validatePlan` checks wire types, safe integer
cents, enum/range constraints, unique IDs within their scope, and recommendation
invariants. `adaptBackendPlan` preserves ordered needs/options, authoritative
backend impact and unmet candidates. Backend reuse counts include USED and have
a distinct label. Absent metadata stays absent. Fixture accounting is separate.

**Backend blockers before calling this a verified live experience:**

- `budget_cents: 0` currently bypasses backend budget enforcement. The frontend
  sends explicit zero unchanged and displays the returned budget/cost honestly;
  the backend must agree on zero versus an unspecified/unlimited budget.
- The mission handler can return a wardrobe fixture after a planner failure with
  HTTP 200 and no marker. Unmarked responses are therefore `backend-unverified`,
  never confidently live. `X-Demo-Fixture` responses are `backend-demo` and name
  the fixture. `backend-live` is reserved in the view model but is never assigned
  until a reliable backend provenance contract exists. Goal-text heuristics are
  not a substitute for that contract.
- Direct browser requests require backend CORS to allow the frontend origin.
  The configured user ID is a development identity, not authentication.

FitCheck flags are informational only. No checkout, payment, auth, or FitCheck
flow is implemented. Backend service tests mock HTTP; they do not call live APIs.

Validation: `npm run test:e2e` builds and starts a fresh production server on
port 3000 for offline fixtures and adapter/service tests.
`npx playwright test --config=playwright.backend.config.ts` builds backend mode
and tests the browser flow on port 3002 with intercepted HTTP (no live backend).
Run these suites sequentially because both use Next's `.next` output; run the
offline suite last to restore the default demo build. Both ports must be free.
