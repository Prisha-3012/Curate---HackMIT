import { expect, test } from "@playwright/test";
import { fixtures } from "../lib/fixtures";
import { TIMING } from "../lib/demo-data";
import { prepareFixture } from "../lib/plan";
import { money } from "../lib/formatting";

for (const fixture of fixtures) {
  test(`${fixture.id}: complete offline mission flow, dynamic sources, and honest plan`, async ({
    page,
  }) => {
    const errors: string[] = [];
    const forbiddenRequests: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/*", (route) => {
      const url = new URL(route.request().url());
      if (url.hostname !== "127.0.0.1" || url.pathname.startsWith("/api/")) {
        forbiddenRequests.push(url.href);
        return route.abort();
      }
      return route.continue();
    });
    await page.goto(`/?fixture=${fixture.id}`);
    await expect(
      page.getByRole("button", { name: fixture.copy.exampleLabel }),
    ).toBeVisible();
    await expect(
      page.getByRole("navigation", { name: "Demo stage controls" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Let Otto figure it out" }),
    ).toBeDisabled();
    await page.getByRole("button", { name: fixture.copy.exampleLabel }).click();
    await page.getByRole("button", { name: "Let Otto figure it out" }).click();
    await expect(
      page.getByRole("heading", { name: fixture.mission.title }),
    ).toBeVisible();
    if (!fixture.mission.location)
      await expect(page.locator(".constraint-grid")).not.toContainText(
        "Location",
      );
    await page.getByRole("button", { name: "Next" }).click();
    await expect(page.locator(".ladder-title>span")).toHaveText(
      fixture.sources.map((source) => source.label),
    );
    await expect(
      page.locator(".resource-pool .resource-card").first(),
    ).toBeVisible();
    await page.screenshot({
      path: `/tmp/enough-${fixture.id}-scouting-v2.png`,
      fullPage: true,
      animations: "disabled",
    });
    await expect(
      page.getByRole("heading", { name: "Finding the best combination." }),
    ).toBeVisible({ timeout: 10000 });
    await expect(
      page.getByRole("heading", { name: "Here’s your curated plan." }),
    ).toBeVisible();
    const { plan } = prepareFixture(fixture);
    await expect(page.locator(".enough-price .sr-only")).toHaveText(
      money(plan.totalCost),
    );
    await expect(page.locator(".savings-total .sr-only")).toHaveText(
      money(plan.savings),
    );
    await expect(page.locator(".retail-price del")).toHaveText(
      money(plan.retailEquivalent),
    );
    await expect(page.locator(".plan-item")).toHaveCount(plan.items.length);
    await expect(page.locator(".plan-item .resource-visual")).toHaveCount(
      plan.items.filter((item) => item.resource.image).length,
    );
    await expect(page.locator(".unmet-need")).toHaveCount(
      plan.unmetNeedIds.length,
    );
    if (fixture.id === "camping") {
      await expect(
        page.getByText("3 of 4 needs matched. Let’s keep the rest in view."),
      ).toBeVisible();
      await expect(page.locator(".savings-panel")).toContainText(
        "Unmatched needs are not priced",
      );
      await expect(page.locator(".plan-screen")).not.toContainText(
        "finds within one mile",
      );
      await expect(page.locator(".plan-screen")).not.toContainText(
        "Everything you need",
      );
      await expect(page.locator(".plan-screen")).toContainText(
        "Fit check needed",
      );
      await expect(page.locator("main")).not.toContainText(
        /Boston|mattress|desk|chair|three months|3 months/i,
      );
      const image = page.getByRole("img", {
        name: "Illustrated moss-green rechargeable camping lantern",
      });
      await expect(image).toBeVisible();
      expect(
        await image.evaluate(
          (image) => (image as HTMLImageElement).naturalWidth,
        ),
      ).toBeGreaterThan(0);
    }
    await page.waitForTimeout(1000);
    await page.screenshot({
      path: `/tmp/enough-${fixture.id}-plan-v2.png`,
      fullPage: true,
      animations: "disabled",
    });
    expect(errors).toEqual([]);
    expect(forbiddenRequests).toEqual([]);
  });
}

test("camping comparison keeps source order and recommends adequate borrowing over higher scores", async ({
  page,
}) => {
  await page.goto("/?fixture=camping&demoControls=true");
  const controls = page.getByRole("navigation", {
    name: "Demo stage controls",
  });
  await controls
    .getByRole("button", { name: "optimizing", exact: true })
    .click();
  await expect(page.locator(".candidate-grid .source-badge")).toHaveText([
    "BORROW",
    "USED",
    "BUY NEW",
  ]);
  await expect(page.locator(".candidate-grid .match-score")).toHaveText([
    "83% match",
    "86% match",
    "91% match",
  ]);
  await expect(page.locator(".candidate-selected")).toHaveAttribute(
    "data-resource-id",
    "borrowed-tent",
  );
  await expect(page.locator(".selection-reason")).toContainText(
    "Borrowing wins before buying",
  );
  await page.screenshot({
    path: "/tmp/enough-camping-comparison-v2.png",
    fullPage: true,
    animations: "disabled",
  });
});

test("failed image collapses the visual region, including after reset", async ({
  page,
}) => {
  await page.route("**/fixtures/camping-lantern.svg", (route) =>
    route.fulfill({ status: 404, body: "Unavailable" }),
  );
  await page.goto("/?fixture=camping&demoControls=true");
  const controls = page.getByRole("navigation", {
    name: "Demo stage controls",
  });
  await controls.getByRole("button", { name: "plan", exact: true }).click();
  const visual = page.locator(
    '[data-resource-id="camp-lantern"] .resource-visual',
  );
  await expect(visual).toHaveCount(0);
  await page.getByRole("button", { name: "New mission" }).click();
  await controls.getByRole("button", { name: "plan", exact: true }).click();
  await expect(visual).toHaveCount(0);
});

test("reset and fixture change invalidate an outstanding reveal", async ({
  page,
}) => {
  await page.goto("/?demoControls=true");
  await page.getByRole("button", { name: "Set up my room under $500" }).click();
  await page.getByRole("button", { name: "Let Otto figure it out" }).click();
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "New mission" }).click();
  await expect(page.getByRole("textbox", { name: "Your mission" })).toHaveValue(
    /moving to Boston/,
  );
  await page.getByLabel("LOCAL FIXTURE").selectOption("camping");
  await page.waitForTimeout(
    TIMING.search + TIMING.source * 5 + TIMING.optimize + 200,
  );
  await expect(
    page.getByRole("heading", { name: "What are you trying to accomplish?" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Prepare for camping under $60" }),
  ).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Your mission" })).toBeEmpty();
});

for (const fixture of fixtures) {
  test(`${fixture.id}: mobile stage controls, reduced motion, and no overflow`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto(`/?fixture=${fixture.id}&demoControls=true`);
    const controls = page.getByRole("navigation", {
      name: "Demo stage controls",
    });
    for (const stage of [
      "mission",
      "understanding",
      "searching",
      "optimizing",
      "plan",
    ]) {
      await controls.getByRole("button", { name: stage, exact: true }).click();
      await expect(
        controls.getByRole("button", { name: stage, exact: true }),
      ).toHaveAttribute("aria-pressed", "true");
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      if (fixture.id === "camping")
        await expect(page.locator("main")).not.toContainText(
          /Boston|mattress|desk|chair|3 months/i,
        );
    }
    await page.screenshot({
      path: `/tmp/enough-${fixture.id}-mobile-v2.png`,
      fullPage: true,
      animations: "disabled",
    });
  });
}

test("keyboard mission submission remains available", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Set up my room under $500" }).click();
  await page
    .getByRole("textbox", { name: "Your mission" })
    .press("Control+Enter");
  await expect(
    page.getByRole("heading", { name: "A room for your next chapter." }),
  ).toBeVisible();
});
