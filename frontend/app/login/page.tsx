"use client";

import { useState } from "react";
import { useAuth } from "../AuthProvider";
import { useRouter } from "next/navigation";
import { Lock, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const { login, isLoggedIn } = useAuth();
  const router = useRouter();

  // Already logged in — redirect
  if (isLoggedIn) {
    router.replace("/");
    return null;
  }

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      setError("Please enter username and password");
      return;
    }
    const ok = login(username, password);
    if (ok) {
      router.replace("/");
    } else {
      setError("Invalid username or password");
    }
  };

  return (
    <div className="flex min-h-[80vh] items-center justify-center">
      {/* Ambient glow */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/3 h-96 w-96 rounded-full bg-indigo-500/[0.07] blur-[120px]" />
        <div className="absolute bottom-1/4 right-1/3 h-96 w-96 rounded-full bg-purple-500/[0.05] blur-[120px]" />
      </div>

      <div className="relative w-full max-w-sm animate-in">
        <div className="card space-y-7 gradient-border">
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-500 to-fuchsia-500 text-2xl shadow-lg shadow-indigo-500/25">
              📈
            </div>
            <h1 className="text-xl font-bold text-white tracking-tight">AI Stock Scanner</h1>
            <p className="mt-1 text-sm text-slate-400">Sign in to your dashboard</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            {error && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-2.5 text-sm text-red-400">
                {error}
              </div>
            )}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-400">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => { setUsername(e.target.value); setError(""); }}
                className="w-full rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none transition focus:border-indigo-500/40 focus:bg-white/[0.05] focus:ring-1 focus:ring-indigo-500/20"
                placeholder="admin"
                autoComplete="username"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium text-slate-400">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError(""); }}
                className="w-full rounded-xl border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none transition focus:border-indigo-500/40 focus:bg-white/[0.05] focus:ring-1 focus:ring-indigo-500/20"
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
            <button
              type="submit"
              className="btn-primary w-full py-3"
            >
              <Lock size={14} />
              Sign In
              <ArrowRight size={14} className="ml-auto" />
            </button>
          </form>

          <p className="text-center text-xs text-slate-600">
            Personal use only &middot; Not financial advice
          </p>
        </div>
      </div>
    </div>
  );
}
