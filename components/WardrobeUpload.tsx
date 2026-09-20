"use client";
import { useRef, useState } from "react";
import { Camera, Check, Loader2 } from "lucide-react";
import { uploadWardrobe, type WardrobeItem } from "@/lib/services/wardrobeApi";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const USER = process.env.NEXT_PUBLIC_DEMO_USER_ID ?? "";

/**
 * Optional first step on the mission screen: upload a photo of your closet.
 *
 * The backend detects what you own and remembers it, so the plan that follows
 * prefers your wardrobe and stops recommending things you already have. Skipping
 * this is fine — the plan just falls back to the seeded closet.
 */
export function WardrobeUpload() {
  const [state, setState] = useState<"idle" | "analyzing" | "done" | "error">("idle");
  const [items, setItems] = useState<WardrobeItem[]>([]);
  const [source, setSource] = useState("");
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // let the same file be re-picked after an error
    if (!file) return;
    setState("analyzing");
    setError("");
    try {
      const result = await uploadWardrobe(BASE, USER, file);
      setItems(result.items);
      setSource(result.source);
      setState("done");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Upload failed.");
      setState("error");
    }
  }

  return (
    <div
      style={{
        maxWidth: 640,
        margin: "1.5rem auto 0",
        padding: "1rem 1.25rem",
        border: "1px solid rgba(0,0,0,0.12)",
        borderRadius: 16,
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
        <button
          type="button"
          className="button"
          onClick={() => inputRef.current?.click()}
          disabled={state === "analyzing"}
          style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem" }}
        >
          {state === "analyzing" ? (
            <Loader2 size={16} className="spin" />
          ) : state === "done" ? (
            <Check size={16} />
          ) : (
            <Camera size={16} />
          )}
          {state === "analyzing"
            ? "Reading your closet…"
            : state === "done"
              ? "Wardrobe added — upload another?"
              : "Add a photo of your wardrobe"}
        </button>
        <span style={{ fontSize: "0.85rem", opacity: 0.65 }}>
          Optional. We recommend around what you already own.
        </span>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          onChange={onPick}
          style={{ display: "none" }}
        />
      </div>

      {error && (
        <p className="notice-banner" role="status" style={{ margin: 0 }}>
          {error}
        </p>
      )}

      {state === "done" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <span style={{ fontSize: "0.9rem" }}>
            Found <strong>{items.length}</strong> item{items.length === 1 ? "" : "s"} in
            your closet. Otto will avoid recommending these.
          </span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
            {items.map((it, i) => (
              <span
                key={i}
                style={{
                  fontSize: "0.8rem",
                  padding: "0.2rem 0.6rem",
                  borderRadius: 999,
                  background: "rgba(0,0,0,0.06)",
                }}
              >
                {it.title || it.category}
              </span>
            ))}
          </div>
          {source === "fixture" && (
            <p className="demo-note" style={{ margin: 0 }}>
              No vision key set, so this is a sample closet, not your photo. Add a
              GEMINI_API_KEY to the backend .env for real detection.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
