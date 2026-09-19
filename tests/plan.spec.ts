import { expect, test } from "@playwright/test";
import { createElement } from "react";
import { createRequire } from "node:module";
import * as reactJsxRuntime from "react/jsx-runtime";
import { renderToStaticMarkup } from "react-dom/server";
import { bostonFixture } from "../lib/fixtures/boston";
import { campingFixture } from "../lib/fixtures/camping";
import {
  calculatePlan,
  comparisonNeed,
  groupNeeds,
  prepareFixture,
} from "../lib/plan";
import { money } from "../lib/formatting";
import { SavingsReveal } from "../components/SavingsReveal";
import { EnoughPlan } from "../components/EnoughPlan";
import { OptimizationView } from "../components/OptimizationView";

// Playwright 1.63 compiles imported TSX against its JSX descriptor runtime.
// These Node-side SSR assertions need React elements instead of browser-mount
// descriptors. Configure the worker's runtime only; application code is untouched.
const requireForTests = createRequire(`${process.cwd()}/package.json`);
Object.assign(requireForTests("playwright/jsx-runtime"), reactJsxRuntime);

test("Boston accounting and six display groups survive dynamic individual needs", () => {
  const experience = prepareFixture(bostonFixture);
  expect(experience.plan).toMatchObject({
    totalCost: 314,
    retailEquivalent: 731,
    savings: 417,
    newPurchasesAvoided: 7,
    reusedResources: 4,
    nearbyResources: 3,
    unmetNeedIds: [],
    totalNeeds: 8,
  });
  expect(groupNeeds(experience.mission.needs)).toHaveLength(6);
  const changed = structuredClone(bostonFixture);
  const option = changed.mission.needs
    .flatMap((need) => need.options)
    .find((resource) => resource.id === "desk")!;
  option.price += 12;
  expect(prepareFixture(changed).plan).toMatchObject({
    totalCost: 326,
    savings: 405,
  });
  expect(
    bostonFixture.mission.needs
      .flatMap((need) => need.options)
      .find((resource) => resource.id === "desk")?.price,
  ).toBe(35);
});

test("camping retains lower-scoring recommendation, metadata, unknowns, and unmet need", () => {
  const experience = prepareFixture(campingFixture);
  const need = comparisonNeed(experience)!;
  expect(need.options.map((option) => option.source)).toEqual([
    "borrow",
    "used",
    "new",
  ]);
  expect(need.recommendedOptionId).toBe("borrowed-tent");
  expect(need.options[0].matchScore).toBeLessThan(need.options[2].matchScore!);
  expect(experience.plan).toMatchObject({
    totalCost: 18.5,
    retailEquivalent: 229.8,
    savings: 211.3,
    unmetNeedIds: ["navigation"],
    totalNeeds: 4,
  });
  expect(experience.plan.nearbyResources).toBeUndefined();
  expect(experience.mission.location).toBeUndefined();
  expect(experience.mission.duration).toBeUndefined();
  expect(
    experience.plan.items.find((item) => item.needId === "warm-layer")?.resource
      .needsFitcheck,
  ).toBe(true);
  expect(
    experience.plan.items.find((item) => item.needId === "light")?.resource
      .image,
  ).toBeTruthy();
});

test("explicit selection is preserved without repeating the recommendation's explanation", () => {
  const fixture = structuredClone(campingFixture);
  fixture.mission.needs[0].selectedOptionId = "new-tent";
  const plan = prepareFixture(fixture).plan;
  expect(plan.items[0].resource.id).toBe("new-tent");
  expect(plan.items[0].reasoning).toBe(
    fixture.mission.needs[0].options[2].description,
  );
  expect(plan.totalCost).toBe(148.4);
  const markup = renderToStaticMarkup(
    createElement(OptimizationView, {
      need: fixture.mission.needs[0],
      candidateCount: 3,
    }),
  );
  expect(markup).toContain('data-selected="true"');
  expect(markup).toContain('data-recommended="true"');
  expect(markup).toContain("SELECTED");
  expect(markup).not.toContain("Borrowing wins before buying");
});

test("all-unmet, empty and zero-budget plans render honestly without invalid math", () => {
  const fixture = structuredClone(campingFixture);
  fixture.mission.budget = 0;
  fixture.mission.needs = fixture.mission.needs.map((need) => ({
    ...need,
    options: [],
    recommendedOptionId: null,
    unmetReason: "No suitable resource in this example.",
  }));
  const experience = prepareFixture(fixture);
  const markup = renderToStaticMarkup(
    createElement(EnoughPlan, { experience, onRestart: () => {} }),
  );
  expect(markup).toContain("0 of 4 needs matched");
  expect(markup.match(/STILL NEEDED/g)).toHaveLength(4);
  expect(markup).not.toMatch(
    /NaN|Infinity|Everything you need|YOUR MISSION, MADE POSSIBLE/,
  );
  expect(markup).not.toContain('role="meter"');
  expect(markup).not.toContain("otto-thinking");
  const empty = {
    ...experience,
    mission: { ...experience.mission, needs: [] },
    plan: calculatePlan([], "No priced resources."),
  };
  expect(
    renderToStaticMarkup(
      createElement(EnoughPlan, { experience: empty, onRestart: () => {} }),
    ),
  ).toContain("Add needs to start");
});

test("currency, negative savings, and over-budget states retain precision", () => {
  expect(money(39.9)).toBe("$39.90");
  expect(money(314)).toBe("$314");
  const fixture = structuredClone(campingFixture);
  const option = fixture.mission.needs[0].options[0];
  option.price = 400;
  const experience = prepareFixture(fixture);
  const markup = renderToStaticMarkup(
    createElement(SavingsReveal, {
      mission: experience.mission,
      plan: experience.plan,
    }),
  );
  expect(markup).toContain("ABOVE RETAIL");
  expect(markup).toContain("above your $60 budget");
  expect(markup).not.toMatch(/NaN|Infinity/);
});

test("invalid recommendations fail explicitly instead of silently dropping needs", () => {
  const fixture = structuredClone(campingFixture);
  fixture.mission.needs[0].recommendedOptionId = "does-not-exist";
  expect(() => prepareFixture(fixture)).toThrow(
    "Recommendation does not belong",
  );
});
