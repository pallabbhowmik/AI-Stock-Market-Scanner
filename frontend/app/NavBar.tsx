"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  ListChecks,
  Search,
  Wallet,
  HelpCircle,
  Menu,
  X,
  LogOut,
} from "lucide-react";
import { useAuth } from "./AuthProvider";

const NAV_LINKS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/watchlist", label: "Watchlist", icon: ListChecks },
  { href: "/explorer", label: "Explorer", icon: Search },
  { href: "/paper-trading", label: "Paper Trading", icon: Wallet },
  { href: "/help", label: "Help", icon: HelpCircle },
];

export function NavBar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { logout } = useAuth();

  return (
    <nav className="sticky top-0 z-40 border-b border-slate-700/80 bg-slate-900/95 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 text-lg font-bold text-white">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 text-sm">
            📈
          </span>
          <span className="hidden sm:inline">AI Stock Scanner</span>
          <span className="sm:hidden">Scanner</span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((l) => {
            const active = pathname === l.href;
            const Icon = l.icon;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
                  active
                    ? "bg-accent/15 text-accent"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icon size={16} />
                {l.label}
              </Link>
            );
          })}
          <button
            onClick={logout}
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-400 transition-all hover:bg-red-900/20 hover:text-red-400"
            title="Sign out"
          >
            <LogOut size={16} />
          </button>
        </div>

        {/* Mobile hamburger */}
        <button
          onClick={() => setOpen(!open)}
          className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white md:hidden"
          aria-label="Toggle menu"
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="border-t border-slate-700/50 bg-slate-900 px-4 pb-4 pt-2 md:hidden">
          {NAV_LINKS.map((l) => {
            const active = pathname === l.href;
            const Icon = l.icon;
            return (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className={`flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium transition ${
                  active
                    ? "bg-accent/15 text-accent"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"
                }`}
              >
                <Icon size={18} />
                {l.label}
              </Link>
            );
          })}
          <button
            onClick={() => { setOpen(false); logout(); }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium text-slate-400 transition hover:bg-red-900/20 hover:text-red-400"
          >
            <LogOut size={18} />
            Sign Out
          </button>
        </div>
      )}
    </nav>
  );
}
