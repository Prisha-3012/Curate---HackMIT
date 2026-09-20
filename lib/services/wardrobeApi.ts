export interface WardrobeItem {
  category: string;
  title: string;
  attrs: Record<string, string>;
}
export interface WardrobeResponse {
  items: WardrobeItem[];
  count: number;
  source: string;
}

export function validateWardrobe(value: unknown): WardrobeResponse {
  const invalid = () =>
    new Error(
      "Closet Check returned an unreadable response. Please try again.",
    );
  if (!value || typeof value !== "object") throw invalid();
  const data = value as Record<string, unknown>;
  if (
    !Array.isArray(data.items) ||
    data.count !== data.items.length ||
    typeof data.source !== "string" ||
    !data.source.trim()
  )
    throw invalid();
  const items = data.items.map((value: unknown): WardrobeItem => {
    if (!value || typeof value !== "object") throw invalid();
    const item = value as Record<string, unknown>;
    if (
      typeof item.category !== "string" ||
      !item.category.trim() ||
      typeof item.title !== "string" ||
      !item.title.trim() ||
      !item.attrs ||
      typeof item.attrs !== "object" ||
      Array.isArray(item.attrs) ||
      Object.values(item.attrs).some((attr) => typeof attr !== "string")
    )
      throw invalid();
    return {
      category: item.category,
      title: item.title,
      attrs: item.attrs as Record<string, string>,
    };
  });
  if (items.length && ["none", "error", "fixture"].includes(data.source))
    throw invalid();
  return { items, count: items.length, source: data.source };
}

export async function scanWardrobe(
  baseUrl: string,
  userId: string,
  image: File,
  signal?: AbortSignal,
  timeoutMs = 60000,
): Promise<WardrobeResponse> {
  if (!baseUrl || !userId)
    throw new Error("Closet Check needs a configured backend and user ID.");
  const controller = new AbortController();
  const abort = () => controller.abort(signal?.reason);
  if (signal?.aborted) abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(
    () =>
      controller.abort(
        new DOMException(
          "Closet Check timed out. Try again or continue with your goal.",
          "TimeoutError",
        ),
      ),
    timeoutMs,
  );
  try {
    controller.signal.throwIfAborted();
    const form = new FormData();
    form.append("user_id", userId);
    form.append("image", image);
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/wardrobe`, {
      method: "POST",
      body: form,
      signal: controller.signal,
    });
    if (!response.ok)
      throw new Error(
        "Closet Check couldn't connect. Try again or continue with your goal.",
      );
    const result = validateWardrobe(await response.json());
    controller.signal.throwIfAborted();
    return result;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}
