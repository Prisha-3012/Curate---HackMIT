"use client";
import { useEffect, useRef, useState } from "react";
import { RotateCcw } from "lucide-react";
import { EnoughLogo } from "./EnoughLogo";
import { MissionInput } from "./MissionInput";
import { MissionSummary } from "./MissionSummary";
import { SearchProgress } from "./SearchProgress";
import { OptimizationView } from "./OptimizationView";
import { EnoughPlan } from "./EnoughPlan";
import { DemoControls } from "./DemoControls";
import { enoughService } from "@/lib/services";
import {
  calculatePlan,
  DEMO_INPUT,
  demoMission,
  resources,
  TIMING,
  searchSources,
} from "@/lib/demo-data";
import type { AppStage, Mission, Resource, OptimizedPlan } from "@/lib/types";
export function EnoughExperience() {
  const [stage, setStage] = useState<AppStage>("mission");
  const [input, setInput] = useState("");
  const [mission, setMission] = useState<Mission | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [candidates, setCandidates] = useState<Resource[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [plan, setPlan] = useState<OptimizedPlan | null>(null);
  const [showControls, setShowControls] = useState(false);
  const generation = useRef(0);
  const mainRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const lifecycle = generation;
    setShowControls(
      new URLSearchParams(window.location.search).get("demoControls") ===
        "true",
    );
    return () => {
      lifecycle.current++;
    };
  }, []);
  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [stage]);
  function reset() {
    generation.current++;
    setStage("mission");
    setMission(null);
    setPlan(null);
    setCandidates([]);
    setActiveIndex(0);
    setError("");
    setNotice("");
  }
  async function submit() {
    if (!input.trim() || stage !== "mission") return;
    const id = ++generation.current;
    setError("");
    setNotice("");
    setStage("understanding");
    setMission(null);
    try {
      const result = await enoughService.understandMission(input.trim());
      if (id === generation.current) setMission(result);
    } catch {
      if (id === generation.current) {
        setStage("mission");
        setError(
          "Otto couldn’t understand that mission. Your text is saved; please try again.",
        );
      }
    }
  }
  async function search() {
    if (!mission) return;
    const id = ++generation.current;
    setError("");
    setNotice("");
    setCandidates([]);
    setActiveIndex(0);
    setStage("searching");
    try {
      const result = await enoughService.searchResources(mission, []);
      if (id !== generation.current) return;
      setCandidates(result);
      for (let index = 0; index < searchSources.length; index++) {
        if (id !== generation.current) return;
        setActiveIndex(index);
        await new Promise((resolve) => setTimeout(resolve, TIMING.source));
      }
      if (id !== generation.current) return;
      setStage("optimizing");
      const optimized = await enoughService.optimizePlan(mission, result);
      if (id !== generation.current) return;
      setPlan(optimized);
      setStage("plan");
    } catch {
      if (id === generation.current) {
        setStage("understanding");
        setError(
          "The resource search was interrupted. Your mission is saved; try again.",
        );
      }
    }
  }
  function jump(next: AppStage) {
    generation.current++;
    setError("");
    setNotice("");
    setMission(structuredClone(demoMission));
    setCandidates(structuredClone(resources));
    setPlan(calculatePlan(resources));
    setActiveIndex(2);
    setStage(next);
  }
  const stageLabel = {
    mission: "Tell Otto your goal",
    understanding: mission
      ? "Your mission is understood"
      : "Understanding your mission",
    searching: `Exploring ${searchSources[activeIndex].label.toLowerCase()} resources`,
    optimizing: "Finding the best combination",
    plan: "Your ENOUGH plan is ready",
  }[stage];
  return (
    <div className="app-shell">
      <header className="site-header">
        <EnoughLogo />
        <div className="header-right">
          <span className="demo-label">
            <span /> THE BOSTON DEMO
          </span>
          <button className="reset-button" onClick={reset}>
            <RotateCcw size={13} /> Reset demo
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
        {stage === "mission" && (
          <MissionInput
            input={input}
            onChange={setInput}
            onSubmit={submit}
            busy={false}
            onVoice={() => {
              setInput(DEMO_INPUT);
              setNotice(
                "Simulated voice input added. No microphone was accessed.",
              );
            }}
          />
        )}{" "}
        {stage === "understanding" && (
          <MissionSummary
            mission={mission}
            onContinue={search}
            onEdit={reset}
          />
        )}{" "}
        {stage === "searching" && (
          <SearchProgress activeIndex={activeIndex} candidates={candidates} />
        )}{" "}
        {stage === "optimizing" && <OptimizationView candidates={candidates} />}{" "}
        {stage === "plan" && mission && plan && (
          <EnoughPlan mission={mission} plan={plan} onRestart={reset} />
        )}
      </main>
      {showControls && <DemoControls stage={stage} onJump={jump} />}
      <footer className="site-footer">
        <span>
          Use what exists. <strong>Buy what matters.</strong>
        </span>
        <div
          className="footer-ladder"
          aria-label="Resource priority: own, circle, used, rent, new"
        >
          <span>OWN</span>
          <i>→</i>
          <span>CIRCLE</span>
          <i>→</i>
          <span>USED</span>
          <i>→</i>
          <span>RENT</span>
          <i>→</i>
          <span>NEW</span>
        </div>
      </footer>
    </div>
  );
}
