import { Check, ArrowDown, Package, ArrowDownRight } from "lucide-react";
import type { Resource, SearchSource } from "@/lib/types";
import { OttoAgent } from "./OttoAgent";
import { ResourceCard } from "./ResourceCard";
export function SearchProgress({
  activeIndex,
  candidates,
  sources,
  disclosure,
  reviewing = false,
}: {
  activeIndex: number;
  candidates: Resource[];
  sources: SearchSource[];
  disclosure: string;
  reviewing?: boolean;
}) {
  const visible = candidates.filter((resource) =>
    sources
      .slice(0, activeIndex + 1)
      .some((source) => source.sources.includes(resource.source)),
  );
  return (
    <section className="search-screen enter">
      <div className="section-intro">
        <span className="eyebrow">02 / LOOKING IN THE RIGHT PLACES</span>
        <h1>
          More possibilities.
          <br />
          <em>Fewer new things.</em>
        </h1>
        <p className="lead">Yours first. New only when it needs to be.</p>
      </div>
      <div className="search-layout">
        <ol
          className="resolution-ladder"
          aria-label="Resource search hierarchy"
        >
          {sources.map((source, index) => {
            const done = index < activeIndex;
            const active = index === activeIndex;
            const matches = candidates.filter((resource) =>
              source.sources.includes(resource.source),
            );
            return (
              <li
                key={source.id}
                className={`ladder-step ${done ? "complete" : ""} ${active ? "active" : ""} ${index > activeIndex ? "pending" : ""}`}
                aria-current={active ? "step" : undefined}
              >
                <div className="ladder-rail">
                  <span className="ladder-icon">
                    {done ? (
                      <Check size={19} />
                    ) : (
                      <span className="rung-number">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                    )}
                  </span>
                  {index < sources.length - 1 && (
                    <span className="rail-line">
                      <ArrowDown size={13} />
                    </span>
                  )}
                </div>
                <div className="ladder-content">
                  <div className="ladder-title">
                    <span>{source.label}</span>
                    <small>
                      {done
                        ? `${matches.length} ${matches.length === 1 ? "match" : "matches"}`
                        : active
                          ? reviewing
                            ? "REVIEWING"
                            : "EXPLORING"
                          : source.sources.includes("new")
                            ? "ONLY IF NEEDED"
                            : "UP NEXT"}
                    </small>
                  </div>
                  <p>
                    {done
                      ? `${source.checked !== undefined ? `${source.checked} resources checked · ` : ""}${matches.length} ${matches.length === 1 ? "option" : "options"} in the resource pool`
                      : source.subtitle}
                  </p>
                </div>
                {active && <OttoAgent state="searching" compact />}
              </li>
            );
          })}
        </ol>
        <div className="resource-pool">
          <div className="pool-heading">
            <span className="eyebrow">YOUR GROWING RESOURCE POOL</span>
            <span>{visible.length.toString().padStart(2, "0")}</span>
          </div>
          <div className="pool-cards">
            {visible.length === 0 ? (
              <div className="pool-empty">
                <Package size={28} />
                <p>No options revealed here yet.</p>
              </div>
            ) : (
              visible
                .slice(-6)
                .map((resource) => (
                  <ResourceCard
                    key={resource.id}
                    resource={resource}
                    variant="scouting"
                  />
                ))
            )}
          </div>
          <div className="pool-footnote">
            <ArrowDownRight size={19} />
            <p>
              One goal. Different ways to meet it.
              <br />
              <span>
                {reviewing
                  ? "Revealing the returned possibilities."
                  : "Otto is putting the possibilities together."}
              </span>
            </p>
          </div>
        </div>
      </div>
      <p className="demo-note">{disclosure}</p>
    </section>
  );
}
