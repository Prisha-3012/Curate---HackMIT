import { test, expect } from "@playwright/test";
import { scanWardrobe, validateWardrobe } from "../lib/services/wardrobeApi";

test("wardrobe validation rejects malformed or contradictory inventory", () => {
  for (const payload of [
    null,
    {},
    { items: [], count: 1, source: "none" },
    {
      items: [{ title: "Shirt", category: "top", attrs: { color: 3 } }],
      count: 1,
      source: "groq",
    },
    {
      items: [{ title: "Shirt", category: "top", attrs: {} }],
      count: 1,
      source: "fixture",
    },
  ])
    expect(() => validateWardrobe(payload)).toThrow();
  expect(validateWardrobe({ items: [], count: 0, source: "error" })).toEqual({
    items: [],
    count: 0,
    source: "error",
  });
});

test("wardrobe request supports cancellation and timeout", async () => {
  const originalFetch = globalThis.fetch;
  let calls = 0;
  globalThis.fetch = async (_url, init) => {
    calls++;
    return new Promise<Response>((_resolve, reject) => {
      const signal = init?.signal;
      signal?.addEventListener("abort", () => reject(signal.reason), {
        once: true,
      });
    });
  };
  try {
    const image = new File(["photo"], "closet.png", { type: "image/png" });
    const controller = new AbortController();
    controller.abort();
    await expect(
      scanWardrobe("http://test/api", "user", image, controller.signal),
    ).rejects.toHaveProperty("name", "AbortError");
    expect(calls).toBe(0);
    await expect(
      scanWardrobe("http://test/api", "user", image, undefined, 5),
    ).rejects.toHaveProperty("name", "TimeoutError");
    const active = new AbortController();
    const request = scanWardrobe(
      "http://test/api",
      "user",
      image,
      active.signal,
    );
    active.abort();
    await expect(request).rejects.toHaveProperty("name", "AbortError");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
