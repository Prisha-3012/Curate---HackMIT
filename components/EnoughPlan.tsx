import { Check, CircleHelp, ArrowUpRight, Shapes } from "lucide-react";
import type { MissionExperience } from "@/lib/types";
import { money } from "@/lib/formatting";
import { groupNeeds } from "@/lib/plan";
import { OttoAgent } from "./OttoAgent";
import { ResourceCard } from "./ResourceCard";
import { SavingsReveal } from "./SavingsReveal";
export function EnoughPlan({
  experience,
  onRestart,
}: {
  experience: MissionExperience;
  onRestart: () => void;
}) {
  const { mission, plan, copy } = experience;
  const groups = groupNeeds(mission.needs);
  const partial = plan.unmetNeedIds.length > 0;
  const empty = plan.totalNeeds === 0;
  const overBudget = mission.budget !== null && plan.totalCost > mission.budget;
  const backendFixture = experience.provenance === "backend-demo";
  const complete = !partial && !empty && !overBudget;
  const metrics = [
    { value: plan.newPurchasesAvoided, label: "new purchases avoided" },
    {
      value: plan.reusedResources,
      label: plan.reuseLabel ?? "owned, borrowed or shared",
    },
    ...(plan.nearbyResources !== undefined
      ? [{ value: plan.nearbyResources, label: "finds within one mile" }]
      : []),
  ];
  return (
    <section className="plan-screen enter">
      {experience.provenance !== "local-fixture" && (
        <p className="demo-note">{copy.disclosure}</p>
      )}
      <div className="plan-intro">
        <div>
          <span className="eyebrow">
            {complete ? <Check size={13} /> : <CircleHelp size={13} />}{" "}
            {backendFixture
              ? "BACKEND SAMPLE PLAN"
              : complete
                ? "YOUR MISSION, MADE POSSIBLE"
                : overBudget && !partial
                  ? "MATCHED, BUT ABOVE BUDGET"
                  : "A PLAN WITH ROOM TO COMPLETE"}
          </span>
          <h1>
            Here’s your <em>curated</em> plan.
          </h1>
          <p className="lead">
            {backendFixture
              ? `${plan.items.length} of ${plan.totalNeeds} sample needs matched. This fixture does not establish that your goal was solved.`
              : complete
                ? "Everything you need. Less of what you don’t."
                : empty
                  ? "Add needs to start putting your plan together."
                  : !partial && overBudget
                    ? "All needs matched. This combination is above your budget."
                    : `${plan.items.length} of ${plan.totalNeeds} needs matched. Let’s keep the rest in view.`}
          </p>
        </div>
        <div className="plan-mission-stamp">
          {mission.location && <span>{mission.location}</span>}
          <span>
            {mission.duration ? `${mission.duration} · ` : ""}
            {mission.budget === null
              ? "No budget stated"
              : `${money(mission.budget)} budget`}
          </span>
        </div>
      </div>
      <div className="plan-layout">
        <div className="plan-resources">
          <div className="plan-section-heading">
            <span className="eyebrow">{copy.planCollectionLabel}</span>
            <span>
              {plan.items.length} resources · {groups.length}{" "}
              {groups.length === 1 ? "need group" : "need groups"}
            </span>
          </div>
          <div className="need-cards">
            {groups.map((group, index) => (
              <article
                className="need-card enter"
                key={group.id}
                style={{ animationDelay: `${index * 65}ms` }}
              >
                <div className="need-card-heading">
                  <Shapes size={18} strokeWidth={1.5} />
                  <h2>{group.label}</h2>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                </div>
                {group.needs.map((need) => {
                  const item = plan.items.find(
                    (item) => item.needId === need.id,
                  );
                  return item ? (
                    <ResourceCard
                      key={need.id}
                      resource={item.resource}
                      needLabel={need.label}
                      explanation={item.reasoning}
                    />
                  ) : (
                    <div className="unmet-need" key={need.id}>
                      <span className="unmet-label">
                        <CircleHelp size={13} /> STILL NEEDED
                      </span>
                      {group.needs.length > 1 && <h3>{need.label}</h3>}
                      <p>{need.unmetReason}</p>
                      {need.options.length > 0 && (
                        <div>
                          <p>
                            Available candidates · not included in this plan or
                            its totals.
                          </p>
                          {need.options.map((resource) => (
                            <ResourceCard
                              key={resource.id}
                              resource={resource}
                              needLabel={need.label}
                              variant="candidate"
                            />
                          ))}
                        </div>
                      )}
                      {need.rationale && (
                        <p className="unmet-rationale">{need.rationale}</p>
                      )}
                    </div>
                  );
                })}
              </article>
            ))}
          </div>
          <div className="plan-agent-note">
            <OttoAgent state={complete ? "success" : "idle"} compact />
            <p>
              <strong>
                {complete
                  ? "Buy new where it matters. Use what exists for the rest."
                  : overBudget && !partial
                    ? "The resources fit. The budget still needs work."
                    : "A useful start. The unmatched needs still matter."}
              </strong>
              <br />
              {copy.planNote}
            </p>
          </div>
        </div>
        <SavingsReveal plan={plan} mission={mission} />
      </div>
      <div
        className="impact-strip"
        style={{ gridTemplateColumns: `1.1fr repeat(${metrics.length}, 1fr)` }}
      >
        <span className="impact-label">
          LESS BUYING.
          <br />
          <em>MORE POSSIBILITY.</em>
        </span>
        {metrics.map((metric) => (
          <div className="impact-metric" key={metric.label}>
            <strong>{metric.value}</strong>
            <span>{metric.label}</span>
          </div>
        ))}
      </div>
      <div className="plan-end">
        <p>
          <span className="completion-dot" />
          {complete
            ? copy.completion
            : empty
              ? "Your next mission starts with a need."
              : !partial && overBudget
                ? "Matched resources. Budget still to resolve."
                : `${plan.unmetNeedIds.length} ${plan.unmetNeedIds.length === 1 ? "need still needs" : "needs still need"} a match.`}
        </p>
        <button className="text-button" onClick={onRestart}>
          Try the mission again <ArrowUpRight size={14} />
        </button>
      </div>
    </section>
  );
}
