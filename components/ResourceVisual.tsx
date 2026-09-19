"use client";
import Image from "next/image";
import { useState } from "react";
import type { CSSProperties } from "react";
import type { Resource, VisualMotif } from "@/lib/types";
const motifs: VisualMotif[] = [
  "fold",
  "frame",
  "vessel",
  "beam",
  "shelter",
  "stack",
];
function hash(value: string) {
  return [...value].reduce(
    (result, char) => (Math.imul(result, 31) + char.charCodeAt(0)) >>> 0,
    17,
  );
}
function Illustration({ motif }: { motif: VisualMotif }) {
  switch (motif) {
    case "shelter":
      return (
        <>
          <path d="m16 65 35-48 34 48Z" fill="currentColor" opacity=".25" />
          <path d="m16 65 35-48 34 48H16Zm35-48v48m0-36-21 36m21-36 19 36" />
          <path d="m15 66-6 6m76-6 6 6" />
        </>
      );
    case "frame":
      return (
        <>
          <path d="m17 30 45-9 22 12-45 11Z" fill="currentColor" opacity=".2" />
          <path d="m17 30 45-9 22 12-45 11-22-14Zm0 0v32m22-18v30m45-41v30M62 21v10M20 55l16 10m7-2 37-9" />
        </>
      );
    case "vessel":
      return (
        <>
          <path
            d="M24 33h45v25c0 23-45 23-45 0Z"
            fill="currentColor"
            opacity=".2"
          />
          <path d="M24 33h45v25c0 23-45 23-45 0V33Zm45 6h8c18 0 17 24-8 22M34 25c-8-8 7-8 0-16m17 16c-8-8 7-8 0-16" />
        </>
      );
    case "beam":
      return (
        <>
          <path d="m36 23 28-6 15 25-51 9Z" fill="currentColor" opacity=".22" />
          <path d="m36 23 28-6 15 25-51 9 8-28Zm17 25v22m-17 5c0-10 35-10 35 0m-42 0h47M49 17l8-2" />
        </>
      );
    case "stack":
      return (
        <>
          <path
            d="m17 49 37-14 29 15v22L47 84 17 68Z"
            fill="currentColor"
            opacity=".18"
          />
          <path d="m17 49 37-14 29 15-36 13-30-14Zm0 0v19l30 16 36-12V50M47 63v21M23 33l34-13 25 13-33 12-26-12Zm0 0v11m26 1v8m33-20v10" />
        </>
      );
    default:
      return (
        <>
          <path
            d="m22 29 40-11 19 37-40 14-22-20Z"
            fill="currentColor"
            opacity=".21"
          />
          <path d="m22 29 40-11 19 37-40 14-22-20 3-20Zm0 0 24 18 35 8M46 47l-5 22M28 65l16 12 36-12" />
        </>
      );
  }
}
export function ResourceVisual({
  resource,
  needLabel,
  size = "small",
}: {
  resource: Resource;
  needLabel?: string;
  size?: "small" | "large";
}) {
  const [failedImage, setFailedImage] = useState<string>();
  const fingerprint = hash(resource.id || needLabel || resource.name);
  const motif = resource.visual ?? motifs[fingerprint % motifs.length];
  const hasImage = Boolean(resource.image && failedImage !== resource.image);
  const initials = resource.name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
  return (
    <div
      className={`resource-visual visual-${size} visual-tone-${fingerprint % 3} ${hasImage ? "visual-image" : "visual-tag"}`}
      data-visual-key={fingerprint}
      data-visual-kind={hasImage ? "image" : motif}
      style={{ "--tag-tilt": `${(fingerprint % 5) - 2}deg` } as CSSProperties}
    >
      {hasImage ? (
        <Image
          src={resource.image!}
          alt={resource.imageAlt ?? resource.name}
          width={240}
          height={220}
          unoptimized
          onError={() => setFailedImage(resource.image)}
        />
      ) : (
        <div className="inventory-tag" aria-hidden="true">
          <span className="tag-punch" />
          <svg
            viewBox="0 0 100 90"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.7"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <Illustration motif={motif} />
          </svg>
          <span className="tag-code">
            {initials}
            <i>{(fingerprint % 1000).toString().padStart(3, "0")}</i>
          </span>
        </div>
      )}
    </div>
  );
}
