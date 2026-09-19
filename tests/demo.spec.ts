import { expect, test } from "@playwright/test";
import { calculatePlan, resources, TIMING } from "../lib/demo-data";

test("plan accounting stays consistent when resource prices change", () => {
  const plan = calculatePlan(resources);
  expect(plan.totalCost).toBe(314);
  expect(plan.retailEquivalent).toBe(731);
  expect(plan.savings).toBe(417);
  expect(plan.newPurchasesAvoided).toBe(7);
  expect(plan.reusedResources).toBe(4);
  expect(plan.nearbyResources).toBe(3);
  const changed = calculatePlan(
    resources.map((r) => (r.id === "desk" ? { ...r, price: r.price + 12 } : r)),
  );
  expect(changed.totalCost).toBe(plan.totalCost + 12);
  expect(changed.savings).toBe(plan.savings - 12);
});

test("complete mission to plan works without external requests", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/*", (route) =>
    new URL(route.request().url()).hostname === "127.0.0.1"
      ? route.continue()
      : route.abort(),
  );
  await page.goto("/");
  await expect(
    page.getByRole("navigation", { name: "Demo stage controls" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Let Otto figure it out" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Set up my room under $500" }).click();
  await page.screenshot({ path: "/tmp/enough-mission.png", fullPage: true });
  await page.getByRole("button", { name: "Let Otto figure it out" }).click();
  await expect(
    page.getByRole("heading", { name: "A room for your next chapter." }),
  ).toBeVisible();
  await expect(page.getByText("Boston, MA", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "/tmp/enough-understanding.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Find a better way" }).click();
  await expect(
    page.getByRole("list", { name: "Resource search hierarchy" }),
  ).toBeVisible();
  await expect(
    page.locator(".ladder-step.active").getByText("CIRCLE", { exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: "/tmp/enough-search.png", fullPage: true });
  await expect(
    page.getByRole("heading", { name: "Finding the best combination." }),
  ).toBeVisible({ timeout: 10000 });
  await page.screenshot({
    path: "/tmp/enough-optimization.png",
    fullPage: true,
  });
  await expect(
    page.getByRole("heading", { name: "Here’s your ENOUGH plan." }),
  ).toBeVisible();
  await expect(page.locator(".enough-price .sr-only")).toHaveText("$314");
  await expect(page.locator(".savings-total .sr-only")).toHaveText("$417");
  await expect(page.locator(".retail-price del")).toHaveText("$731");
  await expect(page.locator(".plan-item")).toHaveCount(8);
  await expect(page.getByText("$186 under your $500 budget")).toBeVisible();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: "/tmp/enough-plan.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("reset invalidates outstanding work and keeps the entered mission", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Set up my room under $500" }).click();
  await page.getByRole("button", { name: "Let Otto figure it out" }).click();
  await page.getByRole("button", { name: "Find a better way" }).click();
  await page.getByRole("button", { name: "Reset demo" }).click();
  await page.waitForTimeout(
    TIMING.search + TIMING.source * 5 + TIMING.optimize + 200,
  );
  await expect(
    page.getByRole("heading", { name: "What are you trying to accomplish?" }),
  ).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Your mission" })).toHaveValue(
    /moving to Boston/,
  );
});

test("demo controls, voice simulation, and mobile layouts", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/?demoControls=true");
  await page.getByRole("button", { name: "Try simulated voice input" }).click();
  await expect(
    page.getByText("Simulated voice input added. No microphone was accessed."),
  ).toBeVisible();
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
  }
  await page.screenshot({
    path: "/tmp/enough-mobile-plan.png",
    fullPage: true,
  });
});
