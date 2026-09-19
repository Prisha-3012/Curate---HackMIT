"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, Mic, Volume2 } from "lucide-react";
import { converse, type ConverseMessage } from "@/lib/services/converseApi";
import { useOttoVoice } from "@/lib/useOttoVoice";
import { useVoiceCapture } from "@/lib/useVoiceCapture";
import { OttoAgent } from "./OttoAgent";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const USER = process.env.NEXT_PUBLIC_DEMO_USER_ID ?? "";

/**
 * Otto asks, you answer — by speaking, typing, or tapping a choice.
 *
 * Every answer route exists because each fails differently: a mic can be
 * declined, a transcript can be wrong, and on a noisy demo floor tapping a
 * button is the only thing guaranteed to work. The conversation ends with a
 * goal and a budget, which the caller hands to /api/mission.
 */
export function OttoConversation({
  onReady,
  onCancel,
}: {
  onReady: (goalText: string, budgetCents: number | null) => void;
  onCancel: () => void;
}) {
  const [messages, setMessages] = useState<ConverseMessage[]>([]);
  const [expects, setExpects] = useState<"text" | "choice" | "none">("text");
  const [choices, setChoices] = useState<string[]>([]);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(true);
  const [notice, setNotice] = useState("");
  const [scripted, setScripted] = useState(false);
  const started = useRef(false);
  const log = useRef<HTMLDivElement>(null);

  const { speak, stop: stopSpeaking } = useOttoVoice(BASE);

  const advance = useCallback(
    async (history: ConverseMessage[]) => {
      setBusy(true);
      setNotice("");
      try {
        const reply = await converse(BASE, USER, history);
        setMessages([...history, { role: "otto", content: reply.say }]);
        setExpects(reply.expects);
        setChoices(reply.choices);
        if (reply.source === "fixture") setScripted(true);
        void speak(reply.say);
        if (reply.ready) {
          // The backend re-derives the budget from what was actually said, so
          // this is the person's figure, not the model's guess.
          onReady(reply.goalText ?? "", reply.budgetCents);
        }
      } catch (cause) {
        setNotice(
          cause instanceof Error
            ? cause.message
            : "Otto lost the thread. Please try again, or type your goal.",
        );
        setExpects("text");
      } finally {
        setBusy(false);
      }
    },
    [onReady, speak],
  );

  // Opening turn, once. Strict mode double-invokes effects in development, and
  // without this guard Otto greets you twice and talks over himself.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void advance([]);
  }, [advance]);

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  const answer = useCallback(
    (text: string) => {
      const said = text.trim();
      if (!said || busy) return;
      stopSpeaking(); // answering interrupts Otto, as it would a person
      setTyped("");
      void advance([...messages, { role: "user", content: said }]);
    },
    [busy, messages, advance, stopSpeaking],
  );

  const mic = useVoiceCapture({
    baseUrl: BASE,
    onTranscript: answer,
    onNotice: setNotice,
  });

  return (
    <section className="understanding-screen enter" aria-label="Talking to Otto">
      <div className="section-intro">
        <span className="eyebrow">
          <Volume2 size={13} /> OTTO IS LISTENING
        </span>
        <h1>Let&rsquo;s figure out what you need.</h1>
      </div>

      <div className="conversation-log" ref={log} role="log" aria-live="polite">
        {messages.map((m, i) => (
          <p key={i} className={`turn turn-${m.role}`}>
            {m.role === "otto" && <OttoAgent compact />}
            <span>{m.content}</span>
          </p>
        ))}
        {busy && (
          <p className="turn turn-otto">
            <OttoAgent state="thinking" compact />
            <span className="animated-dots">…</span>
          </p>
        )}
      </div>

      {notice && (
        <p className="notice-banner" role="status">
          {notice}
        </p>
      )}
      {scripted && (
        <p className="demo-note">
          Otto is using its standard questions — live conversation is
          unavailable right now.
        </p>
      )}

      {expects !== "none" && (
        <div className="conversation-answer">
          {expects === "choice" && (
            <div className="priorities">
              {choices.map((c) => (
                <button key={c} type="button" disabled={busy} onClick={() => answer(c)}>
                  {c}
                </button>
              ))}
            </div>
          )}
          <form
            className="mission-composer"
            onSubmit={(e) => {
              e.preventDefault();
              answer(typed);
            }}
          >
            <label className="sr-only" htmlFor="otto-answer">
              Your answer
            </label>
            <textarea
              id="otto-answer"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder="Say it out loud, or type it here"
              rows={2}
              maxLength={500}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  answer(typed);
                }
              }}
            />
            <div className="composer-bottom">
              {mic.supported && (
                <button
                  type="button"
                  className={`voice-button voice-${mic.state}`}
                  onClick={mic.toggle}
                  disabled={busy || mic.state === "transcribing"}
                  aria-pressed={mic.state === "recording"}
                  aria-label={
                    mic.state === "recording" ? "Stop recording" : "Answer by voice"
                  }
                >
                  <Mic size={19} />
                </button>
              )}
              <span className="input-hint">Enter to send</span>
              <button className="button primary" type="submit" disabled={busy || !typed.trim()}>
                Send <ArrowUpRight size={18} />
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="understanding-footer">
        <div className="actions">
          <button
            className="text-button"
            onClick={() => {
              stopSpeaking();
              onCancel();
            }}
          >
            Type it instead
          </button>
        </div>
      </div>
    </section>
  );
}
