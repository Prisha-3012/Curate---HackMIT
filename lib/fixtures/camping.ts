import type { DemoFixture } from "../types";
/** Hand-authored UI development fixture. No agent, search, or backend generated it. */
export const campingFixture: DemoFixture = {
  id: "camping",
  label: "Camping · UI test fixture",
  badge: "LOCAL UI TEST · CAMPING",
  mission: {
    id: "local-camping",
    rawInput:
      "Help me prepare for my first camping trip with a $60 budget. Use what I can borrow before buying anything.",
    title: "A weekend outside, thoughtfully packed.",
    budget: 60,
    needs: [
      {
        id: "shelter",
        label: "A dry place to settle in",
        priority: "required",
        rationale: "Reliable shelter is the first essential.",
        options: [
          {
            id: "borrowed-tent",
            name: "Two-person canvas tent",
            source: "borrow",
            rung: "BORROW",
            price: 0,
            retailPrice: 120,
            ownerName: "Lina",
            matchScore: 0.83,
            visual: "shelter",
            description: "Lina’s weatherproof tent is available to borrow.",
          },
          {
            id: "used-tent",
            name: "Pre-loved trail tent",
            source: "used",
            rung: "USED",
            price: 45,
            retailPrice: 120,
            matchScore: 0.86,
            visual: "shelter",
            description: "A slightly closer match, with an extra purchase.",
          },
          {
            id: "new-tent",
            name: "New lightweight tent",
            source: "new",
            rung: "NEW",
            price: 129.9,
            retailPrice: 129.9,
            matchScore: 0.91,
            visual: "shelter",
            description:
              "The highest match score, but buying new isn’t necessary.",
          },
        ],
        recommendedOptionId: "borrowed-tent",
        recommendationReason:
          "Lina’s tent already meets your shelter needs. Borrowing wins before buying, even though the new tent has a higher match score.",
      },
      {
        id: "light",
        label: "Light after sunset",
        priority: "required",
        rationale: "A familiar light for finding your way around camp.",
        options: [
          {
            id: "camp-lantern",
            name: "Rechargeable lantern",
            source: "owned",
            rung: "OWN",
            price: 0,
            retailPrice: 39.9,
            matchScore: 0.94,
            image: "/fixtures/camping-lantern.svg",
            imageAlt: "Illustrated moss-green rechargeable camping lantern",
            visual: "beam",
            description: "Already in your kit. Charge it before you go.",
          },
        ],
        recommendedOptionId: "camp-lantern",
      },
      {
        id: "warm-layer",
        label: "A layer for cooler evenings",
        priority: "required",
        rationale: "Keep a warm layer handy when the temperature drops.",
        options: [
          {
            id: "used-fleece",
            name: "Pre-loved fleece pullover",
            source: "used",
            rung: "USED",
            price: 18.5,
            retailPrice: 69.9,
            matchScore: 0.88,
            needsFitcheck: true,
            visual: "fold",
            description: "A warm extra layer. Sizing still needs checking.",
          },
          {
            id: "new-fleece",
            name: "New fleece pullover",
            source: "new",
            rung: "NEW",
            price: 69.9,
            retailPrice: 69.9,
            matchScore: 0.9,
            needsFitcheck: true,
            visual: "fold",
            description: "Another option if the pre-loved layer doesn’t fit.",
          },
        ],
        recommendedOptionId: "used-fleece",
      },
      {
        id: "navigation",
        label: "An offline navigation kit",
        priority: "required",
        rationale: "Know your route when your phone has no signal.",
        options: [],
        recommendedOptionId: null,
        unmetReason:
          "No suitable map and compass in this sample resource pool. This need still needs a match before you head out.",
      },
    ],
  },
  sources: [
    {
      id: "own",
      label: "OWN",
      subtitle: "Start with what’s already yours.",
      sources: ["owned"],
    },
    {
      id: "borrow",
      label: "BORROW",
      subtitle: "A good resource can be shared.",
      sources: ["borrow"],
    },
    {
      id: "used",
      label: "USED",
      subtitle: "Useful things, ready for another chapter.",
      sources: ["used"],
    },
    {
      id: "new",
      label: "NEW",
      subtitle: "Only when the earlier options fall short.",
      sources: ["new"],
    },
  ],
  copy: {
    exampleLabel: "Prepare for camping under $60",
    placeholder:
      "I’m heading outdoors. Help me get ready with what already exists…",
    disclosure:
      "LOCAL UI TEST FIXTURE · Hand-authored camping example · Not AI-generated",
    summary: "A few good resources. A little more time outside.",
    planCollectionLabel: "A LITTLE MORE READY FOR THE OUTDOORS",
    planNote:
      "Borrow shelter, use your own light, and give a warm layer another outing.",
    completion: "Your essentials, thoughtfully gathered.",
    optimizationCriteria: "Source priority + suitability + cost",
  },
  optimizationNeedId: "shelter",
  impactAssumptions:
    "Hand-authored UI test estimates. Totals cover matched resources only; the navigation kit is not priced. Taxes, delivery, and fees are excluded.",
};
