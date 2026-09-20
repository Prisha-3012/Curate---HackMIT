import type { Metadata } from "next";
import { Instrument_Serif, Inter } from "next/font/google";
import "./globals.css";
import { THEME_STORAGE_KEY } from "../lib/theme";

// Self-hosted by next/font, so there is no render-blocking request to Google
// and no swap flash. Exposed as variables the token layer reads.
const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  display: "swap",
  variable: "--font-serif",
});
const sans = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

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
      className={`${serif.variable} ${sans.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: noFlashTheme }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
