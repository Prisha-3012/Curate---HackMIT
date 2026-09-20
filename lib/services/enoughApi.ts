import { adaptBackendPlan } from "../api/adaptBackendPlan";
import { validatePlan } from "../api/validatePlan";
import type { MissionRequest } from "../api/plan";
import type { EnoughService } from "./enoughService";

/** No dollar budget means null; an explicit $0 remains zero. Never infer a cap. */
export function parseBudgetCents(input: string): number | null {
  const matches = [
    ...input.matchAll(
      /\$\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)(?!\d|[.,]\d)/g,
    ),
  ];
  if (!input.includes("$")) return null;
  if (matches.length !== 1 || (input.match(/\$/g)?.length ?? 0) !== 1)
    throw new Error(
      "Include one explicit budget, such as $100 or $0, in your mission.",
    );
  const cents = Math.round(Number(matches[0][1].replaceAll(",", "")) * 100);
  if (!Number.isSafeInteger(cents) || cents < 0)
    throw new Error("Enter a valid dollar budget.");
  return cents;
}
export function createEnoughApi(
  baseUrl: string,
  userId: string,
  timeoutMs = 45000,
): EnoughService {
  return {
    async prepareMission(input, signal, budgetCents) {
      if (!baseUrl || !userId)
        throw new Error("Backend URL and user ID must be configured.");
      const payload: MissionRequest = {
        user_id: userId,
        goal_text: input,
        budget_cents:
          budgetCents === undefined ? parseBudgetCents(input) : budgetCents,
      };
      const controller = new AbortController();
      const abort = () => controller.abort(signal?.reason);
      if (signal?.aborted) abort();
      signal?.addEventListener("abort", abort, { once: true });
      const timer = setTimeout(
        () =>
          controller.abort(
            new DOMException(
              "The plan request timed out. Please try again.",
              "TimeoutError",
            ),
          ),
        timeoutMs,
      );
      try {
        controller.signal.throwIfAborted();
        const response = await fetch(`${baseUrl.replace(/\/$/, "")}/mission`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal: controller.signal,
        });
        if (!response.ok)
          throw new Error(
            `The plan request failed (${response.status}). Please try again.`,
          );
        const plan = validatePlan(await response.json());
        controller.signal.throwIfAborted();
        return adaptBackendPlan(
          plan,
          input,
          response.headers.get("X-Demo-Fixture") || undefined,
        );
      } finally {
        clearTimeout(timer);
        signal?.removeEventListener("abort", abort);
      }
    },
  };
}
