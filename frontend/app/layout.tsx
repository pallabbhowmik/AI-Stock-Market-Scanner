import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import { NavBar } from "./NavBar";

export const metadata: Metadata = {
  title: "AI Stock Scanner – Indian Market",
  description: "AI-powered stock market scanning and prediction platform for the Indian stock market",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-slate-100 antialiased">
        <NavBar />
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">{children}</main>
        <footer className="border-t border-slate-800 bg-slate-900/50">
          <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
            <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-between">
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <span className="text-lg">📈</span>
                <span className="font-semibold text-slate-300">AI Stock Scanner</span>
              </div>
              <div className="flex flex-wrap justify-center gap-4 text-xs text-slate-500">
                <Link href="/help" className="hover:text-slate-300 transition">Help & Guide</Link>
                <span>&middot;</span>
                <span>For educational use only</span>
                <span>&middot;</span>
                <span>Not financial advice</span>
              </div>
              <div className="text-xs text-slate-600">
                Built with AI &middot; NSE Data via Yahoo Finance
              </div>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
