"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { TokenResponse, User } from "@/lib/types";

type AuthValue = {
  user: User | null;
  token: string | null;
  ready: boolean;
  acceptToken: (data: TokenResponse) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);
const SESSION_KEY = "sentinel.session.v1";

type StoredSession = { token: string; expiresAt: number };

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    if (typeof window !== "undefined") sessionStorage.removeItem(SESSION_KEY);
  }, []);

  const acceptToken = useCallback((data: TokenResponse) => {
    setToken(data.access_token);
    setUser(data.user);
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ token: data.access_token, expiresAt: Date.now() + data.expires_in * 1000 } satisfies StoredSession));
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function restore() {
      try {
        const raw = sessionStorage.getItem(SESSION_KEY);
        if (!raw) return;
        const saved = JSON.parse(raw) as StoredSession;
        if (!saved.token || !saved.expiresAt || saved.expiresAt <= Date.now()) {
          sessionStorage.removeItem(SESSION_KEY);
          return;
        }
        const currentUser = await api.me(saved.token);
        if (cancelled) return;
        setToken(saved.token);
        setUser(currentUser);
      } catch {
        sessionStorage.removeItem(SESSION_KEY);
      } finally {
        if (!cancelled) setReady(true);
      }
    }
    void restore();
    return () => { cancelled = true; };
  }, []);

  const value = useMemo(() => ({ user, token, ready, acceptToken, logout }), [user, token, ready, acceptToken, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
