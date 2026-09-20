import { ArrowDown, CircleHelp } from "lucide-react";
import type { Need } from "@/lib/types";
import { selectedOption } from "@/lib/plan";
import { OttoAgent } from "./OttoAgent";
import { ResourceCard } from "./ResourceCard";
import { Reveal } from "./Reveal";
export function OptimizationView({
  need,
  candidateCount,
  criteria,
}: {
  need?: Need;
  candidateCount: number;
  criteria?: string;
}) {
  const chosen = need && selectedOption(need);
  return (
    <section className="optimization-screen">
      <div className="optimization-intro">
        <Reveal>
          <OttoAgent state="optimizing" />
          <span className="eyebrow">03 / MAKING THE PIECES FIT</span>
          <h1>
            Finding the best
            <br />
            <em>combination.</em>
          </h1>
          <p className="lead">
            {candidateCount}{" "}
            {candidateCount === 1 ? "possibility" : "possibilities"}. Each need
            deserves a thoughtful match.
          </p>
        </Reveal>
      </div>
      <div className="optimization-example">
        {need && (
          <div className="optimization-label">
            <span className="eyebrow">A CLOSER LOOK: {need.label}</span>
            {criteria && <span>{criteria}</span>}
          </div>
        )}
        {need?.options.length ? (
          <>
            <div className="candidate-grid">
              <Reveal>
                {need.options.map((resource) => (
                  <ResourceCard
                    key={resource.id}
                    resource={resource}
                    needLabel={need.label}
                    variant="candidate"
                    recommended={need.recommendedOptionId === resource.id}
                    selected={need.selectedOptionId === resource.id}
                  />
                ))}
              </Reveal>
            </div>
            {chosen && <ArrowDown size={22} className="optimization-arrow" />}
            <p className="selection-reason">
              {!chosen
                ? need.unmetReason
                : chosen.id === need.recommendedOptionId
                  ? (need.recommendationReason ?? chosen?.description)
                  : chosen?.description}
            </p>
          </>
        ) : (
          <div className="unmet-comparison">
            <CircleHelp size={24} />
            <p>{need?.unmetReason ?? "No needs have been provided yet."}</p>
            <span>An unmatched need stays in the plan.</span>
          </div>
        )}
      </div>
    </section>
  );
}
