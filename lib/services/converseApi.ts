/**
 * POST /api/converse — the spoken front door to /api/mission.
 *
 * Stateless on the server: the whole conversation is sent every turn, so this
 * holds the history and there is no session to lose on a refresh.
 */

export interface ConverseMessage {
  role: "otto" | "user";
  content: string;
}

export interface ConverseReply {
  /** Spoken aloud and shown. */
  say: string;
  expects: "text" | "choice" | "none";
  choices: string[];
  /** True when there is enough to build a plan. */
  ready: boolean;
  goalText: string | null;
  /** Cents. null means no budget was stated — NOT zero. */
  budgetCents: number | null;
  /** "fixture" means canned dialogue: no provider, or the daily quota is spent. */
  source: "live" | "fixture";
}

export async function converse(
  baseUrl: string,
  userId: string,
  messages: ConverseMessage[],
  signal?: AbortSignal,
): Promise<ConverseReply> {
  if (!baseUrl || !userId)
    throw new Error("Backend URL and user ID must be configured.");

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/converse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, messages }),
    signal,
  });
  if (!response.ok)
    throw new Error("Otto lost the thread. Please try again, or type your goal.");

  const body = (await response.json()) as Record<string, unknown>;
  if (typeof body.say !== "string" || !body.say)
    throw new Error("The conversation response was malformed.");

  const expects =
    body.expects === "text" || body.expects === "choice" || body.expects === "none"
      ? body.expects
      : "text";

  return {
    say: body.say,
    expects,
    choices: Array.isArray(body.choices) ? body.choices.map(String) : [],
    ready: body.ready === true,
    goalText: typeof body.goal_text === "string" ? body.goal_text : null,
    budgetCents:
      typeof body.budget_cents === "number" ? body.budget_cents : null,
    source: body.source === "fixture" ? "fixture" : "live",
  };
}
