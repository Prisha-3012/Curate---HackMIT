import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "ENOUGH — Use what exists. Buy what matters.",
  description: "Tell Otto the goal. Find a better way to make it happen.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
