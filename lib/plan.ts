import type {
  DemoFixture,
  MissionExperience,
  Need,
  OptimizedPlan,
  Resource,
} from "./types";

export function selectedOption(need: Need): Resource | undefined {
  const id = need.selectedOptionId ?? need.recommendedOptionId;
  return id === null
    ? undefined
    : need.options.find((option) => option.id === id);
}
export function groupNeeds(
  needs: Need[],
): { id: string; label: string; needs: Need[] }[] {
  const groups = new Map<
    string,
    { id: string; label: string; needs: Need[] }
  >();
  for (const need of needs) {
    const key = need.group ? `group:${need.group.id}` : `need:${need.id}`;
    const group = groups.get(key) ?? {
      id: key,
      label: need.group?.label ?? need.label,
      needs: [],
    };
    group.needs.push(need);
    groups.set(key, group);
  }
  return [...groups.values()];
}
export function candidateResources(needs: Need[]): Resource[] {
  const resources = new Map<string, Resource>();
  for (const need of needs)
    for (const option of need.options) {
      if (!resources.has(option.id)) resources.set(option.id, option);
    }
  return [...resources.values()];
}
/** Local fixture accounting only. A future adapter must preserve backend impact semantics. */
export function calculatePlan(
  needs: Need[],
  impactAssumptions: string,
): OptimizedPlan {
  const items = needs.flatMap((need) => {
    if (
      need.recommendedOptionId !== null &&
      !need.options.some((o) => o.id === need.recommendedOptionId)
    ) {
      throw new Error(`Recommendation does not belong to need ${need.id}`);
    }
    const resource = selectedOption(need);
    if (!resource) {
      if (need.options.length || !need.unmetReason)
        throw new Error(
          `Need ${need.id} requires a selection or an unmet reason`,
        );
      return [];
    }
    return [
      {
        needId: need.id,
        resource,
        reasoning:
          resource.id === need.recommendedOptionId
            ? (need.recommendationReason ?? resource.description)
            : resource.description,
      },
    ];
  });
  const totalCents = items.reduce(
    (sum, item) => sum + Math.round(item.resource.price * 100),
    0,
  );
  const retailCents = items.reduce(
    (sum, item) => sum + Math.round(item.resource.retailPrice * 100),
    0,
  );
  const knownDistances = items.filter(
    (item) => item.resource.distanceMiles !== undefined,
  );
  return {
    items,
    totalCost: totalCents / 100,
    retailEquivalent: retailCents / 100,
    savings: (retailCents - totalCents) / 100,
    newPurchasesAvoided: items.filter((item) => item.resource.source !== "new")
      .length,
    reusedResources: items.filter((item) =>
      ["owned", "borrow", "share"].includes(item.resource.source),
    ).length,
    nearbyResources: knownDistances.length
      ? knownDistances.filter((item) => item.resource.distanceMiles! <= 1)
          .length
      : undefined,
    unmetNeedIds: needs
      .filter((need) => !selectedOption(need))
      .map((need) => need.id),
    totalNeeds: needs.length,
    impactAssumptions,
  };
}
export function prepareFixture(
  fixture: DemoFixture,
  input = fixture.mission.rawInput,
): MissionExperience {
  const copy = structuredClone(fixture);
  copy.mission.rawInput = input;
  return {
    mission: copy.mission,
    sources: copy.sources,
    copy: copy.copy,
    plan: calculatePlan(copy.mission.needs, copy.impactAssumptions),
    optimizationNeedId: copy.optimizationNeedId,
    provenance: "local-fixture",
  };
}
export function comparisonNeed(
  experience: MissionExperience,
): Need | undefined {
  const needs = experience.mission.needs;
  return (
    needs.find((need) => need.id === experience.optimizationNeedId) ??
    needs.find((need) => need.options.length > 1) ??
    needs.find((need) => need.options.length > 0) ??
    needs[0]
  );
}
