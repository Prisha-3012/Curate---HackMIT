import { test, expect } from "@playwright/test";
test("single backend response drives every stage and preserves budget-unmet candidates", async ({
  page,
}) => {
  let calls = 0;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("http://127.0.0.1:8000/api/mission", async (route) => {
    calls++;
    expect(route.request().postDataJSON().budget_cents).toBe(0);
    await route.fulfill({
      json: {
        mission_id: "dinner",
        source: "fixture",
        goal_text: "Host dinner",
        budget_cents: 0,
        needs: [
          {
            need_id: "plates",
            label: "Plates",
            rationale: "Serve guests",
            priority: 1,
            recommended_listing_id: null,
            unmet_reason: "Available but outside the budget",
            options: [
              {
                listing_id: "used",
                title: "Secondhand plates",
                rung: "USED",
                owner_label: "Neighbor",
                price_cents: 1250,
                retail_cents: 2500,
                match_score: 0.8,
                why: "Suitable plates",
                needs_fitcheck: false,
              },
            ],
          },
        ],
        impact: {
          baseline_cents: 0,
          plan_cents: 0,
          saved_cents: 0,
          items_reused: 0,
          textile_kg_avoided: 0,
          assumptions_note: "Unmatched needs are excluded.",
        },
      },
    });
  });
  await page.goto("/");
  await page
    .getByLabel("Your mission", { exact: true })
    .fill("Host dinner for $0");
  await page.getByRole("button", { name: "Let Otto figure it out" }).click();
  await expect(
    page.getByRole("heading", { name: "Host dinner" }),
  ).toBeVisible();
  await expect(page.locator(".demo-note")).toContainText(
    "Backend fixture/demo data",
  );
  await page.getByRole("button", { name: "Find a better way" }).click();
  await expect(page.locator(".ladder-title>span")).toHaveText([
    "OWN",
    "BORROW",
    "USED",
    "NEW",
  ]);
  await expect(
    page.getByRole("heading", { name: "Here’s your ENOUGH plan." }),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.locator(".plan-intro")).toContainText(
    "0 of 1 sample needs matched",
  );
  await expect(page.locator(".unmet-need")).toContainText(
    "Available but outside the budget",
  );
  await expect(page.locator(".unmet-need")).toContainText("Secondhand plates");
  await expect(
    page.locator('[data-selected="true"], [data-recommended="true"]'),
  ).toHaveCount(0);
  await expect(page.locator(".savings-panel")).not.toContainText(
    /NaN|Infinity/,
  );
  expect(calls).toBe(1);
  expect(errors).toEqual([]);
});
