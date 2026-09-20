import type { AppStage, DemoFixture } from "@/lib/types";
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
  fixtures,
  fixtureId,
  onFixture,
}: {
  stage: AppStage;
  onJump: (stage: AppStage) => void;
  fixtures: DemoFixture[];
  fixtureId: string;
  onFixture: (id: string) => void;
}) {
  return (
    <nav className="demo-controls" aria-label="Demo stage controls">
      <label htmlFor="demo-fixture">LOCAL FIXTURE</label>
      <select
        id="demo-fixture"
        value={fixtureId}
        onChange={(event) => onFixture(event.target.value)}
      >
        {fixtures.map((fixture) => (
          <option key={fixture.id} value={fixture.id}>
            {fixture.label}
          </option>
        ))}
      </select>
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
