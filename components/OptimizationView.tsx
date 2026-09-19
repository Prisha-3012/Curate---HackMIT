import { Check, ArrowDown, MapPin } from "lucide-react";
import type { Resource } from "@/lib/types";
import { money } from "@/lib/demo-data";
import { OttoAgent } from "./OttoAgent";
import { ResourceSourceBadge } from "./ResourceSourceBadge";
export function OptimizationView({ candidates }: { candidates: Resource[] }) {
  const desks = candidates.filter(
    (r) => r.category === "study" && r.id !== "chair",
  );
  return (
    <section className="optimization-screen enter">
      <div className="optimization-intro">
        <OttoAgent state="optimizing" />
        <span className="eyebrow">03 / MAKING THE PIECES FIT</span>
        <h1>
          Finding the best
          <br />
          <em>combination.</em>
        </h1>
        <p className="lead">
          {candidates.length} possibilities. One plan that makes sense for you.
        </p>
      </div>
      <div className="optimization-example">
        <div className="optimization-label">
          <span className="eyebrow">A CLOSER LOOK: YOUR STUDY SPACE</span>
          <span>Cost + distance + 3-month fit</span>
        </div>
        <div className="candidate-grid">
          {desks.map((resource) => (
            <div
              key={resource.id}
              className={`candidate ${resource.id === "desk" ? "candidate-selected" : ""}`}
            >
              <ResourceSourceBadge source={resource.source} />
              <h3>{resource.name}</h3>
              <strong>{money(resource.price)}</strong>
              <span className="candidate-detail">
                {resource.distanceMiles !== undefined ? (
                  <>
                    <MapPin size={12} />
                    {resource.distanceMiles} miles away
                  </>
                ) : (
                  resource.description
                )}
              </span>
              {resource.id === "desk" && (
                <span className="selected-mark">
                  <Check size={12} /> BEST FIT
                </span>
              )}
            </div>
          ))}
        </div>
        <ArrowDown size={22} className="optimization-arrow" />
        <p className="selection-reason">
          Close enough to collect. Affordable enough to keep.
          <br />
          <span>And easy to pass on when summer ends.</span>
        </p>
      </div>
    </section>
  );
}
