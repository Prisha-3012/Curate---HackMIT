import type { Plan, Rung } from "./plan";
import type {
  ExperienceCopy,
  MissionExperience,
  ResourceSource,
  SearchSource,
} from "../types";

const sourceByRung: Record<Rung, ResourceSource> = {
  OWN: "owned",
  BORROW: "borrow",
  USED: "used",
  NEW: "new",
};
const activeRungs: Rung[] = ["OWN", "USED", "NEW"];

export const backendSources: SearchSource[] = activeRungs.map((rung) => ({
  id: rung,
  label: rung,
  sources: [sourceByRung[rung]],
  subtitle: `Reviewing returned ${rung.toLowerCase()} options`,
}));
export const backendCopy: ExperienceCopy = {
  exampleLabel: "A goal to get started",
  placeholder: "Describe your goal. Add a dollar budget if you have one…",
  // Empty: the live path is the demo, and users do not need our internals.
  // The one disclosure that survives is the backend-fixture case below, which
  // exists to stop seeded needs being read as an answer to the user's goal.
  disclosure: "",
  summary: "Here is what your goal breaks down into.",
  planCollectionLabel: "RESOURCES FOR YOUR GOAL",
  planNote: "",
  completion: "Your returned plan, ready to review.",
  optimizationCriteria: "",
};
const dollars = (cents: number) => cents / 100;

/** Pure mapping of validated DTOs. Backend impact is authoritative, never recalculated. */
export function adaptBackendPlan(
  plan: Plan,
  rawInput: string,
  backendFixture?: string,
): MissionExperience {
  const needs = plan.needs.map((need) => ({
    id: need.need_id,
    label: need.label,
    rationale: need.rationale,
    priority:
      need.priority === 1 ? ("required" as const) : ("preferred" as const),
    recommendedOptionId: need.recommended_listing_id,
    unmetReason: need.unmet_reason ?? undefined,
    options: need.options.map((option) => ({
      id: option.listing_id,
      name: option.title,
      source: sourceByRung[option.rung],
      rung: option.rung,
      price: dollars(option.price_cents),
      retailPrice: dollars(option.retail_cents),
      ownerName: option.owner_label,
      image: option.image_url ?? undefined,
      productUrl: option.product_url ?? undefined,
      matchScore: option.match_score,
      description: option.why,
      needsFitcheck: option.needs_fitcheck,
    })),
  }));
  const items = needs.flatMap((need) => {
    const resource = need.options.find(
      (option) => option.id === need.recommendedOptionId,
    );
    return resource
      ? [{ needId: need.id, resource, reasoning: resource.description }]
      : [];
  });
  const isFixture = plan.source === "fixture";
  const disclosure = isFixture
    ? `Backend fixture/demo data${backendFixture ? ` (${backendFixture})` : ""} — seeded sample needs, not a result for your goal.`
    : "";
  return {
    mission: {
      id: plan.mission_id,
      rawInput,
      title: plan.goal_text,
      budget: plan.budget_cents === null ? null : dollars(plan.budget_cents),
      needs,
    },
    sources: backendSources.map((source) => ({
      ...source,
      sources: [...source.sources],
    })),
    copy: {
      ...backendCopy,
      disclosure,
      ...(isFixture
        ? {
            summary:
              "The backend returned seeded sample needs. Review this as fixture data, not a generated answer to your goal.",
            planNote:
              "This is a backend sample plan. It does not establish that your requested goal was solved.",
            completion: "Backend sample plan, ready to review.",
          }
        : {}),
    },
    plan: {
      items,
      totalCost: dollars(plan.impact.plan_cents),
      retailEquivalent: dollars(plan.impact.baseline_cents),
      savings: dollars(plan.impact.saved_cents),
      newPurchasesAvoided: items.filter(
        (item) => item.resource.source !== "new",
      ).length,
      reusedResources: plan.impact.items_reused,
      reuseLabel: "resources reused, including used",
      textileKgAvoided: plan.impact.textile_kg_avoided,
      impactAssumptions: plan.impact.assumptions_note,
      unmetNeedIds: needs
        .filter((need) => need.recommendedOptionId === null)
        .map((need) => need.id),
      totalNeeds: needs.length,
    },
    provenance: isFixture ? "backend-demo" : "backend-live",
    ...(isFixture && backendFixture ? { backendFixture } : {}),
  };
}
