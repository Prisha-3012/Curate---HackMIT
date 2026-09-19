import {
  BedDouble,
  BookOpen,
  LampDesk,
  CookingPot,
  Brush,
  Archive,
  Check,
  MapPin,
  ArrowUpRight,
} from "lucide-react";
import type { Mission, OptimizedPlan } from "@/lib/types";
import { money } from "@/lib/demo-data";
import { OttoAgent } from "./OttoAgent";
import { ResourceSourceBadge } from "./ResourceSourceBadge";
import { SavingsReveal } from "./SavingsReveal";
const needIcons = {
  sleep: BedDouble,
  study: BookOpen,
  lighting: LampDesk,
  cooking: CookingPot,
  cleaning: Brush,
  storage: Archive,
};
export function EnoughPlan({
  mission,
  plan,
  onRestart,
}: {
  mission: Mission;
  plan: OptimizedPlan;
  onRestart: () => void;
}) {
  const metrics = [
    { value: plan.newPurchasesAvoided, label: "new purchases avoided" },
    { value: plan.reusedResources, label: "existing resources reused" },
    { value: plan.nearbyResources, label: "finds within one mile" },
  ];
  return (
    <section className="plan-screen enter">
      <div className="plan-intro">
        <div>
          <span className="eyebrow">
            <Check size={13} /> YOUR MISSION, MADE POSSIBLE
          </span>
          <h1>
            Here’s your <em>ENOUGH</em> plan.
          </h1>
          <p className="lead">Everything you need. Less of what you don’t.</p>
        </div>
        <div className="plan-mission-stamp">
          <span>{mission.location}</span>
          <span>
            {mission.duration} · {money(mission.budget)} budget
          </span>
        </div>
      </div>
      <div className="plan-layout">
        <div className="plan-resources">
          <div className="plan-section-heading">
            <span className="eyebrow">A ROOM, RESOURCEFULLY PUT TOGETHER</span>
            <span>
              {plan.items.length} resources · {mission.needs.length} needs
            </span>
          </div>
          <div className="need-cards">
            {mission.needs.map((need, index) => {
              const Icon =
                needIcons[need.id as keyof typeof needIcons] || Archive;
              const items = plan.items.filter((i) => i.needId === need.id);
              return (
                <article
                  className={`need-card need-${need.id} enter`}
                  key={need.id}
                  style={{ animationDelay: `${index * 65}ms` }}
                >
                  <div className="need-card-heading">
                    <Icon size={18} strokeWidth={1.5} />
                    <h2>{need.label}</h2>
                    <span>0{index + 1}</span>
                  </div>
                  {items.map(({ resource, reasoning }) => (
                    <div className="plan-item" key={resource.id}>
                      <div className="plan-item-line">
                        <h3>{resource.name}</h3>
                        <strong>{money(resource.price)}</strong>
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
                      <p>{reasoning}</p>
                    </div>
                  ))}
                </article>
              );
            })}
          </div>
          <div className="plan-agent-note">
            <OttoAgent state="success" compact />
            <p>
              <strong>
                Buy new where it matters. Use what exists for the rest.
              </strong>
              <br />A new mattress for a fresh start. Existing resources for the
              rest.
            </p>
          </div>
        </div>
        <SavingsReveal plan={plan} mission={mission} />
      </div>
      <div className="impact-strip">
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
          <span className="completion-dot" /> Your room, figured out.
          <span className="plan-end-detail">
            {" "}
            A little intention goes a long way.
          </span>
        </p>
        <button className="text-button" onClick={onRestart}>
          Try the mission again <ArrowUpRight size={14} />
        </button>
      </div>
    </section>
  );
}
