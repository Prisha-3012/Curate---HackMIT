/**
 * The backend contract, verbatim.
 *
 * Mirrors apps/api/models/schemas.py on the `backend` branch, which mirrors
 * ARCHITECTURE.md §4. snake_case because that is what crosses the wire — do not
 * rename fields here. Map into UI types at the service boundary instead
 * (see lib/services/enoughApi.ts).
 *
 * Keep synchronized with the backend schema; validate wire data before mapping.
 */

/** The ladder, in the order the resolver walks it. Exactly four rungs. */
export type Rung = "OWN" | "BORROW" | "USED" | "NEW";

/** One way to satisfy a need, on one rung. */
export interface PlanOption {
  listing_id: string;
  rung: Rung;
  title: string;
  /** "you", a friend's display name, or a retailer/marketplace label. */
  owner_label: string;
  /** Cents. 0 for OWN and BORROW. */
  price_cents: number;
  /** Cents. What it costs new — the savings baseline. */
  retail_cents: number;
  image_url?: string | null;
  /** 0..1. */
  match_score: number;
  /** One sentence, shown verbatim next to the price. */
  why: string;
  /** True only for top/bottom on the USED and NEW rungs. */
  needs_fitcheck: boolean;
}

/**
 * One need decomposed out of the goal.
 *
 * THREE STATES, not two:
 *   met              -> recommended_listing_id != null, unmet_reason == null
 *   unmet, nothing   -> recommended_listing_id == null, options == [],  unmet_reason set
 *   unmet, unafford. -> recommended_listing_id == null, options != [],  unmet_reason set
 *
 * Branch on `unmet_reason`, never on `options.length`. The third state carries
 * real options that the user should still see — "three exist, none affordable"
 * is different information from "nothing matched".
 *
 * Note: `category` and `attrs` exist on the server but are deliberately NOT
 * serialized (§4). Do not expect them.
 */
export interface PlanNeed {
  need_id: string;
  label: string;
  /** Why this need exists. Shown in the UI. */
  rationale: string;
  /** 1 = essential, 2 = nice-to-have. */
  priority: 1 | 2;
  options: PlanOption[];
  /** Null when unmet. Always null-check before options.find(...). */
  recommended_listing_id: string | null;
  /** Set exactly when recommended_listing_id is null. */
  unmet_reason: string | null;
}

export interface PlanImpact {
  /** Cents. Sum of the RECOMMENDED options' retail_cents. Met needs only. */
  baseline_cents: number;
  /** Cents. Cost of the recommended options. Met needs only. */
  plan_cents: number;
  saved_cents: number;
  items_reused: number;
  /** 0.0 for non-textile categories. Never inflated to look better. */
  textile_kg_avoided: number;
  assumptions_note: string;
}

/** POST /api/mission and GET /api/mission/{id} both return this. */
export interface Plan {
  mission_id: string;
  goal_text: string;
  budget_cents: number;
  needs: PlanNeed[];
  impact: PlanImpact;
}

export interface MissionRequest {
  user_id: string;
  goal_text: string;
  budget_cents: number;
}

/** True when the need is unmet for any reason. */
export function isUnmet(need: PlanNeed): boolean {
  return need.recommended_listing_id === null;
}

/** True when options exist but none are affordable — the budget-dropped case. */
export function isUnaffordable(need: PlanNeed): boolean {
  return isUnmet(need) && need.options.length > 0;
}

/** The recommended option for a need, or null when unmet. */
export function recommendedOption(need: PlanNeed): PlanOption | null {
  if (need.recommended_listing_id === null) return null;
  return (
    need.options.find((o) => o.listing_id === need.recommended_listing_id) ??
    null
  );
}
