# ENOUGH

Use what exists. Buy what matters.

## Development

Node 20.20 or later. Run `npm install`, then `npm run dev` and open http://localhost:3000.

Validation: `npm run lint`, `npm run typecheck`, `npm run build`, `npm run test:e2e`. Browser tests use installed Google Chrome; run `npx playwright install chrome` if needed. The suite checks the offline flow, budget math, reset cancellation, stage shortcuts, voice simulation, and mobile layouts.

Open `/?demoControls=true` for presenter stage shortcuts. Search and optimization shortcuts hold that screen for inspection; the normal flow advances automatically. Reset keeps the mission text for easy rehearsal. The microphone button inserts a clearly labeled simulated transcript and never requests microphone access.

## Architecture

Next.js App Router, TypeScript, React, Tailwind CSS, Lucide icons. No external assets, fonts, or network requests are required by the mock experience after installation.

`lib/types.ts` defines the domain models. `lib/demo-data.ts` owns the Boston fixture, candidate resources, selected resource IDs, timing, and calculations. `lib/services/enoughService.ts` defines the service contract. Components use the service selected in `lib/services/index.ts`.

`DEMO_MODE` defaults to true. The mock is a rehearsable Boston room setup fixture, not a general natural-language interpreter. All delays are fixed. Retail equivalents are per-resource demo values. Purchases avoided counts every selected non-new item. Reused resources counts owned, borrowed, and shared selections. Nearby counts selected items with a known distance of at most one mile. Mock inventory and circle data are seeded; no actual possessions or contacts are accessed.

The real API adapter proposes POST `/missions/understand`, `/resources/search`, and `/plans/optimize` relative to `/api`. These routes are not implemented locally. Align payloads and add response validation with the backend team before disabling demo mode.

## Scope

First milestone: Mission → Understanding → Resource Search → Optimization → Plan. Inventory scanning, preference feedback, execution, and ownership are intentionally outside this implementation.

## Demo timing

Mission understanding takes 900 ms. After presenter confirmation, resource discovery takes 1,000 ms followed by five source reveals of 850 ms each. Optimization takes 1,400 ms, followed by a 900 ms CSS/animation-frame savings reveal. Reduced-motion preferences disable decorative motion and number counting.

## Dependency note

Next.js’s nested PostCSS is overridden to the compatible patched 8.5 series. Keep this override until Next.js updates its own dependency.
