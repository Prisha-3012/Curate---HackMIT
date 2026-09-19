/**
 * Speech to text, via the backend's /api/voice/transcribe.
 *
 * The browser never talks to Deepgram directly — that would put the API key in
 * the bundle. The backend holds the key and returns { text }, with the
 * provenance in a header.
 */

export type TranscriptSource = "deepgram" | "fixture" | "unknown";

export interface Transcript {
  text: string;
  /**
   * "fixture" means the backend has no speech credentials and returned the
   * canned demo transcript for whatever was recorded — it is NOT what the
   * person said. Never present it as their words.
   */
  source: TranscriptSource;
}

export async function transcribeAudio(
  baseUrl: string,
  clip: Blob,
  signal?: AbortSignal,
): Promise<Transcript> {
  if (!baseUrl) throw new Error("Backend URL must be configured.");
  const form = new FormData();
  // Field name and extension match what the FastAPI route expects.
  form.append("audio", clip, "mission.webm");

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/voice/transcribe`, {
    method: "POST",
    body: form,
    signal,
  });
  if (!response.ok)
    throw new Error("Otto couldn't hear that. Please try again or type it.");

  const header = response.headers.get("X-Voice-Source");
  const source: TranscriptSource =
    header === "deepgram" || header === "fixture" ? header : "unknown";
  const body = (await response.json()) as { text?: unknown };
  if (typeof body.text !== "string")
    throw new Error("The transcription response was malformed.");
  return { text: body.text, source };
}
