"use client";
import { Fragment, useEffect, useRef, useState } from "react";
import { RotateCcw } from "lucide-react";
import { EnoughLogo } from "./EnoughLogo";
import { MissionInput } from "./MissionInput";
import { MissionSummary } from "./MissionSummary";
import { SearchProgress } from "./SearchProgress";
import { OptimizationView } from "./OptimizationView";
import { EnoughPlan } from "./EnoughPlan";
import { DemoControls } from "./DemoControls";
import { OttoConversation } from "./OttoConversation";
import { getEnoughService } from "@/lib/services";
import { waitForDemo } from "@/lib/services/mockEnoughService";
import { DEMO_MODE, TIMING } from "@/lib/demo-data";
import { useVoiceCapture } from "@/lib/useVoiceCapture";
import { backendCopy, backendSources } from "@/lib/api/adaptBackendPlan";
import { defaultFixture, findFixture, fixtures } from "@/lib/fixtures";
import { candidateResources, comparisonNeed, prepareFixture } from "@/lib/plan";
import type { AppStage, MissionExperience } from "@/lib/types";
export function EnoughExperience() {
  const [stage, setStage] = useState<AppStage>("mission");
  const [fixture, setFixture] = useState(defaultFixture);
  const [input, setInput] = useState("");
  const [experience, setExperience] = useState<MissionExperience | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [discovered, setDiscovered] = useState(false);
  const [showControls, setShowControls] = useState(false);
  const running = useRef<AbortController | null>(null);
  const mainRef = useRef<HTMLElement>(null);
  // Hooks cannot be called conditionally, so this runs in demo mode too; its
  // toggle is simply never wired up there.
  const voice = useVoiceCapture({
    baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "",
    onTranscript: setInput,
    onNotice: setNotice,
  });
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setShowControls(params.get("demoControls") === "true");
    setFixture(findFixture(params.get("fixture")));
    const lifecycle = running;
    return () => lifecycle.current?.abort();
  }, []);
  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [stage]);
  function beginRun() {
    running.current?.abort();
    const controller = new AbortController();
    running.current = controller;
    return controller;
  }
  function reset() {
    running.current?.abort();
    setStage("mission");
    setExperience(null);
    setActiveIndex(0);
    setDiscovered(false);
    setError("");
    setNotice("");
  }
  function selectFixture(id: string) {
    reset();
    setInput("");
    const next = findFixture(id);
    setFixture(next);
    const url = new URL(window.location.href);
    url.searchParams.set("fixture", next.id);
    window.history.replaceState(null, "", url);
  }
  async function submit(
    explicitGoal?: string,
    budgetCents?: number | null,
  ) {
    const goal = (explicitGoal ?? input).trim();
    // The conversation finishes on the "conversation" stage, so the original
    // mission-only guard would have silently dropped every spoken mission.
    if (!goal || (stage !== "mission" && stage !== "conversation")) return;
    const run = beginRun();
    setError("");
    setNotice("");
    setStage("understanding");
    setExperience(null);
    try {
      const result = await getEnoughService(fixture).prepareMission(
        goal,
        run.signal,
        budgetCents,
      );
      if (!run.signal.aborted) setExperience(result);
    } catch (cause) {
      if (!run.signal.aborted) {
        setStage("mission");
        setError(
          cause instanceof Error
            ? cause.message
            : "Otto couldn’t prepare that mission. Your text is saved; please try again.",
        );
      }
    }
  }
  async function search() {
    if (!experience) return;
    const run = beginRun();
    setError("");
    setNotice("");
    setDiscovered(false);
    setActiveIndex(0);
    setStage("searching");
    try {
      await waitForDemo(TIMING.search, run.signal);
      setDiscovered(true);
      for (let index = 0; index < experience.sources.length; index++) {
        setActiveIndex(index);
        await waitForDemo(TIMING.source, run.signal);
      }
      setStage("optimizing");
      await waitForDemo(TIMING.optimize, run.signal);
      setStage("plan");
    } catch {
      if (!run.signal.aborted) {
        setStage("understanding");
        setError(
          "The example was interrupted. Your mission is saved; try again.",
        );
      }
    }
  }
  function jump(next: AppStage) {
    running.current?.abort();
    setError("");
    setNotice("");
    setExperience(prepareFixture(fixture));
    setDiscovered(true);
    setActiveIndex(Math.max(0, Math.min(2, fixture.sources.length - 1)));
    setStage(next);
  }
  const sources =
    experience?.sources ?? (DEMO_MODE ? fixture.sources : backendSources);
  const candidates = experience
    ? candidateResources(experience.mission.needs)
    : [];
  const stageLabel = {
    mission: "Tell Otto your goal",
    // Announced to screen readers; the conversation itself is an aria-live log.
    conversation: "Talking to Otto",
    understanding: experience
      ? "Your mission is understood"
      : "Preparing your mission",
    searching: `${DEMO_MODE ? "Exploring" : "Reviewing returned"} ${sources[activeIndex]?.label.toLowerCase() ?? "available"} resources`,
    optimizing: "Finding the best combination",
    plan: "Your ENOUGH plan is ready",
  }[stage];
  return (
    <div className="app-shell">
      <header className="site-header">
        <EnoughLogo />
        <div className="header-right">
          <span className="demo-label">
            <span />
            {DEMO_MODE
              ? fixture.badge
              : experience?.provenance === "backend-demo"
                ? "Backend demo fixture"
                : "Backend"}
          </span>
          <button className="reset-button" onClick={reset}>
            <RotateCcw size={13} /> {DEMO_MODE ? "Reset demo" : "New mission"}
          </button>
        </div>
      </header>
      <main ref={mainRef} tabIndex={-1} className="main-content">
        <div className="sr-only" role="status" aria-live="polite">
          {stageLabel}
        </div>
        {error && (
          <p className="error-banner" role="alert">
            {error}
          </p>
        )}
        {notice && (
          <p className="notice-banner" role="status">
            {notice}
          </p>
        )}
        {stage === "conversation" && (
          <OttoConversation
            onReady={(goalText, budgetCents) => {
              setInput(goalText);
              void submit(goalText, budgetCents);
            }}
            onCancel={() => setStage("mission")}
          />
        )}
        {stage === "mission" && (
          <MissionInput
            input={input}
            onChange={setInput}
            onSubmit={submit}
            busy={false}
            copy={DEMO_MODE ? fixture.copy : backendCopy}
            exampleInput={
              DEMO_MODE
                ? fixture.mission.rawInput
                : "Help me host a dinner for six with a $100 budget"
            }
            onVoice={
              DEMO_MODE
                ? () => {
                    setInput(fixture.mission.rawInput);
                    setNotice(
                      "Simulated voice input added. No microphone was accessed.",
                    );
                  }
                : voice.supported
                  ? voice.toggle
                  : undefined
            }
            voiceState={DEMO_MODE ? "simulated" : voice.state}
            onTalk={DEMO_MODE ? undefined : () => setStage("conversation")}
          />
        )}
        {stage === "understanding" && (
          <MissionSummary
            experience={experience}
            onContinue={search}
            onEdit={reset}
          />
        )}
        {stage === "searching" && (
          <SearchProgress
            activeIndex={activeIndex}
            candidates={discovered ? candidates : []}
            sources={sources}
            disclosure={experience?.copy.disclosure ?? fixture.copy.disclosure}
            reviewing={!DEMO_MODE}
          />
        )}
        {stage === "optimizing" && experience && (
          <OptimizationView
            need={comparisonNeed(experience)}
            candidateCount={candidates.length}
            criteria={experience.copy.optimizationCriteria}
          />
        )}
        {stage === "plan" && experience && (
          <EnoughPlan experience={experience} onRestart={reset} />
        )}
      </main>
      {DEMO_MODE && showControls && (
        <DemoControls
          stage={stage}
          onJump={jump}
          fixtures={fixtures}
          fixtureId={fixture.id}
          onFixture={selectFixture}
        />
      )}
      <footer className="site-footer">
        <span>
          Use what exists. <strong>Buy what matters.</strong>
        </span>
        <div
          className="footer-ladder"
          aria-label={`Resource priority: ${sources.map((source) => source.label.toLowerCase()).join(", ")}`}
        >
          {sources.map((source, index) => (
            <Fragment key={source.id}>
              {index > 0 && <i aria-hidden="true">→</i>}
              <span>{source.label}</span>
            </Fragment>
          ))}
        </div>
      </footer>
    </div>
  );
}
