import { expect, test } from "@playwright/test";

const TOGGLE_TO_LIGHT = "button[aria-label='Switch to light theme']";
const TOGGLE_TO_DARK = "button[aria-label='Switch to dark theme']";

test("the page opens dark", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator(TOGGLE_TO_LIGHT)).toBeVisible();
});

test("the choice survives a reload, in both directions", async ({ page }) => {
  await page.goto("/");

  await page.locator(TOGGLE_TO_LIGHT).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

  await page.reload();
  // The inline script must apply this before first paint, so it is already
  // correct by the time anything is visible.
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.locator(TOGGLE_TO_DARK)).toBeVisible();

  await page.locator(TOGGLE_TO_DARK).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("switching themes does not warn about hydration", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });

  await page.goto("/");
  await page.locator(TOGGLE_TO_LIGHT).click();
  await page.reload();
  await expect(page.locator(TOGGLE_TO_DARK)).toBeVisible();

  expect(errors.filter((e) => /hydrat/i.test(e))).toEqual([]);
});

test("both themes actually repaint the page", async ({ page }) => {
  await page.goto("/");
  const background = () =>
    page.evaluate(() => getComputedStyle(document.body).backgroundColor);

  const dark = await background();
  await page.locator(TOGGLE_TO_LIGHT).click();
  // Let the crossfade finish before sampling.
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.waitForTimeout(400);
  const light = await background();

  expect(dark).not.toEqual(light);
  // Sanity: the dark page is genuinely darker than the light one.
  const luminance = (rgb: string) =>
    (rgb.match(/\d+/g) ?? []).slice(0, 3).reduce((a, b) => a + Number(b), 0);
  expect(luminance(dark)).toBeLessThan(luminance(light));
});
