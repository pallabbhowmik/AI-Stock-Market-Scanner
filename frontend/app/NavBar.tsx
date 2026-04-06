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
    <nav className="sticky top-0 z-40 glass">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-fuchsia-500 text-sm shadow-lg shadow-indigo-500/20 transition-transform group-hover:scale-105">
            📈
          </span>
          <div className="flex flex-col">
            <span className="text-base font-bold text-white tracking-tight hidden sm:block">AI Stock Scanner</span>
            <span className="text-base font-bold text-white sm:hidden">Scanner</span>
            <span className="hidden sm:block text-[10px] font-medium text-indigo-400/70 -mt-0.5 tracking-wide">NSE • INDIAN MARKET</span>
          </div>
        </Link>

        {/* Desktop nav */}
        <div className="hidden items-center gap-0.5 md:flex">
          {NAV_LINKS.map((l) => {
            const active = pathname === l.href;
            const Icon = l.icon;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`relative flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium transition-all duration-200 ${
                  active
                    ? "text-white"
                    : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
                }`}
              >
                {active && (
                  <span className="absolute inset-0 rounded-xl bg-gradient-to-r from-indigo-500/15 to-purple-500/10 border border-indigo-500/20" />
                )}
                <Icon size={15} className={active ? "text-indigo-400" : ""} />
                <span className="relative">{l.label}</span>
              </Link>
            );
          })}
          <div className="ml-1 h-6 w-px bg-white/[0.06]" />
          <button
            onClick={logout}
            className="ml-1 flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-slate-500 transition-all hover:bg-red-500/10 hover:text-red-400"
            title="Sign out"
          >
            <LogOut size={15} />
          </button>
        </div>

        {/* Mobile hamburger */}
        <button
          onClick={() => setOpen(!open)}
          className="rounded-xl p-2 text-slate-400 hover:bg-white/[0.05] hover:text-white md:hidden transition"
          aria-label="Toggle menu"
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="border-t border-white/[0.04] px-4 pb-4 pt-2 md:hidden animate-in">
          {NAV_LINKS.map((l) => {
            const active = pathname === l.href;
            const Icon = l.icon;
            return (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className={`flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition ${
                  active
                    ? "bg-indigo-500/10 text-indigo-400"
                    : "text-slate-400 hover:bg-white/[0.04] hover:text-white"
                }`}
              >
                <Icon size={18} />
                {l.label}
              </Link>
            );
          })}
          <div className="my-2 h-px bg-white/[0.04]" />
          <button
            onClick={() => { setOpen(false); logout(); }}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-slate-400 transition hover:bg-red-500/10 hover:text-red-400"
          >
            <LogOut size={18} />
            Sign Out
          </button>
        </div>
      )}
    </nav>
  );
}
