import { test, expect, type Page, type Route } from "@playwright/test";

const MIC = "button[aria-label='Record your mission']";
const STOP = "button[aria-label='Stop recording']";

/** Stub only the transcription response; the mic and MediaRecorder are real. */
async function stubTranscribe(
  page: Page,
  handler: (route: Route) => Promise<void> | void,
) {
  await page.route("**/api/voice/transcribe", handler);
}

async function record(page: Page) {
  await page.locator(MIC).click();
  await expect(page.locator(STOP)).toBeVisible();
  // Let MediaRecorder actually produce a chunk.
  await page.waitForTimeout(700);
  await page.locator(STOP).click();
}

test("a real transcript fills the mission box and says nothing extra", async ({ page }) => {
  await stubTranscribe(page, (route) =>
    route.fulfill({
      status: 200,
      headers: {
        "X-Voice-Source": "deepgram",
        "Access-Control-Expose-Headers": "X-Voice-Source",
      },
      contentType: "application/json",
      body: JSON.stringify({
        text: "I need business casual clothes for my internship. My budget is $100.",
      }),
    }),
  );
  await page.goto("/");
  await record(page);

  await expect(page.getByLabel("Your mission", { exact: true })).toHaveValue(
    "I need business casual clothes for my internship. My budget is $100.",
    { timeout: 15000 },
  );
  await expect(page.getByText(/didn.t catch|unavailable|couldn.t hear/i)).toHaveCount(0);
});

test("silence is reported honestly instead of inventing a mission", async ({ page }) => {
  // The backend returns "" for silence rather than the hero goal, so this is
  // the state the UI actually receives.
  await stubTranscribe(page, (route) =>
    route.fulfill({
      status: 200,
      headers: {
        "X-Voice-Source": "deepgram",
        "Access-Control-Expose-Headers": "X-Voice-Source",
      },
      contentType: "application/json",
      body: JSON.stringify({ text: "" }),
    }),
  );
  await page.goto("/");
  await record(page);

  await expect(page.getByText(/didn.t catch anything/i)).toBeVisible({ timeout: 15000 });
  await expect(page.getByLabel("Your mission", { exact: true })).toHaveValue("");
});

test("a fixture transcript is labelled, not passed off as what was said", async ({ page }) => {
  await stubTranscribe(page, (route) =>
    route.fulfill({
      status: 200,
      headers: {
        "X-Voice-Source": "fixture",
        // The real server sends this too; without it the browser hides the
        // header cross-origin and provenance silently reads as unknown.
        "Access-Control-Expose-Headers": "X-Voice-Source",
      },
      contentType: "application/json",
      body: JSON.stringify({ text: "business casual for my internship" }),
    }),
  );
  await page.goto("/");
  await record(page);

  await expect(
    page.getByText(/speech recognition is unavailable/i),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.getByLabel("Your mission", { exact: true })).toHaveValue(
    "business casual for my internship",
  );
});

test("a failed transcription tells the user they can type instead", async ({ page }) => {
  await stubTranscribe(page, (route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: "{}" }),
  );
  await page.goto("/");
  await record(page);

  await expect(page.getByText(/couldn.t hear that/i)).toBeVisible({ timeout: 15000 });
});
