"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { AuthProvider } from "./AuthProvider";
import { NavBar } from "./NavBar";

export function LayoutShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/login";

  return (
    <AuthProvider>
      {!isLogin && <NavBar />}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 bg-mesh min-h-[calc(100vh-8rem)]">{children}</main>
      {!isLogin && (
        <footer className="border-t border-white/[0.04]">
          <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
            <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-between">
              <div className="flex items-center gap-2.5 text-sm text-slate-400">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500/20 to-purple-500/20 text-xs">📈</span>
                <span className="font-semibold text-slate-300">AI Stock Scanner</span>
              </div>
              <div className="flex flex-wrap justify-center gap-3 text-xs text-slate-500">
                <Link href="/help" className="hover:text-indigo-400 transition">Help &amp; Guide</Link>
                <span className="text-slate-700">&middot;</span>
                <span>Educational use only</span>
                <span className="text-slate-700">&middot;</span>
                <span>Not financial advice</span>
              </div>
              <div className="text-xs text-slate-600">
                Built with AI &middot; NSE Data
              </div>
            </div>
          </div>
        </footer>
      )}
    </AuthProvider>
  );
}
