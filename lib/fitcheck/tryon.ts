/**
 * Client-side virtual try-on via the IDM-VTON Hugging Face Space.
 *
 * Calls the Space's gradio API straight from the browser with @gradio/client
 * (loaded from a CDN at runtime), so it needs no backend and ships on Vercel.
 * Mirrors the Python cv/tryon_hf.py call: /tryon with is_checked + is_checked_crop.
 *
 * Requires NEXT_PUBLIC_HF_TOKEN for usable ZeroGPU quota. That token is PUBLIC
 * (it ships in the bundle) — use a disposable token and revoke it after the demo.
 * ~30-60s per render; the Space can queue or rate-limit.
 */

const GRADIO_CDN = "https://cdn.jsdelivr.net/npm/@gradio/client@1/+esm";
const SPACE = "yisol/IDM-VTON";

export class TryOnError extends Error {}

/** Turn a data: URL (the captured frame) into a Blob for upload. */
export async function dataUrlToBlob(dataUrl: string): Promise<Blob> {
  const res = await fetch(dataUrl);
  return res.blob();
}

export async function tryOn(
  personBlob: Blob,
  garmentUrl: string,
  description: string,
): Promise<string> {
  const token = process.env.NEXT_PUBLIC_HF_TOKEN;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let mod: any;
  try {
    mod = await import(/* webpackIgnore: true */ GRADIO_CDN);
  } catch {
    throw new TryOnError("Couldn't load the try-on client. Check your connection and retry.");
  }
  const Client = mod.Client;

  // The garment photo has to be a Blob to upload; some CDNs block cross-origin
  // fetches, which surfaces as a clear message rather than a silent failure.
  let garmentBlob: Blob;
  try {
    const r = await fetch(garmentUrl, { mode: "cors" });
    if (!r.ok) throw new Error(String(r.status));
    garmentBlob = await r.blob();
  } catch {
    throw new TryOnError("Couldn't fetch the garment image for try-on (the retailer blocked it). Try a different garment.");
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let client: any;
  try {
    client = await Client.connect(SPACE, token ? ({ hf_token: token } as never) : undefined);
  } catch {
    throw new TryOnError("Couldn't reach the try-on model. It may be starting up or rate-limited — try again in a moment.");
  }

  let result: unknown;
  try {
    result = await client.predict("/tryon", [
      { background: personBlob, layers: [], composite: null },
      garmentBlob,
      description,
      true, // is_checked (use auto mask)
      true, // is_checked_crop
      30, // denoise steps
      42, // seed
    ]);
  } catch {
    throw new TryOnError("The try-on didn't finish — the GPU Space likely queued or hit its free quota. Wait a bit and retry.");
  }

  // result.data[0] is the rendered image (a gradio FileData with a url).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const data = (result as any)?.data;
  const first = Array.isArray(data) ? data[0] : undefined;
  const url = first?.url ?? first?.path ?? (Array.isArray(first) ? first[0]?.url : undefined);
  if (typeof url !== "string") {
    throw new TryOnError("The try-on returned no image. Try again.");
  }
  return url;
}
