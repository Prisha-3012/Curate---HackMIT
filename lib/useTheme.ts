"use client";

import { useCallback, useEffect, useState } from "react";

import { THEME_STORAGE_KEY, type Theme } from "./theme";

/**
 * Dark is the default. The stored preference is applied by the inline script in
 * app/layout.tsx before first paint; this hook only mirrors what that script
 * already decided, and writes the choice back when it changes.
 *
 * The initial state must equal what the server rendered, so the real value is
 * read from the DOM after mount rather than during render — the same hydration
 * trap useVoiceCapture works around for `supported`.
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const applied = document.documentElement.getAttribute("data-theme");
    setTheme(applied === "light" ? "light" : "dark");
  }, []);

  const toggle = useCallback(() => {
    setTheme((current) => {
      const next: Theme = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try {
        localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch {
        // Private mode / blocked storage. The choice still holds for this page
        // view; it just will not survive a reload.
      }
      return next;
    });
  }, []);

  return { theme, toggle };
}
