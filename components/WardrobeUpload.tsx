"use client";

import { useEffect, useRef, useState } from "react";
import { Camera } from "lucide-react";
import { scanWardrobe, type WardrobeItem } from "@/lib/services/wardrobeApi";

export function WardrobeUpload() {
  const [items, setItems] = useState<WardrobeItem[]>([]);
  const [state, setState] = useState<
    "idle" | "analyzing" | "success" | "empty" | "error"
  >("idle");
  const fileInput = useRef<HTMLInputElement>(null);
  const running = useRef<AbortController | null>(null);
  useEffect(() => () => running.current?.abort(), []);

  async function scan(file: File) {
    running.current?.abort();
    const controller = new AbortController();
    running.current = controller;
    setState("analyzing");
    try {
      const result = await scanWardrobe(
        process.env.NEXT_PUBLIC_API_BASE_URL ?? "",
        process.env.NEXT_PUBLIC_DEMO_USER_ID ?? "",
        file,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      if (result.items.length) {
        setItems(result.items);
        setState("success");
      } else setState("empty");
    } catch {
      if (!controller.signal.aborted) setState("error");
    }
  }

  return (
    <section className="closet-check" aria-label="Closet Check">
      <div className="closet-heading">
        <Camera size={17} />
        <strong>Closet Check</strong>
        <span>Optional</span>
      </div>
      <div role="status" aria-live="polite">
        {state === "idle" && (
          <p>Otto checks your closet before suggesting anything to buy.</p>
        )}
        {state === "analyzing" && <p>Checking your closet…</p>}
        {state === "success" && (
          <p>
            Found {items.length} {items.length === 1 ? "item" : "items"} you
            already own
          </p>
        )}
        {state === "empty" && (
          <p>
            I couldn’t confidently identify any items in that photo. Try another
            photo or continue without Closet Check.
          </p>
        )}
        {state === "error" && (
          <p>
            Closet Check couldn’t finish. Try again or continue with your goal.
          </p>
        )}
        {items.length > 0 && (
          <>
            {state !== "success" && (
              <p>Your previously detected items are still available.</p>
            )}
            <ul className="closet-items">
              {items.map((item, index) => (
                <li key={index}>
                  <strong>{item.title}</strong>
                  <span>{item.category}</span>
                </li>
              ))}
            </ul>
            <p>
              These can now satisfy needs before Otto looks for anything to buy.
            </p>
          </>
        )}
      </div>
      <input
        ref={fileInput}
        className="sr-only"
        type="file"
        accept="image/*"
        aria-label="Closet photo"
        tabIndex={-1}
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file) void scan(file);
        }}
      />
      <button
        type="button"
        className="button secondary"
        disabled={state === "analyzing"}
        onClick={() => fileInput.current?.click()}
      >
        {state === "analyzing"
          ? "Checking your closet…"
          : state === "idle"
            ? "Scan what I already own"
            : "Scan another photo"}
      </button>
      <p className="closet-note">
        A successful scan replaces your previous scan; photos don’t accumulate.
      </p>
    </section>
  );
}
