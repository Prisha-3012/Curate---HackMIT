"use client";
import Image from "next/image";
import { useState } from "react";
import type { Resource } from "@/lib/types";
function hash(value: string) {
  return [...value].reduce(
    (result, char) => (Math.imul(result, 31) + char.charCodeAt(0)) >>> 0,
    17,
  );
}
export function ResourceVisual({
  resource,
  size = "small",
}: {
  resource: Resource;
  size?: "small" | "large";
}) {
  const [failedImage, setFailedImage] = useState<string>();
  const hasImage = Boolean(resource.image && failedImage !== resource.image);
  if (!hasImage) return null;

  const fingerprint = hash(resource.id || resource.name);
  return (
    <div
      className={`resource-visual visual-${size} visual-image`}
      data-visual-key={fingerprint}
      data-visual-kind="image"
    >
      <Image
        src={resource.image!}
        alt={resource.imageAlt ?? resource.name}
        width={240}
        height={220}
        unoptimized
        onError={() => setFailedImage(resource.image)}
      />
    </div>
  );
}
