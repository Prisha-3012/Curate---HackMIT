import { Check, MapPin, Ruler } from "lucide-react";
import type { Resource } from "@/lib/types";
import { money, percent } from "@/lib/formatting";
import { ResourceVisual } from "./ResourceVisual";
import { ResourceSourceBadge } from "./ResourceSourceBadge";
export function ResourceCard({
  resource,
  needLabel,
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
        needLabel={needLabel}
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
          (resource.source === "used" || resource.source === "new") && (
            <a
              className="product-link"
              href={resource.productUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              View product →
            </a>
          )}
        {variant !== "scouting" && resource.needsFitcheck && (
          <span className="fitcheck-note">
            <Ruler size={11} /> Fit check needed
          </span>
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
