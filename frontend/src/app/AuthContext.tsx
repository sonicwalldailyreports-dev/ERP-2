import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authApi } from "../services/authApi";
import { setAccessToken } from "../services/apiClient";
import type { AuthUser } from "../types/auth";

type AuthContextValue = { user: AuthUser | null; isLoading: boolean; login: (username: string, password: string) => Promise<void>; logout: () => Promise<void> };
const Context = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isLoading, setLoading] = useState(true);
  useEffect(() => { setLoading(false); }, []);
  const login = async (username: string, password: string) => { const tokens = await authApi.login(username, password); setAccessToken(tokens.access_token); setRefreshToken(tokens.refresh_token); setUser(await authApi.me()); };
  const logout = async () => { if (refreshToken) await authApi.logout(refreshToken); setAccessToken(null); setRefreshToken(null); setUser(null); };
  const value = useMemo(() => ({ user, isLoading, login, logout }), [user, isLoading, refreshToken]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useAuth() {
  const value = useContext(Context);
  if (!value) throw new Error("useAuth must be used within AuthProvider");
  return value;
}
