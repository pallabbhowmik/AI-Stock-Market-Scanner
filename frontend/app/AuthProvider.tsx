"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

interface AuthContextType {
  isLoggedIn: boolean;
  login: (username: string, password: string) => boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  isLoggedIn: false,
  login: () => false,
  logout: () => {},
});

export const useAuth = () => useContext(AuthContext);

// ── Single-account credentials ──────────────────────────────────────────────
// Change these to whatever you want — they're only checked client-side.
const VALID_USERNAME = "admin";
const VALID_PASSWORD = "scanner@2026";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoggedIn, setIsLoggedIn] = useState<boolean | null>(null); // null = loading
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    setIsLoggedIn(sessionStorage.getItem("auth") === "1");
  }, []);

  useEffect(() => {
    if (isLoggedIn === false && pathname !== "/login") {
      router.replace("/login");
    }
  }, [isLoggedIn, pathname, router]);

  const login = (username: string, password: string): boolean => {
    if (username === VALID_USERNAME && password === VALID_PASSWORD) {
      sessionStorage.setItem("auth", "1");
      setIsLoggedIn(true);
      return true;
    }
    return false;
  };

  const logout = () => {
    sessionStorage.removeItem("auth");
    setIsLoggedIn(false);
    router.replace("/login");
  };

  // While checking auth state, show nothing (prevents flash)
  if (isLoggedIn === null) {
    return (
      <AuthContext.Provider value={{ isLoggedIn: false, login, logout }}>
        <div className="flex min-h-screen items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-accent" />
        </div>
      </AuthContext.Provider>
    );
  }

  // On /login page, always render children (the login form)
  if (pathname === "/login") {
    return (
      <AuthContext.Provider value={{ isLoggedIn, login, logout }}>
        {children}
      </AuthContext.Provider>
    );
  }

  // Not logged in → redirect handled by useEffect, render nothing
  if (!isLoggedIn) {
    return (
      <AuthContext.Provider value={{ isLoggedIn, login, logout }}>
        <div className="flex min-h-screen items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-600 border-t-accent" />
        </div>
      </AuthContext.Provider>
    );
  }

  return (
    <AuthContext.Provider value={{ isLoggedIn, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
