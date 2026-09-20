"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/useTheme";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";
  const label = dark ? "Switch to light theme" : "Switch to dark theme";

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={label}
      title={label}
      aria-pressed={dark}
    >
      {dark ? <Sun size={14} /> : <Moon size={14} />}
    </button>
  );
}
