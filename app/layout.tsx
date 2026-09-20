import type { Metadata } from "next";
import "./globals.css";
import { THEME_STORAGE_KEY } from "../lib/theme";

export const metadata: Metadata = {
  title: "Curate — Use what exists. Buy what matters.",
  description: "Tell Otto the goal. Find a better way to make it happen.",
};

// Runs before first paint so a viewer who chose light does not get a dark
// flash (or the reverse). Anything that reads storage after hydration is too
// late — React has already painted by then. Storage throws in private mode, so
// every access is guarded; failing here just means the default theme stands.
const noFlashTheme = `(function(){try{var t=localStorage.getItem(${JSON.stringify(
  THEME_STORAGE_KEY,
)});if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // suppressHydrationWarning: the script above mutates data-theme before
    // React hydrates, so the server and client attributes legitimately differ.
    <html
      lang="en"
      data-theme="dark"
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: noFlashTheme }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
