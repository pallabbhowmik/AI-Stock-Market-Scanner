"use client";

import { useState } from "react";
import { useAuth } from "../AuthProvider";
import { useRouter } from "next/navigation";
import { Lock } from "lucide-react";

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
      <div className="card w-full max-w-sm space-y-6 animate-in">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 text-2xl">
            📈
          </div>
          <h1 className="text-xl font-bold text-white">AI Stock Scanner</h1>
          <p className="text-sm text-slate-400">Sign in to continue</p>
        </div>

        <form onSubmit={handleLogin} className="space-y-4">
          {error && (
            <div className="rounded-lg bg-red-900/30 border border-red-800 px-3 py-2 text-sm text-red-400">
              {error}
            </div>
          )}
          <div>
            <label className="mb-1 block text-xs text-slate-400">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => { setUsername(e.target.value); setError(""); }}
              className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-accent"
              placeholder="admin"
              autoComplete="username"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(""); }}
              className="w-full rounded-lg border border-slate-600 bg-slate-700 px-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-accent"
              placeholder="••••••••"
              autoComplete="current-password"
            />
          </div>
          <button
            type="submit"
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent py-2.5 text-sm font-medium text-white transition hover:bg-blue-600"
          >
            <Lock size={14} />
            Sign In
          </button>
        </form>

        <p className="text-center text-xs text-slate-500">
          Personal use only &middot; Not financial advice
        </p>
      </div>
    </div>
  );
}
