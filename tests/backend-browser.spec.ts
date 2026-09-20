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
    "USED",
    "NEW",
  ]);
  await expect(
    page.getByRole("heading", { name: "Here’s your curated plan." }),
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

const closetItem = {
  title: "White oxford",
  category: "top",
  attrs: { color: "white", style: "oxford" },
};
const photo = {
  name: "closet.png",
  mimeType: "image/png",
  buffer: Buffer.from("test photo"),
};

test("Closet Check displays detected items without submitting and preserves them after an empty rescan", async ({
  page,
}) => {
  let missions = 0;
  let scans = 0;
  await page.route("**/api/mission", async (route) => {
    missions++;
    await route.abort();
  });
  await page.route("**/api/wardrobe", async (route) => {
    scans++;
    expect(route.request().method()).toBe("POST");
    const body = route.request().postDataBuffer()?.toString() ?? "";
    expect(body).toContain('name="user_id"');
    expect(body).toContain("test-user");
    expect(body).toContain('name="image"; filename="closet.png"');
    await route.fulfill({
      json:
        scans === 1
          ? { items: [closetItem], count: 1, source: "groq" }
          : { items: [], count: 0, source: "error" },
    });
  });
  await page.goto("/");
  await expect(page.locator(".footer-ladder > span")).toHaveText([
    "OWN",
    "USED",
    "NEW",
  ]);
  await page.getByLabel("Closet photo").setInputFiles(photo);
  await expect(page.getByText("Found 1 item you already own")).toBeVisible();
  await expect(page.locator(".closet-items")).toContainText("White oxford");
  await expect(page.getByText(/successful scan replaces/)).toBeVisible();
  expect(missions).toBe(0);
  await page.getByLabel("Closet photo").setInputFiles(photo);
  await expect(page.getByText(/couldn’t confidently identify/)).toBeVisible();
  await expect(page.locator(".closet-items")).toContainText("White oxford");
  expect(missions).toBe(0);
});

for (const failure of ["empty", "network", "malformed"] as const) {
  test(`Closet Check ${failure} remains truthful and does not block mission submission`, async ({
    page,
  }) => {
    let missions = 0;
    await page.route("**/api/wardrobe", async (route) => {
      if (failure === "network") await route.abort();
      else
        await route.fulfill({
          json:
            failure === "empty"
              ? { items: [], count: 0, source: "none" }
              : { items: [closetItem], count: 7, source: "groq" },
        });
    });
    await page.route("**/api/mission", async (route) => {
      missions++;
      await route.fulfill({
        json: {
          mission_id: "closet-test",
          source: "live",
          goal_text: "Prepare for college",
          budget_cents: null,
          needs: [],
          impact: {
            baseline_cents: 0,
            plan_cents: 0,
            saved_cents: 0,
            items_reused: 0,
            textile_kg_avoided: 0,
            assumptions_note: "No matched resources.",
          },
        },
      });
    });
    await page.goto("/");
    await page
      .getByLabel("Your mission", { exact: true })
      .fill("Prepare for college");
    await page.getByLabel("Closet photo").setInputFiles(photo);
    await expect(
      page.getByText(
        failure === "empty"
          ? /couldn’t confidently identify/
          : /Closet Check couldn’t finish/,
      ),
    ).toBeVisible();
    await expect(page.locator(".closet-items")).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Scan another photo" }),
    ).toBeEnabled();
    await page.getByRole("button", { name: "Let Otto figure it out" }).click();
    await expect(
      page.getByRole("heading", { name: "Prepare for college" }),
    ).toBeVisible();
    expect(missions).toBe(1);
  });
}
