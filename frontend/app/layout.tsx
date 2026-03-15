import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "AI Stock Scanner – Indian Market",
  description: "AI-powered stock market scanning and prediction platform for the Indian stock market",
};

function Navbar() {
  const links = [
    { href: "/", label: "Dashboard" },
    { href: "/watchlist", label: "Watchlist" },
    { href: "/paper-trading", label: "Paper Trading" },
    { href: "/explorer", label: "Explorer" },
    { href: "/help", label: "Help" },
  ];

  return (
    <nav className="sticky top-0 z-40 border-b border-slate-700 bg-slate-900/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold text-white">
          <span className="text-2xl">📈</span> AI Stock Scanner
        </Link>
        <div className="flex items-center gap-6">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="text-sm text-slate-300 transition hover:text-white"
            >
              {l.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-slate-100 antialiased">
        <Navbar />
        <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
        <footer className="border-t border-slate-800 py-6 text-center text-xs text-slate-500">
          AI Stock Scanner &middot; For personal educational use only &middot; Not financial advice
        </footer>
      </body>
    </html>
  );
}
