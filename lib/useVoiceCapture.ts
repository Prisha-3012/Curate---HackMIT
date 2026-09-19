"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { transcribeAudio } from "./services/voiceApi";

export type VoiceState = "idle" | "recording" | "transcribing";

/**
 * Hold-to-talk is fiddly on a laptop, so this is a toggle: click to start,
 * click again to stop and transcribe.
 *
 * Everything that can fail here is a normal thing a person does — declining the
 * mic prompt, having no microphone, saying nothing — so each one produces a
 * sentence they can act on rather than an exception.
 */
export function useVoiceCapture({
  baseUrl,
  onTranscript,
  onNotice,
}: {
  baseUrl: string;
  onTranscript: (text: string) => void;
  onNotice: (message: string) => void;
}) {
  const [state, setState] = useState<VoiceState>("idle");
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<BlobPart[]>([]);

  const supported =
    typeof window !== "undefined" &&
    typeof window.MediaRecorder !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia;

  // Release the mic if the component goes away mid-recording, otherwise the
  // browser keeps showing the recording indicator.
  useEffect(() => {
    return () => {
      recorder.current?.stream.getTracks().forEach((t) => t.stop());
      recorder.current = null;
    };
  }, []);

  const stop = useCallback(() => {
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);

  const start = useCallback(async () => {
    if (!supported) {
      onNotice("This browser can't record audio. Type your mission instead.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onNotice(
        "Otto needs microphone access to listen. You can type your mission instead.",
      );
      return;
    }

    chunks.current = [];
    const mr = new MediaRecorder(stream);
    recorder.current = mr;
    mr.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.current.push(e.data);
    };
    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      recorder.current = null;
      const clip = new Blob(chunks.current, { type: mr.mimeType });
      chunks.current = [];
      if (clip.size === 0) {
        setState("idle");
        onNotice("Otto didn't catch anything. Try again, or type your mission.");
        return;
      }
      setState("transcribing");
      try {
        const { text, source } = await transcribeAudio(baseUrl, clip);
        if (!text.trim()) {
          // The backend returns an empty string for silence rather than
          // inventing a goal, so this branch is reachable and honest.
          onNotice("Otto didn't catch anything. Try again, or type your mission.");
        } else if (source === "fixture") {
          // Canned demo text, not what they said. Saying so beats letting them
          // believe their words were understood.
          onTranscript(text);
          onNotice(
            "Speech recognition is unavailable, so this is the demo mission rather than what you said.",
          );
        } else {
          onTranscript(text);
        }
      } catch (error) {
        onNotice(
          error instanceof Error
            ? error.message
            : "Otto couldn't hear that. Please try again or type it.",
        );
      } finally {
        setState("idle");
      }
    };

    mr.start();
    setState("recording");
  }, [baseUrl, onNotice, onTranscript, supported]);

  const toggle = useCallback(() => {
    if (state === "recording") stop();
    else if (state === "idle") void start();
  }, [state, start, stop]);

  return { state, toggle, supported };
}
