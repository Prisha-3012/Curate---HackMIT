import {
  Check,
  ArrowDown,
  Package,
  Users,
  MapPin,
  Clock3,
  Plus,
  ArrowDownRight,
} from "lucide-react";
import type { Resource } from "@/lib/types";
import { searchSources, money } from "@/lib/demo-data";
import { OttoAgent } from "./OttoAgent";
const icons = [Package, Users, MapPin, Clock3, Plus];
export function SearchProgress({
  activeIndex,
  candidates,
}: {
  activeIndex: number;
  candidates: Resource[];
}) {
  const visible = candidates.filter((r) =>
    searchSources
      .slice(0, activeIndex + 1)
      .some((s) => s.sources.includes(r.source)),
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
          {searchSources.map((source, index) => {
            const Icon = icons[index];
            const done = index < activeIndex;
            const active = index === activeIndex;
            const matches = candidates.filter((r) =>
              source.sources.includes(r.source),
            );
            return (
              <li
                key={source.id}
                className={`ladder-step ${done ? "complete" : ""} ${active ? "active" : ""} ${index > activeIndex ? "pending" : ""}`}
                aria-current={active ? "step" : undefined}
              >
                <div className="ladder-rail">
                  <span className="ladder-icon">
                    {done ? <Check size={19} /> : <Icon size={19} />}
                  </span>
                  {index < searchSources.length - 1 && (
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
                          ? "EXPLORING"
                          : index === 4
                            ? "ONLY IF NEEDED"
                            : `0${index + 1}`}
                    </small>
                  </div>
                  <p>
                    {done
                      ? `${source.checked} resources checked · ${matches.length} useful ${matches.length === 1 ? "possibility" : "possibilities"}`
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
          <div className="pool-cards" aria-live="polite" aria-atomic="true">
            {visible.length === 0 ? (
              <div className="pool-empty">
                <Package size={28} />
                <p>Starting with what you already have.</p>
              </div>
            ) : (
              visible.slice(-6).map((resource) => (
                <div className="pool-card enter" key={resource.id}>
                  <span className="pool-dot" />
                  <div>
                    <strong>{resource.name}</strong>
                    <span>
                      {resource.source === "owned"
                        ? "Already yours"
                        : resource.ownerName ||
                          (resource.distanceMiles !== undefined
                            ? `${resource.distanceMiles} mi away`
                            : resource.source === "rent"
                              ? "Short-term rental"
                              : "Available new")}
                    </span>
                  </div>
                  <span>
                    {resource.price === 0 ? "Free" : money(resource.price)}
                  </span>
                </div>
              ))
            )}
          </div>
          <div className="pool-footnote">
            <ArrowDownRight size={19} />
            <p>
              One goal. Every source considered.
              <br />
              <span>Otto is building a solution, piece by piece.</span>
            </p>
          </div>
        </div>
      </div>
      <p className="demo-note">
        Simulated inventory, circle, and listings · No external searches
      </p>
    </section>
  );
}
