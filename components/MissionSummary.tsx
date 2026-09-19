import { ArrowRight, Check, MapPin, Wallet, CalendarDays } from "lucide-react";
import type { Mission } from "@/lib/types";
import { money } from "@/lib/demo-data";
import { OttoAgent } from "./OttoAgent";
export function MissionSummary({
  mission,
  onContinue,
  onEdit,
}: {
  mission: Mission | null;
  onContinue: () => void;
  onEdit: () => void;
}) {
  if (!mission)
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
  return (
    <section className="understanding-screen enter">
      <div className="section-intro">
        <span className="eyebrow">01 / YOUR MISSION, UNDERSTOOD</span>
        <h1>{mission.title}</h1>
        <p className="lead">
          A temporary home. Everything you need to settle in.
        </p>
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
              <strong>{money(mission.budget)}</strong>
            </div>
            <div>
              <CalendarDays size={18} />
              <span>Duration</span>
              <strong>{mission.duration}</strong>
            </div>
            <div>
              <MapPin size={18} />
              <span>Location</span>
              <strong>{mission.location}</strong>
            </div>
          </div>
          <div className="priorities">
            {mission.preferences.map((p) => (
              <span key={p.id}>{p.label}</span>
            ))}
          </div>
        </div>
        <div className="needs-section">
          <span className="eyebrow">WHAT YOU ACTUALLY NEED</span>
          <div className="needs-list">
            {mission.needs.map((need, index) => (
              <div
                className="need-row enter"
                style={{ animationDelay: `${index * 110}ms` }}
                key={need.id}
              >
                <span className="need-number">0{index + 1}</span>
                <span>{need.label}</span>
                <Check size={15} />
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="understanding-footer">
        <div className="agent-caption">
          <OttoAgent state="success" compact />
          <p>
            Before buying anything,
            <br />
            <strong>let’s see what already exists.</strong>
          </p>
        </div>
        <div className="actions">
          <button className="text-button" onClick={onEdit}>
            Edit my mission
          </button>
          <button className="button primary" onClick={onContinue}>
            Find a better way <ArrowRight size={17} />
          </button>
        </div>
      </div>
      <p className="demo-note">
        Demo understanding uses the Boston / $500 / 3-month fixture.
      </p>
    </section>
  );
}
