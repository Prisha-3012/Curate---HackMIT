"use client";
import { useEffect, useState } from "react";
import { ArrowDown, Check, ArrowUpRight } from "lucide-react";
import type { Mission, OptimizedPlan } from "@/lib/types";
import { money } from "@/lib/demo-data";
function AnimatedAmount({ value }: { value: number }) {
  const [display, setDisplay] = useState(value);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const start = performance.now();
    function tick(now: number) {
      const progress = Math.min((now - start) / 900, 1);
      setDisplay(Math.round(value * (1 - Math.pow(1 - progress, 3))));
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
  const remaining = mission.budget - plan.totalCost;
  const percent = Math.round((plan.savings / plan.retailEquivalent) * 100);
  return (
    <aside className="savings-panel" aria-label="Your savings">
      <div className="savings-heading">
        <span>THE DIFFERENCE IS ENOUGH.</span>
        <ArrowUpRight size={19} />
      </div>
      <div className="retail-price">
        <span>BUYING EVERYTHING NEW</span>
        <del>{money(plan.retailEquivalent)}</del>
      </div>
      <div className="savings-connector">
        <ArrowDown size={21} />
        <span>A little more resourceful.</span>
      </div>
      <div className="enough-price">
        <span>WITH ENOUGH</span>
        <strong>
          <AnimatedAmount value={plan.totalCost} />
        </strong>
        <p>Everything you need. Thoughtfully sourced.</p>
      </div>
      <div className="savings-total">
        <div>
          <span>YOU SAVE</span>
          <strong>
            <AnimatedAmount value={plan.savings} />
          </strong>
        </div>
        <span className="percent-badge">{percent}% less</span>
      </div>
      <div className="budget-status">
        <Check size={14} />
        <span>
          {remaining >= 0
            ? `${money(remaining)} under your ${money(mission.budget)} budget`
            : `${money(-remaining)} above your ${money(mission.budget)} budget`}
        </span>
      </div>
      <div
        className="budget-track"
        role="meter"
        aria-label="Budget used"
        aria-valuemin={0}
        aria-valuemax={mission.budget}
        aria-valuenow={Math.min(plan.totalCost, mission.budget)}
        aria-valuetext={`${money(plan.totalCost)} of ${money(mission.budget)}`}
      >
        <span
          style={{
            width: `${Math.min((plan.totalCost / mission.budget) * 100, 100)}%`,
          }}
        />
      </div>
      <p className="savings-note">
        Demo estimates · Before taxes, delivery, or fees.
        <br />
        Nothing has been bought or reserved.
      </p>
    </aside>
  );
}
