import { Check, ArrowDown, Package } from "lucide-react";
import type { Resource, SearchSource } from "@/lib/types";
import { OttoAgent } from "./OttoAgent";
import { ResourceCard } from "./ResourceCard";
import { Reveal } from "./Reveal";
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
  const active = sources[activeIndex];
  const visible = candidates.filter((resource) =>
    sources
      .slice(0, activeIndex + 1)
      .some((source) => source.sources.includes(resource.source)),
  );
  return (
    <section className="search-screen">
      <div className="section-intro">
        <Reveal>
          <span className="eyebrow">02 / SEARCHING</span>
          <h1>Checking what already exists</h1>
          <p className="lead" aria-live="polite">
            {active ? (
              <>
                Looking through <em>{active.label}</em>
              </>
            ) : (
              "Every rung checked."
            )}
          </p>
        </Reveal>
      </div>
      <div className="search-layout">
        <ol
          className="resolution-ladder"
          aria-label="Resource search hierarchy"
        >
          <Reveal>
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
          </Reveal>
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
        </div>
      </div>
      {disclosure && <p className="demo-note">{disclosure}</p>}
    </section>
  );
}
