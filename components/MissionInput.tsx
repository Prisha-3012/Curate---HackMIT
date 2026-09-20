import { useRef, useState } from "react";
import {
  ArrowUpRight,
  CornerDownLeft,
  ImagePlus,
  Mic,
  MoveUpRight,
  X,
} from "lucide-react";
import type { ExperienceCopy } from "@/lib/types";
import type { ReactNode } from "react";
import { OttoAgent } from "./OttoAgent";
import { FluidShapes } from "./FluidShapes";
import { Reveal } from "./Reveal";

/** What the mic is doing right now, in words, for people who can see it. */
const VOICE_STATUS: Record<string, string> = {
  recording: "Listening…",
  transcribing: "Writing that down…",
};

export function MissionInput({
  input,
  onChange,
  onSubmit,
  busy,
  onVoice,
  onTalk,
  voiceState = "simulated",
  copy,
  exampleInput,
  closetCheck,
}: {
  closetCheck?: ReactNode;
  copy: ExperienceCopy;
  exampleInput: string;
  input: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
  onVoice?: () => void;
  /** Starts a spoken conversation. Absent offline, which has no backend. */
  onTalk?: () => void;
  /** "simulated" keeps the offline demo's original wording. */
  voiceState?: "simulated" | "idle" | "recording" | "transcribing";
}) {
  // An attached image is held here and nowhere else. No endpoint accepts one
  // yet, so this control must not imply the photo was sent anywhere.
  const [image, setImage] = useState<{ name: string; url: string } | null>(
    null,
  );
  const fileRef = useRef<HTMLInputElement>(null);

  const voiceLabel = {
    simulated: "Try simulated voice input",
    idle: "Record your mission",
    recording: "Stop recording",
    transcribing: "Transcribing…",
  }[voiceState];
  const status = VOICE_STATUS[voiceState];

  function attach(file: File | undefined) {
    if (!file) return;
    if (image) URL.revokeObjectURL(image.url);
    setImage({ name: file.name, url: URL.createObjectURL(file) });
  }
  function detach() {
    if (image) URL.revokeObjectURL(image.url);
    setImage(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  return (
    <section className="mission-screen">
      <FluidShapes />
      <Reveal>
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
          Say what you want to pull off, plus anything that limits it — a
          budget, a date, a place. Otto works out what that actually requires,
          then looks for each piece before suggesting you buy it.
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
          {image && (
            <div className="attachment">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={image.url} alt="" />
              <span>{image.name}</span>
              <button
                type="button"
                onClick={detach}
                aria-label={`Remove ${image.name}`}
              >
                <X size={13} />
              </button>
            </div>
          )}
          <div className="composer-bottom">
            {onVoice && (
              <button
                type="button"
                className={`voice-button voice-${voiceState}`}
                onClick={onVoice}
                aria-label={voiceLabel}
                aria-pressed={voiceState === "recording"}
                title={voiceLabel}
                disabled={voiceState === "transcribing"}
              >
                <Mic size={19} />
              </button>
            )}
            <input
              ref={fileRef}
              id="mission-image"
              type="file"
              accept="image/*"
              className="sr-only"
              onChange={(e) => attach(e.target.files?.[0])}
            />
            <button
              type="button"
              className="voice-button"
              onClick={() => fileRef.current?.click()}
              aria-label="Add a photo"
              title="Add a photo"
            >
              <ImagePlus size={18} />
            </button>
            {status ? (
              <span className="voice-status" role="status" aria-live="polite">
                <i aria-hidden="true" /> {status}
              </span>
            ) : (
              <span className="input-hint">
                <CornerDownLeft size={12} /> ⌘ / Ctrl + Enter
              </span>
            )}
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
        <p className="mission-hint">
          Try something like <em>“business casual for my internship, about
          $150”</em> or <em>“camping next weekend, I have $60”</em>.
        </p>
        <div className="example-row">
          {onTalk && (
            <button className="talk-button" onClick={onTalk}>
              <Mic size={13} /> Talk to Otto
            </button>
          )}
          <button onClick={() => onChange(exampleInput)}>
            {copy.exampleLabel} <MoveUpRight size={13} />
          </button>
        </div>
        {closetCheck}
        <div className="mission-promise">
          <OttoAgent compact />
          <p>
            A good plan starts with what already exists.
            <br />
            <span>Buying new comes last.</span>
          </p>
        </div>
        {copy.disclosure && <p className="demo-note">{copy.disclosure}</p>}
      </Reveal>
    </section>
  );
}
