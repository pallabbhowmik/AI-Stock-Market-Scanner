import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import { LayoutShell } from "./LayoutShell";

export const metadata: Metadata = {
  title: "AI Stock Scanner – Indian Market",
  description: "AI-powered stock market scanning and prediction platform for the Indian stock market",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-slate-100 antialiased">
        <LayoutShell>{children}</LayoutShell>
      </body>
    </html>
  );
}
