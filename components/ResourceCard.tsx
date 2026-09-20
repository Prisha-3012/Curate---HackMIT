import { Check, MapPin } from "lucide-react";
import type { Resource } from "@/lib/types";
import { money, percent } from "@/lib/formatting";
import { ResourceVisual } from "./ResourceVisual";
import { ResourceSourceBadge } from "./ResourceSourceBadge";
import { FitCheck } from "./FitCheck";
export function ResourceCard({
  resource,
  variant = "plan",
  recommended = false,
  selected = false,
  explanation,
}: {
  resource: Resource;
  needLabel?: string;
  variant?: "plan" | "scouting" | "candidate";
  recommended?: boolean;
  selected?: boolean;
  explanation?: string;
}) {
  return (
    <div
      className={`resource-card resource-card-${variant} ${variant === "plan" ? "plan-item" : variant === "scouting" ? "pool-card enter" : "candidate"} ${recommended || selected ? "candidate-selected" : ""}`}
      data-resource-id={resource.id}
      data-recommended={recommended || undefined}
      data-selected={selected || undefined}
    >
      <ResourceVisual
        resource={resource}
        size={variant === "candidate" ? "large" : "small"}
      />
      <div className="resource-card-content">
        <div className="plan-item-line">
          <h3>{resource.name}</h3>
          <strong>
            {variant === "scouting" && resource.price === 0
              ? "Free"
              : money(resource.price)}
          </strong>
        </div>
        <div className="plan-item-meta">
          <ResourceSourceBadge source={resource.source} />
          {resource.distanceMiles !== undefined ? (
            <span>
              <MapPin size={10} />
              {resource.distanceMiles} mi
            </span>
          ) : resource.ownerName ? (
            <span>{resource.ownerName}</span>
          ) : null}
        </div>
        {variant !== "scouting" && (
          <p className="resource-explanation">
            {explanation ?? resource.description}
          </p>
        )}
        {variant === "candidate" && resource.matchScore !== undefined && (
          <span className="match-score">
            {percent(resource.matchScore)} match
          </span>
        )}
        {resource.productUrl &&
          (resource.source === "new" || resource.source === "used") && (
            <a
              className="product-link"
              href={resource.productUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              View product →
            </a>
          )}
        {resource.source === "used" &&
          !resource.productUrl &&
          (resource.marketplaces?.length ?? 0) > 0 && (
            <div
              className="marketplace-links"
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: "0.5rem",
                marginTop: "0.35rem",
              }}
            >
              <span style={{ fontSize: "0.72rem", opacity: 0.6 }}>
                Browse secondhand:
              </span>
              {resource.marketplaces!.map((m) => (
                <a
                  key={m.name}
                  className="product-link"
                  href={m.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ fontSize: "0.78rem" }}
                >
                  {m.name}
                </a>
              ))}
            </div>
          )}
        {variant !== "scouting" && resource.needsFitcheck && (
          <FitCheck item={{ name: resource.name, category: resource.category }} />
        )}
      </div>
      {(recommended || selected) && (
        <span className="selected-mark">
          <Check size={12} /> {selected ? "SELECTED" : "RECOMMENDED"}
        </span>
      )}
    </div>
  );
}
