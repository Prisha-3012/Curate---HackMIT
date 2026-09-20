import { test, expect } from "@playwright/test";
import { createElement } from "react";
import { createRequire } from "node:module";
import * as jsx from "react/jsx-runtime";
import { renderToStaticMarkup } from "react-dom/server";
import { validatePlan } from "../lib/api/validatePlan";
import { adaptBackendPlan } from "../lib/api/adaptBackendPlan";
import { createEnoughApi, parseBudgetCents } from "../lib/services/enoughApi";
import type { Plan } from "../lib/api/plan";
import { EnoughPlan } from "../components/EnoughPlan";
import { OptimizationView } from "../components/OptimizationView";
Object.assign(
  createRequire(`${process.cwd()}/package.json`)("playwright/jsx-runtime"),
  jsx,
);
const plan = (): Plan => ({
  mission_id: "mission",
  source: "live",
  goal_text: "Host dinner",
  budget_cents: 2000,
  needs: [
    {
      need_id: "plates",
      label: "Plates",
      rationale: "Serve guests",
      priority: 1,
      recommended_listing_id: "borrow",
      unmet_reason: null,
      options: [
        {
          listing_id: "borrow",
          rung: "BORROW",
          title: "Borrowed plates",
          owner_label: "Sam",
          price_cents: 0,
          retail_cents: 1299,
          match_score: 0.83,
          why: "Borrow meets the need first.",
          needs_fitcheck: false,
        },
        {
          listing_id: "new",
          rung: "NEW",
          title: "New plates",
          owner_label: "Store",
          price_cents: 1499,
          retail_cents: 1499,
          match_score: 0.99,
          why: "New alternative",
          needs_fitcheck: true,
          image_url: null,
        },
      ],
    },
  ],
  impact: {
    baseline_cents: 1299,
    plan_cents: 0,
    saved_cents: 1299,
    items_reused: 1,
    textile_kg_avoided: 0,
    assumptions_note: "Matched resources only.",
  },
});
function render(p: Plan) {
  return renderToStaticMarkup(
    createElement(EnoughPlan, {
      experience: adaptBackendPlan(validatePlan(p), p.goal_text),
      onRestart() {},
    }),
  );
}
test("fully solved: ordered options, earlier BORROW wins, explicit conversion and no invented metadata", () => {
  const p = plan();
  const e = adaptBackendPlan(validatePlan(p), "original");
  expect(e.mission.needs[0].options.map((o) => o.id)).toEqual([
    "borrow",
    "new",
  ]);
  expect(e.plan.items[0].resource.matchScore).toBe(0.83);
  expect(e.plan.retailEquivalent).toBe(12.99);
  expect(e.mission.needs[0].options[1].price).toBe(14.99);
  expect(e.mission.needs[0].options[1].needsFitcheck).toBe(true);
  expect(e.sources.map((s) => s.label)).toEqual([
    "OWN",
    "BORROW",
    "USED",
    "NEW",
  ]);
  expect(e.mission.location).toBeUndefined();
  expect(e.plan.nearbyResources).toBeUndefined();
  expect(e.plan.reuseLabel).toContain("including used");
  expect(render(p)).toContain("YOUR MISSION, MADE POSSIBLE");
  expect(e.provenance).toBe("backend-live");
  expect(
    adaptBackendPlan({ ...p, source: "fixture" }, "original", "hero")
      .provenance,
  ).toBe("backend-demo");
  expect(p).toEqual(plan());
});
test("partial plan preserves empty and budget-unmet candidates without selection or costing", () => {
  const p = plan();
  p.needs.push({
    ...structuredClone(p.needs[0]),
    need_id: "extra",
    priority: 2,
    recommended_listing_id: null,
    unmet_reason: "Outside the budget",
  });
  p.needs.push({
    ...structuredClone(p.needs[0]),
    need_id: "missing",
    options: [],
    recommended_listing_id: null,
    unmet_reason: "Nothing available",
  });
  const e = adaptBackendPlan(validatePlan(p), "goal");
  expect(e.plan.unmetNeedIds).toEqual(["extra", "missing"]);
  expect(e.plan.items).toHaveLength(1);
  expect(e.mission.needs[1].priority).toBe("preferred");
  const html = render(p);
  expect(html).toContain("1 of 3 needs matched");
  expect(html).toContain("Outside the budget");
  expect(html).toContain("Nothing available");
  expect(html).toContain("not included in this plan");
  const optimization = renderToStaticMarkup(
    createElement(OptimizationView, {
      need: e.mission.needs[1],
      candidateCount: 2,
    }),
  );
  expect(optimization).toContain("Outside the budget");
  expect(optimization).not.toContain('data-recommended="true"');
});
test("all unmet and explicit zero budget retain intent without invalid savings", () => {
  const p = plan();
  p.budget_cents = 0;
  p.needs[0].recommended_listing_id = null;
  p.needs[0].unmet_reason = "No budget";
  p.impact = {
    ...p.impact,
    baseline_cents: 0,
    plan_cents: 0,
    saved_cents: 0,
    items_reused: 0,
  };
  expect(parseBudgetCents("A dinner for $0")).toBe(0);
  expect(render(p)).toContain("0 of 1 needs matched");
  expect(render(p)).not.toMatch(/NaN|Infinity|role="meter"/);
  expect(parseBudgetCents("dinner")).toBeNull();
  expect(() => parseBudgetCents("$10 or $20")).toThrow();
});
test("runtime validation rejects malformed fields and broken recommendation invariants", () => {
  for (const mutate of [
    (p: Plan) => {
      p.needs[0].options[0].price_cents = 1.5;
    },
    (p: Plan) => {
      p.needs[0].options[0].match_score = NaN;
    },
    (p: Plan) => {
      p.needs[0].recommended_listing_id = "missing";
    },
    (p: Plan) => {
      p.needs[0].recommended_listing_id = null;
    },
    (p: Plan) => {
      p.impact.plan_cents = Infinity;
    },
  ]) {
    const p = plan();
    mutate(p);
    expect(() => validatePlan(p)).toThrow("invalid plan");
  }
  expect(() => validatePlan(null)).toThrow();
});
test("service sends exactly one POST with zero cents, validates and identifies demo provenance", async () => {
  const original = globalThis.fetch;
  const requests: RequestInit[] = [];
  globalThis.fetch = async (url, init) => {
    expect(url).toBe("http://backend/api/mission");
    requests.push(init!);
    return new Response(JSON.stringify({ ...plan(), source: "fixture" }), {
      headers: { "X-Demo-Fixture": "hero" },
    });
  };
  try {
    const e = await createEnoughApi(
      "http://backend/api/",
      "user",
    ).prepareMission("Dinner $0");
    expect(requests).toHaveLength(1);
    expect(requests[0].method).toBe("POST");
    expect(JSON.parse(requests[0].body as string)).toEqual({
      user_id: "user",
      goal_text: "Dinner $0",
      budget_cents: 0,
    });
    expect(e.provenance).toBe("backend-demo");
    globalThis.fetch = async () => new Response("{}");
    await expect(
      createEnoughApi("http://backend/api", "user").prepareMission(
        "Dinner $20",
      ),
    ).rejects.toThrow("invalid plan");
    globalThis.fetch = async () => new Response("", { status: 500 });
    await expect(
      createEnoughApi("http://backend/api", "user").prepareMission(
        "Dinner $20",
      ),
    ).rejects.toThrow("500");
  } finally {
    globalThis.fetch = original;
  }
});
test("service cancellation and timeout reject without fixture fallback", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (_url, init) =>
    new Promise((_resolve, reject) => {
      const signal = init!.signal!;
      if (signal.aborted) reject(signal.reason);
      else
        signal.addEventListener("abort", () => reject(signal.reason), {
          once: true,
        });
    });
  try {
    const controller = new AbortController();
    const request = createEnoughApi(
      "http://backend/api",
      "user",
    ).prepareMission("Dinner $10", controller.signal);
    controller.abort();
    await expect(request).rejects.toMatchObject({ name: "AbortError" });
    await expect(
      createEnoughApi("http://backend/api", "user", 5).prepareMission(
        "Dinner $10",
      ),
    ).rejects.toMatchObject({ name: "TimeoutError" });
    await expect(
      createEnoughApi("http://backend/api", "user").prepareMission(
        "Dinner $10",
        controller.signal,
      ),
    ).rejects.toMatchObject({ name: "AbortError" });
  } finally {
    globalThis.fetch = original;
  }
});

test("nullable budgets remain distinct and Plan.source is authoritative", async () => {
  const p = plan();
  p.budget_cents = null;
  const experience = adaptBackendPlan(
    validatePlan(p),
    "no cap",
    "stale-header",
  );
  expect(experience.mission.budget).toBeNull();
  expect(experience.provenance).toBe("backend-live");
  expect(experience.backendFixture).toBeUndefined();
  expect(render(p)).toContain("No budget stated");
  expect(render(p)).not.toMatch(/NaN|Infinity|role="meter"|under your/);
  expect(
    adaptBackendPlan({ ...p, source: "fixture" }, "different goal").provenance,
  ).toBe("backend-demo");
  expect(render({ ...p, source: "fixture" })).not.toContain(
    "YOUR MISSION, MADE POSSIBLE",
  );
  expect(parseBudgetCents("business casual for my internship")).toBeNull();
  expect(parseBudgetCents("business casual for $150")).toBe(15000);
  expect(parseBudgetCents("business casual for $30")).toBe(3000);
  expect(parseBudgetCents("business casual for $0")).toBe(0);
  for (const source of [undefined, null, "unknown"])
    expect(() => validatePlan({ ...p, source })).toThrow();
  expect(() => validatePlan({ ...p, budget_cents: undefined })).toThrow();
  const original = globalThis.fetch;
  globalThis.fetch = async (_url, init) => {
    expect(JSON.parse(init!.body as string).budget_cents).toBeNull();
    return new Response(JSON.stringify(p));
  };
  try {
    expect(
      (
        await createEnoughApi("http://backend/api", "user").prepareMission(
          "no stated budget",
        )
      ).mission.budget,
    ).toBeNull();
  } finally {
    globalThis.fetch = original;
  }
});

test("budget parser accepts punctuation without truncating malformed amounts", () => {
  for (const [input, cents] of [
    [
      "I need business casual clothes for my internship. My budget is $100.",
      10000,
    ],
    ["My budget is $100, including accessories.", 10000],
    ["Budget: $100!", 10000],
    ["Budget: ($100).", 10000],
    ["Budget: $100.50.", 10050],
    ["Budget: $1,000.50.", 100050],
    ["Budget: $0.", 0],
  ] as const)
    expect(parseBudgetCents(input)).toBe(cents);
  expect(parseBudgetCents("No budget stated.")).toBeNull();
  for (const input of [
    "$100.123",
    "$1,00",
    "$1,000.123",
    "$100,50",
    "$-100",
    "$100 or $200",
  ])
    expect(() => parseBudgetCents(input)).toThrow();
});
