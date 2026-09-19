import { test, expect } from "@playwright/test";
import { validatePlan } from "../lib/api/validatePlan";
import { adaptBackendPlan } from "../lib/api/adaptBackendPlan";
import { money } from "../lib/formatting";

for (const budget of [null, 15000, 3000, 0]) {
  test(`real backend: budget ${budget === null ? "unstated" : budget}`, async ({
    page,
    request,
  }, testInfo) => {
    const health = await (
      await request.get("http://127.0.0.1:8000/health")
    ).json();
    expect(health.demo_mode).toBe("off");
    const input = `business casual for my internship${budget === null ? "" : ` with a $${budget / 100} budget`}`;
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    let calls = 0;
    page.on("request", (r) => {
      if (r.method() === "POST" && r.url().endsWith("/api/mission")) calls++;
    });
    await page.goto("/");
    await page.getByLabel("Your mission", { exact: true }).fill(input);
    const responsePromise = page.waitForResponse(
      (r) =>
        r.request().method() === "POST" &&
        r.url() === "http://127.0.0.1:8000/api/mission",
    );
    await page.getByRole("button", { name: "Let Otto figure it out" }).click();
    const response = await responsePromise;
    expect(response.ok()).toBe(true);
    const payload = response.request().postDataJSON();
    expect(payload).toEqual({
      user_id: "00000000-0000-0000-0000-000000000001",
      goal_text: input,
      budget_cents: budget,
    });
    const plan = validatePlan(await response.json());
    expect(plan.budget_cents).toBe(budget);
    expect(plan.source).toBe("fixture");
    const experience = adaptBackendPlan(plan, input);
    expect(experience.provenance).toBe("backend-demo");
    expect(experience.mission.needs.map((n) => n.id)).toEqual(
      plan.needs.map((n) => n.need_id),
    );
    for (const [index, need] of plan.needs.entries()) {
      const mapped = experience.mission.needs[index];
      expect(mapped.options.map((o) => o.id)).toEqual(
        need.options.map((o) => o.listing_id),
      );
      expect(mapped.recommendedOptionId).toBe(need.recommended_listing_id);
      expect(mapped.unmetReason).toBe(need.unmet_reason ?? undefined);
      expect(mapped.category).toBeUndefined();
      for (const option of mapped.options)
        expect(option.distanceMiles).toBeUndefined();
    }
    expect(experience.mission.location).toBeUndefined();
    expect(experience.mission.duration).toBeUndefined();
    expect(experience.mission.preferences).toBeUndefined();
    expect(experience.plan.nearbyResources).toBeUndefined();
    await expect(
      page.locator(".understanding-screen .demo-note"),
    ).toContainText("Backend fixture/demo data");
    await expect(page.locator(".constraint-grid")).toContainText(
      budget === null ? "Not stated" : money(budget / 100),
    );
    await page.getByRole("button", { name: "Find a better way" }).click();
    await expect(page.locator(".ladder-title>span")).toHaveText([
      "OWN",
      "BORROW",
      "USED",
      "NEW",
    ]);
    await expect(page.locator(".plan-screen")).toBeVisible({ timeout: 15000 });
    const chosen = plan.needs.flatMap((n) =>
      n.options.filter((o) => o.listing_id === n.recommended_listing_id),
    );
    expect(
      await page
        .locator(".plan-item")
        .evaluateAll((nodes) =>
          nodes.map((n) => n.getAttribute("data-resource-id")),
        ),
    ).toEqual(chosen.map((o) => o.listing_id));
    const unmet = plan.needs.filter((n) => n.recommended_listing_id === null);
    await expect(page.locator(".unmet-need")).toHaveCount(unmet.length);
    for (const [index, need] of unmet.entries()) {
      await expect(page.locator(".unmet-need").nth(index)).toContainText(
        need.unmet_reason!,
      );
      expect(
        await page
          .locator(".unmet-need")
          .nth(index)
          .locator(".resource-card")
          .evaluateAll((nodes) =>
            nodes.map((n) => n.getAttribute("data-resource-id")),
          ),
      ).toEqual(need.options.map((o) => o.listing_id));
    }
    await expect(page.locator(".enough-price .sr-only")).toHaveText(
      money(plan.impact.plan_cents / 100),
    );
    await expect(page.locator(".retail-price")).toContainText(
      money(plan.impact.baseline_cents / 100),
    );
    await expect(page.locator(".savings-total .sr-only")).toHaveText(
      money(plan.impact.saved_cents / 100),
    );
    await expect(page.locator(".plan-screen")).not.toContainText(
      /NaN|Infinity|YOUR MISSION, MADE POSSIBLE|finds within one mile/,
    );
    if (budget === null) {
      await expect(page.locator(".budget-status")).toHaveText(
        "No budget stated",
      );
      await expect(page.getByRole("meter")).toHaveCount(0);
    }
    if (budget === 0)
      expect(chosen.every((o) => o.price_cents === 0)).toBe(true);
    expect(unmet.length).toBe(budget === 0 || budget === 3000 ? 1 : 0);
    expect(calls).toBe(1);
    expect(errors).toEqual([]);
    await testInfo.attach("actual-request-and-response", {
      body: JSON.stringify({ payload, plan }, null, 2),
      contentType: "application/json",
    });
    await page.screenshot({
      path: `/tmp/enough-real-stack-${budget ?? "null"}.png`,
      fullPage: true,
      animations: "disabled",
    });
  });
}
