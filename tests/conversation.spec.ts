import { test, expect, type Page } from "@playwright/test";

/**
 * Drives the spoken front door against a REAL backend on :8000 with
 * DEMO_MODE=off. Audio playback is stubbed — headless Chrome has no speakers
 * and /api/voice/speak is already covered server side.
 */
async function silenceOtto(page: Page) {
  await page.route("**/api/voice/speak", (route) =>
    route.fulfill({ status: 200, contentType: "audio/mpeg", body: "" }),
  );
}

test("a typed conversation reaches a real plan", async ({ page, request }) => {
  const health = await (await request.get("http://127.0.0.1:8000/health")).json();
  expect(health.demo_mode).toBe("off");

  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await silenceOtto(page);

  await page.goto("/");
  await page.getByRole("button", { name: /talk to otto/i }).click();

  // Otto opens the conversation.
  const log = page.getByRole("log");
  await expect(log).toContainText(/\?/, { timeout: 20000 });

  const answer = page.getByLabel("Your answer", { exact: true });
  await answer.fill("business casual for my internship");
  await page.getByRole("button", { name: /^send/i }).click();

  // Second turn: whatever Otto asks, answering with a budget must finish.
  await expect(answer).toBeVisible({ timeout: 20000 });
  await answer.fill("about one hundred dollars");
  await page.getByRole("button", { name: /^send/i }).click();

  // Conversation hands off to /api/mission and the plan renders.
  await expect(
    page.getByRole("button", { name: /find a better way/i }),
  ).toBeVisible({ timeout: 40000 });
  await page.getByRole("button", { name: /find a better way/i }).click();
  await expect(page.getByText(/here.s your/i)).toBeVisible({ timeout: 40000 });

  const body = await page.locator("body").innerText();
  expect(body).not.toMatch(/NaN|Infinity|undefined/);
  expect(errors).toHaveLength(0);
});

test("the budget gathered by talking reaches the backend", async ({ page }) => {
  await silenceOtto(page);
  const missions: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().endsWith("/api/mission"))
      missions.push(r.postData() ?? "");
  });

  await page.goto("/");
  await page.getByRole("button", { name: /talk to otto/i }).click();
  const answer = page.getByLabel("Your answer", { exact: true });
  await expect(answer).toBeVisible({ timeout: 20000 });

  // The budget goes in the FIRST answer. A live model decides for itself how
  // many questions to ask — sometimes none — so a test that assumes a second
  // turn is testing the model's mood, not the plumbing. What must hold either
  // way is that a plainly-spoken amount reaches the backend as cents.
  await answer.fill("a camping trip for five people, about eighty dollars");
  await page.getByRole("button", { name: /^send/i }).click();

  // Answer any follow-ups neutrally; the budget is already on the record and
  // the server re-derives it from every user turn.
  //
  // Each send must wait for Otto to finish the previous turn. Sending straight
  // away races the disabled Send button and then the whole block unmounts the
  // moment the conversation completes, so the click retries into a detached
  // element.
  for (let i = 0; i < 3 && missions.length === 0; i++) {
    const send = page.getByRole("button", { name: /^send/i });
    try {
      await answer.fill("that's everything", { timeout: 5000 });
      await expect(send).toBeEnabled({ timeout: 15000 });
      await send.click({ timeout: 5000 });
    } catch {
      break; // conversation finished and the answer block went away
    }
  }

  await expect
    .poll(() => missions.length, { timeout: 40000 })
    .toBeGreaterThan(0);
  const sent = JSON.parse(missions[0]);
  // No dollar sign anywhere in what was typed.
  expect(sent.budget_cents).toBe(8000);
  expect(sent.goal_text.toLowerCase()).toContain("camping");
});

test("you can back out to typing", async ({ page }) => {
  await silenceOtto(page);
  await page.goto("/");
  await page.getByRole("button", { name: /talk to otto/i }).click();
  await expect(page.getByRole("log")).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: /type it instead/i }).click();
  await expect(page.getByLabel("Your mission", { exact: true })).toBeVisible();
});
