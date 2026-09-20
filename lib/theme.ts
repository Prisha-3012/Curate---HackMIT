/**
 * Shared by the client hook and by the server-rendered no-flash script in
 * app/layout.tsx. Deliberately NOT a "use client" module: importing a plain
 * constant from one into a server component yields undefined, because Next
 * replaces client modules with a proxy that only exposes components.
 */
export const THEME_STORAGE_KEY = "curate-theme";

export type Theme = "dark" | "light";
