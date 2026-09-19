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
export const backendSources: SearchSource[] = Object.entries(sourceByRung).map(
  ([rung, source]) => ({
    id: rung,
    label: rung,
    sources: [source],
    subtitle: `Reviewing returned ${rung.toLowerCase()} options`,
  }),
);
export const backendCopy: ExperienceCopy = {
  exampleLabel: "A goal with an explicit budget",
  placeholder: "Describe your goal and include your budget, for example $100…",
  disclosure:
    "One plan request. The following stages reveal the returned plan.",
  summary: "Review the needs returned for your goal.",
  planCollectionLabel: "RESOURCES FOR YOUR GOAL",
  planNote: "Recommendations and impact estimates are supplied by the backend.",
  completion: "Your returned plan, ready to review.",
  optimizationCriteria:
    "Provider order is preserved. A higher match score does not override the resource ladder.",
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
  const disclosure = backendFixture
    ? `Backend demo fixture: ${backendFixture}. This is a staged reveal of fixture data.`
    : "Backend response · origin unverified. The backend may substitute a demo fixture without identifying it. These stages reveal the returned plan.";
  return {
    mission: {
      id: plan.mission_id,
      rawInput,
      title: plan.goal_text,
      budget: dollars(plan.budget_cents),
      needs,
    },
    sources: backendSources.map((source) => ({
      ...source,
      sources: [...source.sources],
    })),
    copy: { ...backendCopy, disclosure },
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
    provenance: backendFixture ? "backend-demo" : "backend-unverified",
    ...(backendFixture ? { backendFixture } : {}),
  };
}
