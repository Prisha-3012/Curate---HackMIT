import { ArrowRight, Check, MapPin, Wallet, CalendarDays } from "lucide-react";
import type { MissionExperience } from "@/lib/types";
import { money } from "@/lib/formatting";
import { groupNeeds } from "@/lib/plan";
import { OttoAgent } from "./OttoAgent";
export function MissionSummary({
  experience,
  onContinue,
  onEdit,
}: {
  experience: MissionExperience | null;
  onContinue: () => void;
  onEdit: () => void;
}) {
  if (!experience)
    return (
      <section className="loading-understanding enter">
        <OttoAgent state="thinking" />
        <p className="eyebrow">FIRST, THE BIG PICTURE</p>
        <h1>
          Breaking that down<span className="animated-dots">…</span>
        </h1>
        <p className="lead">A few details. A clearer direction.</p>
        <div className="skeleton-lines" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
      </section>
    );
  const { mission, copy } = experience;
  return (
    <section className="understanding-screen">
      <div className="section-intro stagger">
        <span className="eyebrow">01 / YOUR MISSION, UNDERSTOOD</span>
        <h1>{mission.title}</h1>
        <p className="lead">{copy.summary}</p>
      </div>
      <div className="understanding-layout">
        <div className="mission-brief">
          <div className="brief-top">
            <span className="eyebrow">THE BRIEF</span>
            <Check size={18} />
          </div>
          <p className="brief-quote">“{mission.rawInput}”</p>
          <div className="constraint-grid">
            <div>
              <Wallet size={18} />
              <span>Budget</span>
              <strong>
                {mission.budget === null ? "Not stated" : money(mission.budget)}
              </strong>
            </div>
            {mission.duration && (
              <div>
                <CalendarDays size={18} />
                <span>Duration</span>
                <strong>{mission.duration}</strong>
              </div>
            )}
            {mission.location && (
              <div>
                <MapPin size={18} />
                <span>Location</span>
                <strong>{mission.location}</strong>
              </div>
            )}
          </div>
          {!!mission.preferences?.length && (
            <div className="priorities">
              {mission.preferences.map((p) => (
                <span key={p.id}>{p.label}</span>
              ))}
            </div>
          )}
        </div>
        <div className="needs-section">
          <span className="eyebrow">WHAT YOU ACTUALLY NEED</span>
          <div className="needs-list">
            {groupNeeds(mission.needs).map((group, index) => (
              <div
                className="need-row enter"
                style={{ animationDelay: `${index * 110}ms` }}
                key={group.id}
              >
                <span className="need-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div>
                  <span>{group.label}</span>
                  {group.needs.length === 1 && group.needs[0].rationale && (
                    <p className="need-rationale">{group.needs[0].rationale}</p>
                  )}
                </div>
                <Check size={15} />
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="understanding-footer">
        <div className="actions">
          <button className="text-button" onClick={onEdit}>
            Edit my mission
          </button>
          <button className="button primary" onClick={onContinue}>
            Next <ArrowRight size={17} />
          </button>
        </div>
      </div>
      {copy.disclosure && <p className="demo-note">{copy.disclosure}</p>}
    </section>
  );
}
