"use client";

import { useEffect, useRef } from "react";

/**
 * Decorative blobs behind the mission screen that drift toward the pointer.
 *
 * Fixed to the viewport rather than clipped to the section: a blurred shape cut
 * off by an `overflow: hidden` box shows a hard rectangular edge, and a fixed
 * layer cannot add document scroll width either.
 *
 * It renders the same markup on the server and the client — the pointer
 * position only ever arrives through a CSS custom property set after mount, so
 * there is nothing here to mismatch during hydration.
 */
export function FluidShapes() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = ref.current;
    if (!host) return;
    // Someone who asked for less motion should not get a layer that chases
    // their cursor, so the listener is never attached rather than merely
    // animating to the same place.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let frame = 0;
    function onMove(event: PointerEvent) {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const x = event.clientX / window.innerWidth - 0.5;
        const y = event.clientY / window.innerHeight - 0.5;
        host!.style.setProperty("--px", x.toFixed(3));
        host!.style.setProperty("--py", y.toFixed(3));
      });
    }

    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div className="fluid" ref={ref} aria-hidden="true">
      <span className="fluid-blob fluid-1" />
      <span className="fluid-blob fluid-2" />
      <span className="fluid-blob fluid-3" />
      <span className="fluid-blob fluid-ring" />
    </div>
  );
}
