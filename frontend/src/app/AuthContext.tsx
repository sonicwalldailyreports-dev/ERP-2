import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authApi } from "../services/authApi";
import { setAccessToken, setRefreshHandler } from "../services/apiClient";
import type { AuthUser } from "../types/auth";

type AuthContextValue = { user: AuthUser | null; isLoading: boolean; login: (username: string, password: string) => Promise<void>; logout: () => Promise<void> };
const Context = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(() => sessionStorage.getItem("refreshToken"));
  const [isLoading, setLoading] = useState(true);
  const applyTokens = (access: string, refresh: string) => {
    setAccessToken(access);
    setRefreshToken(refresh);
    sessionStorage.setItem("refreshToken", refresh);
  };
  const refresh = async () => {
    const current = sessionStorage.getItem("refreshToken");
    if (!current) return null;
    try {
      const tokens = await authApi.refresh(current);
      applyTokens(tokens.access_token, tokens.refresh_token);
      return tokens.access_token;
    } catch {
      setAccessToken(null);
      setRefreshToken(null);
      sessionStorage.removeItem("refreshToken");
      setUser(null);
      return null;
    }
  };
  useEffect(() => {
    setRefreshHandler(refresh);
    void (async () => {
      if (await refresh()) {
        try {
          setUser(await authApi.me());
        } catch {
          setUser(null);
        }
      }
      setLoading(false);
    })();
    return () => setRefreshHandler(null);
  }, []);
  const login = async (username: string, password: string) => {
    const tokens = await authApi.login(username, password);
    applyTokens(tokens.access_token, tokens.refresh_token);
    setUser(await authApi.me());
  };
  const logout = async () => {
    if (refreshToken) await authApi.logout(refreshToken).catch(() => undefined);
    setAccessToken(null);
    setRefreshToken(null);
    sessionStorage.removeItem("refreshToken");
    setUser(null);
  };
  const value = useMemo(() => ({ user, isLoading, login, logout }), [user, isLoading, refreshToken]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useAuth() {
  const value = useContext(Context);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
