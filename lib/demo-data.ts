import type { Mission, Resource, SearchSource, OptimizedPlan } from "./types";
export const DEMO_MODE = true;
export const TIMING = {
  understand: 900,
  search: 1000,
  source: 850,
  optimize: 1400,
};
export const DEMO_INPUT =
  "I’m moving to Boston for a 3-month internship. I have $500 and basically nothing. Help me set up my room.";
export const demoMission: Mission = {
  rawInput: DEMO_INPUT,
  title: "A room for your next chapter.",
  budget: 500,
  duration: "3 months",
  location: "Boston, MA",
  needs: ["Sleep", "Study", "Lighting", "Cooking", "Cleaning", "Storage"].map(
    (label) => ({
      id: label.toLowerCase(),
      category: label,
      label,
      priority: "required",
    }),
  ),
  preferences: ["Affordable", "Nearby", "Temporary", "Easy to resell"].map(
    (label) => ({
      id: label.toLowerCase().replaceAll(" ", "-"),
      label,
      weight: 1,
    }),
  ),
};
export const resources: Resource[] = [
  {
    id: "mattress",
    name: "Mattress",
    category: "sleep",
    source: "new",
    price: 189,
    retailPrice: 189,
    description: "A fresh start, where it matters.",
  },
  {
    id: "frame",
    name: "Bed frame",
    category: "sleep",
    source: "used",
    price: 45,
    retailPrice: 129,
    distanceMiles: 0.8,
    description: "Solid wood. Ready for another chapter.",
  },
  {
    id: "desk",
    name: "Writing desk",
    category: "study",
    source: "used",
    price: 35,
    retailPrice: 99,
    distanceMiles: 0.6,
    description: "Just the right size for a summer of good work.",
  },
  {
    id: "chair",
    name: "Desk chair",
    category: "study",
    source: "borrow",
    price: 0,
    retailPrice: 79,
    ownerName: "Alex",
    description: "Alex has a spare. Borrow it for the summer.",
  },
  {
    id: "lamp",
    name: "Desk lamp",
    category: "lighting",
    source: "owned",
    price: 0,
    retailPrice: 25,
    description: "Your trusty lamp already does the job.",
  },
  {
    id: "cookware",
    name: "Cookware",
    category: "cooking",
    source: "borrow",
    price: 0,
    retailPrice: 65,
    ownerName: "Roommate",
    description: "Your roommate’s kitchen has you covered.",
  },
  {
    id: "vacuum",
    name: "Vacuum",
    category: "cleaning",
    source: "share",
    price: 18,
    retailPrice: 90,
    ownerName: "Roommates",
    description: "Split the cost. Share the clean floors.",
  },
  {
    id: "storage",
    name: "Storage shelves",
    category: "storage",
    source: "used",
    price: 27,
    retailPrice: 55,
    distanceMiles: 0.4,
    description: "A little more room for everything you bring.",
  },
  {
    id: "rental-desk",
    name: "Rental desk",
    category: "study",
    source: "rent",
    price: 72,
    retailPrice: 99,
    description: "$24/month × 3 months.",
  },
  {
    id: "new-desk",
    name: "New desk",
    category: "study",
    source: "new",
    price: 89,
    retailPrice: 89,
    description: "Delivered new, with assembly required.",
  },
  {
    id: "friend-desk",
    name: "Friend’s desk",
    category: "study",
    source: "borrow",
    price: 0,
    retailPrice: 99,
    distanceMiles: 4.8,
    description: "Free to borrow, but a longer trip across town.",
  },
];
export const selectedIds = [
  "mattress",
  "frame",
  "desk",
  "chair",
  "lamp",
  "cookware",
  "vacuum",
  "storage",
];
export const searchSources: SearchSource[] = [
  {
    id: "own",
    label: "OWN",
    subtitle: "Start with what’s yours.",
    sources: ["owned"],
    checked: 4,
  },
  {
    id: "circle",
    label: "CIRCLE",
    subtitle: "Good things are closer than you think.",
    sources: ["borrow", "share"],
    checked: 8,
  },
  {
    id: "used",
    label: "USED",
    subtitle: "A second life. A short walk away.",
    sources: ["used"],
    checked: 18,
  },
  {
    id: "rent",
    label: "RENT",
    subtitle: "Only for as long as you need it.",
    sources: ["rent"],
    checked: 5,
  },
  {
    id: "new",
    label: "NEW",
    subtitle: "For what still needs a fresh start.",
    sources: ["new"],
    checked: 12,
  },
];
export function calculatePlan(candidates: Resource[]): OptimizedPlan {
  const items = candidates
    .filter((r) => selectedIds.includes(r.id))
    .map((resource) => ({
      needId: resource.category,
      resource,
      reasoning: resource.description,
    }));
  const totalCost = items.reduce(
    (sum, { resource }) => sum + resource.price,
    0,
  );
  const retailEquivalent = items.reduce(
    (sum, { resource }) => sum + resource.retailPrice,
    0,
  );
  return {
    items,
    totalCost,
    retailEquivalent,
    savings: retailEquivalent - totalCost,
    newPurchasesAvoided: items.filter((i) => i.resource.source !== "new")
      .length,
    reusedResources: items.filter((i) =>
      ["owned", "borrow", "share"].includes(i.resource.source),
    ).length,
    nearbyResources: items.filter(
      (i) =>
        i.resource.distanceMiles !== undefined && i.resource.distanceMiles <= 1,
    ).length,
  };
}
export const money = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
