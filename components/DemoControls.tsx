import type { AppStage } from "@/lib/types";
const stages: AppStage[] = [
  "mission",
  "understanding",
  "searching",
  "optimizing",
  "plan",
];
export function DemoControls({
  stage,
  onJump,
}: {
  stage: AppStage;
  onJump: (stage: AppStage) => void;
}) {
  return (
    <nav className="demo-controls" aria-label="Demo stage controls">
      <span>DEMO CONTROLS</span>
      {stages.map((value) => (
        <button
          key={value}
          aria-pressed={stage === value}
          onClick={() => onJump(value)}
        >
          {value}
        </button>
      ))}
    </nav>
  );
}
