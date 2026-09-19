import { ArrowUpRight, CornerDownLeft, Mic, MoveUpRight } from "lucide-react";
import type { ExperienceCopy } from "@/lib/types";
import { OttoAgent } from "./OttoAgent";
export function MissionInput({
  input,
  onChange,
  onSubmit,
  busy,
  onVoice,
  copy,
  exampleInput,
}: {
  copy: ExperienceCopy;
  exampleInput: string;
  input: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
  onVoice: () => void;
}) {
  return (
    <section className="mission-screen enter">
      <div className="eyebrow">
        <span className="tiny-star">✳</span> A LITTLE RESOURCEFULNESS GOES A
        LONG WAY
      </div>
      <h1>
        What are you trying
        <br />
        to <em>accomplish?</em>
      </h1>
      <p className="lead">
        Tell Otto the goal. We’ll figure out what you actually need.
      </p>
      <form
        className="mission-composer"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <label className="sr-only" htmlFor="mission">
          Your mission
        </label>
        <textarea
          id="mission"
          value={input}
          onChange={(e) => onChange(e.target.value)}
          placeholder={copy.placeholder}
          maxLength={2000}
          required
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              if (input.trim()) onSubmit();
            }
          }}
        />
        <div className="composer-bottom">
          <button
            type="button"
            className="voice-button"
            onClick={onVoice}
            aria-label="Try simulated voice input"
            title="Try simulated voice input"
          >
            <Mic size={19} />
          </button>
          <span className="input-hint">
            <CornerDownLeft size={12} /> ⌘ / Ctrl + Enter
          </span>
          <button
            className="button primary"
            type="submit"
            disabled={busy || !input.trim()}
          >
            {busy ? "Understanding your mission…" : "Let Otto figure it out"}
            <ArrowUpRight size={18} />
          </button>
        </div>
      </form>
      <div className="example-row">
        <span>Try a mission</span>
        <button onClick={() => onChange(exampleInput)}>
          {copy.exampleLabel} <MoveUpRight size={13} />
        </button>
      </div>
      <div className="mission-promise">
        <OttoAgent compact />
        <p>
          A good plan starts with what already exists.
          <br />
          <span>Buying new comes last.</span>
        </p>
      </div>
      <p className="demo-note">{copy.disclosure}</p>
    </section>
  );
}
