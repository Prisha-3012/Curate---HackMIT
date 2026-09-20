import type { Plan } from "./plan";

/** Reject malformed wire data before it reaches rendering or money arithmetic. */
export function validatePlan(value: unknown): Plan {
  function fail(): never {
    throw new Error("The backend returned an invalid plan.");
  }
  function object(v: unknown): Record<string, unknown> {
    if (!v || typeof v !== "object" || Array.isArray(v)) fail();
    return v as Record<string, unknown>;
  }
  function string(v: unknown) {
    if (typeof v !== "string") fail();
  }
  function cents(v: unknown, signed = false) {
    if (typeof v !== "number" || !Number.isSafeInteger(v) || (!signed && v < 0))
      fail();
  }
  const p = object(value);
  string(p.mission_id);
  string(p.goal_text);
  if (p.budget_cents !== null) cents(p.budget_cents);
  if (p.source !== "live" && p.source !== "fixture") fail();
  if (!Array.isArray(p.needs)) fail();
  const needIds = new Set();
  for (const raw of p.needs) {
    const n = object(raw);
    string(n.need_id);
    string(n.label);
    string(n.rationale);
    if (needIds.has(n.need_id)) fail();
    needIds.add(n.need_id);
    if (n.priority !== 1 && n.priority !== 2) fail();
    if (!Array.isArray(n.options)) fail();
    const optionIds = new Set();
    for (const rawOption of n.options) {
      const o = object(rawOption);
      for (const key of ["listing_id", "title", "owner_label", "why"])
        string(o[key]);
      if (optionIds.has(o.listing_id)) fail();
      optionIds.add(o.listing_id);
      if (!["OWN", "BORROW", "USED", "NEW"].includes(o.rung as string)) fail();
      cents(o.price_cents);
      cents(o.retail_cents);
      if (o.image_url != null) string(o.image_url);
      if (o.product_url != null) string(o.product_url);
      if (
        typeof o.match_score !== "number" ||
        !Number.isFinite(o.match_score) ||
        o.match_score < 0 ||
        o.match_score > 1
      )
        fail();
      if (typeof o.needs_fitcheck !== "boolean") fail();
    }
    if (n.recommended_listing_id == null) {
      if (typeof n.unmet_reason !== "string" || !n.unmet_reason.trim()) fail();
    } else {
      string(n.recommended_listing_id);
      if (!optionIds.has(n.recommended_listing_id) || n.unmet_reason) fail();
    }
    if (n.unmet_reason != null) string(n.unmet_reason);
  }
  const impact = object(p.impact);
  for (const key of ["baseline_cents", "plan_cents", "items_reused"])
    cents(impact[key]);
  cents(impact.saved_cents, true);
  if (
    typeof impact.textile_kg_avoided !== "number" ||
    !Number.isFinite(impact.textile_kg_avoided) ||
    impact.textile_kg_avoided < 0
  )
    fail();
  string(impact.assumptions_note);
  // Pydantic allows omitted nullable fields and fills these defaults.
  return {
    ...p,
    needs: p.needs.map((raw) => {
      const n = object(raw);
      return {
        ...n,
        recommended_listing_id: n.recommended_listing_id ?? null,
        unmet_reason: n.unmet_reason ?? null,
      };
    }),
  } as Plan;
}
