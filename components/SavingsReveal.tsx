"use client";
import { useEffect, useState } from "react";
import { ArrowDown, Check, ArrowUpRight, CircleHelp } from "lucide-react";
import type { Mission, OptimizedPlan } from "@/lib/types";
import { money } from "@/lib/formatting";
function AnimatedAmount({ value }: { value: number }) {
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDisplay(value);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const scale = Number.isInteger(value) ? 1 : 100;
    function tick(now: number) {
      const progress = Math.min((now - start) / 900, 1);
      setDisplay(
        Math.round(value * scale * (1 - Math.pow(1 - progress, 3))) / scale,
      );
      if (progress < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return (
    <>
      <span aria-hidden="true">{money(display)}</span>
      <span className="sr-only">{money(value)}</span>
    </>
  );
}
export function SavingsReveal({
  plan,
  mission,
}: {
  plan: OptimizedPlan;
  mission: Mission;
}) {
  const remaining =
    mission.budget === null
      ? null
      : Math.round((mission.budget - plan.totalCost) * 100) / 100;
  const percentage =
    plan.retailEquivalent > 0
      ? Math.round((plan.savings / plan.retailEquivalent) * 100)
      : null;
  const incomplete = plan.unmetNeedIds.length > 0 || plan.totalNeeds === 0;
  const overBudget = remaining !== null && remaining < 0;
  const usage =
    mission.budget !== null && mission.budget > 0
      ? Math.min((plan.totalCost / mission.budget) * 100, 100)
      : 0;
  return (
    <aside className="savings-panel" aria-label="Your savings">
      <div className="savings-heading">
        <span>THE DIFFERENCE IS THE POINT.</span>
        <ArrowUpRight size={19} />
      </div>
      {incomplete && (
        <p className="partial-cost-note">
          Matched resources only · Unmatched needs are not priced.
        </p>
      )}
      <div className="retail-price">
        <span>
          {incomplete ? "MATCHED ITEMS, BOUGHT NEW" : "BUYING EVERYTHING NEW"}
        </span>
        <del>{money(plan.retailEquivalent)}</del>
      </div>
      <div className="savings-connector">
        <ArrowDown size={21} />
        <span>A little more resourceful.</span>
      </div>
      <div className="enough-price">
        <span>{incomplete ? "WITH CURATE · SO FAR" : "WITH CURATE"}</span>
        <strong>
          <AnimatedAmount value={plan.totalCost} />
        </strong>
        <p>
          {incomplete
            ? "A starting point, with gaps still to resolve."
            : "Your matched resources. Thoughtfully sourced."}
        </p>
      </div>
      <div className="savings-total">
        <div>
          <span>{plan.savings < 0 ? "ABOVE RETAIL" : "YOU SAVE"}</span>
          <strong>
            <AnimatedAmount value={Math.abs(plan.savings)} />
          </strong>
        </div>
        {percentage !== null && (
          <span className="percent-badge">
            {Math.abs(percentage)}% {percentage < 0 ? "more" : "less"}
          </span>
        )}
      </div>
      {remaining !== null && mission.budget !== null ? (
        <div className={`budget-status ${overBudget ? "budget-over" : ""}`}>
          {overBudget || incomplete ? (
            <CircleHelp size={14} />
          ) : (
            <Check size={14} />
          )}
          <span>
            {remaining === 0
              ? `At your ${money(mission.budget)} budget`
              : `${money(Math.abs(remaining))} ${overBudget ? "above" : "under"} your ${money(mission.budget)} budget`}
            {incomplete ? " so far" : ""}
          </span>
        </div>
      ) : (
        <p className="budget-status">No budget stated</p>
      )}
      {mission.budget !== null && mission.budget > 0 && (
        <div
          className="budget-track"
          role="meter"
          aria-label="Budget used"
          aria-valuemin={0}
          aria-valuemax={mission.budget}
          aria-valuenow={Math.min(plan.totalCost, mission.budget)}
          aria-valuetext={`${money(plan.totalCost)} of ${money(mission.budget)}`}
        >
          <span style={{ width: `${usage}%` }} />
        </div>
      )}
      <p className="savings-note">
        {plan.impactAssumptions}
        <br />
        Nothing has been bought or reserved.
      </p>
    </aside>
  );
}
