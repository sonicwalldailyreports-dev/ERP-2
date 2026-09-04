import { apiClient } from "./apiClient";
import type { AuthTokens, AuthUser } from "../types/auth";

export const authApi = {
  login: (username: string, password: string) => apiClient<AuthTokens>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  refresh: (refreshToken: string) => apiClient<AuthTokens>("/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) }),
  logout: (refreshToken: string) => apiClient<void>("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) }),
  me: () => apiClient<AuthUser>("/auth/me"),
};
