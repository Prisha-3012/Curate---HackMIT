/**
 * Wardrobe upload, via the backend's POST /api/wardrobe.
 *
 * The photo never goes to a vision provider from the browser — that would put an
 * API key in the bundle. The backend holds the key, detects the items, and
 * remembers them for this user, so the very next mission prefers the closet and
 * skips buying duplicates of it. Nothing needs to be threaded through the mission
 * call; it is keyed on the same user_id.
 */

export interface WardrobeItem {
  category: string;
  title: string;
  attrs: Record<string, string>;
}

export interface WardrobeResult {
  items: WardrobeItem[];
  count: number;
  /**
   * "fixture" means no vision key was set and this is a SAMPLE closet, not what
   * was in the photo. Say so rather than letting them think the photo was read.
   */
  source: string;
}

export async function uploadWardrobe(
  baseUrl: string,
  userId: string,
  file: File,
  signal?: AbortSignal,
): Promise<WardrobeResult> {
  if (!baseUrl) throw new Error("Backend URL must be configured.");
  const form = new FormData();
  form.append("user_id", userId);
  form.append("image", file, file.name);

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/wardrobe`, {
    method: "POST",
    body: form,
    signal,
  });
  if (!response.ok)
    throw new Error("Otto couldn't read that photo. Try a clearer wardrobe shot.");

  const body = (await response.json()) as Partial<WardrobeResult>;
  if (!Array.isArray(body.items))
    throw new Error("The wardrobe response was malformed.");
  return {
    items: body.items as WardrobeItem[],
    count: typeof body.count === "number" ? body.count : body.items.length,
    source: typeof body.source === "string" ? body.source : "unknown",
  };
}
