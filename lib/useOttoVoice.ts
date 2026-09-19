"use client";
import { useCallback, useEffect, useRef } from "react";

/**
 * Plays Otto's turns through the backend's /api/voice/speak.
 *
 * Browsers block audio until the person has interacted with the page. The
 * button that starts the conversation is that interaction, so everything after
 * it is allowed to play. A blocked play() is swallowed rather than surfaced —
 * the same words are already on screen, so failing loudly would be noise.
 */
export function useOttoVoice(baseUrl: string) {
  const current = useRef<HTMLAudioElement | null>(null);
  const url = useRef<string | null>(null);

  const stop = useCallback(() => {
    current.current?.pause();
    current.current = null;
    if (url.current) {
      URL.revokeObjectURL(url.current);
      url.current = null;
    }
  }, []);

  useEffect(() => stop, [stop]);

  const speak = useCallback(
    async (text: string) => {
      if (!baseUrl || !text.trim()) return;
      stop(); // never let two turns talk over each other
      try {
        const response = await fetch(`${baseUrl.replace(/\/$/, "")}/voice/speak`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        });
        if (!response.ok) return;
        const blob = await response.blob();
        if (blob.size === 0) return;
        const src = URL.createObjectURL(blob);
        url.current = src;
        const audio = new Audio(src);
        current.current = audio;
        await audio.play();
      } catch {
        // Autoplay refused, offline, or no speech credentials. The text is on
        // screen either way.
      }
    },
    [baseUrl, stop],
  );

  return { speak, stop };
}
