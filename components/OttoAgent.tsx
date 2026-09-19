import type { OttoState } from "@/lib/types";
export function OttoAgent({
  state = "idle",
  compact = false,
}: {
  state?: OttoState;
  compact?: boolean;
}) {
  return (
    <span
      className={`otto otto-${state} ${compact ? "otto-small" : ""}`}
      role="img"
      aria-label={`Otto, ${state}`}
    >
      <svg viewBox="0 0 64 64" fill="none" aria-hidden="true">
        <path
          d="M12 27C12 14 21 9 32 9s20 5 20 18v13c0 10-6 15-13 15l-7-4-7 4c-7 0-13-5-13-15V27Z"
          fill="currentColor"
        />
        <g className="otto-eyes">
          <rect x="23" y="25" width="5" height="10" rx="2.5" fill="#f7f6f0" />
          <rect x="36" y="25" width="5" height="10" rx="2.5" fill="#f7f6f0" />
        </g>
        <path
          d="M28 41c2.5 2 5.5 2 8 0"
          stroke="#f7f6f0"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}
