import type { Metadata } from "next";

import "./globals.css";

import { ThemeScript } from "./theme-script";

export const metadata: Metadata = {
  title: "llmh",
  description: "wireframe frontend for llmh",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <ThemeScript />
        {children}
      </body>
    </html>
  );
}
