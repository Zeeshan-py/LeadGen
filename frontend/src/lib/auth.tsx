"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { apiFetch, API_URL } from "@/lib/http";

export type AuthUser = {
  id: string;
  full_name: string;
  email: string;
  provider: string;
  avatar_url: string;
  is_admin: boolean;
  is_verified: boolean;
  created_at: string;
  last_login: string | null;
};

type AuthResponse = {
  user: AuthUser;
  csrf_token: string;
};

type ForgotPasswordResponse = {
  message: string;
  reset_token?: string | null;
  reset_url?: string | null;
};

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  login: (payload: { email: string; password: string; remember_me: boolean }) => Promise<AuthUser>;
  signup: (payload: { full_name: string; email: string; password: string; remember_me: boolean }) => Promise<AuthUser>;
  logout: () => Promise<void>;
  forgotPassword: (email: string) => Promise<ForgotPasswordResponse>;
  resetPassword: (token: string, password: string) => Promise<void>;
  refreshMe: () => Promise<AuthUser | null>;
  oauthUrl: (provider: "google" | "github", nextPath?: string) => string;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    const response = await apiFetch("/auth/me", undefined, true);
    if (!response.ok) {
      setUser(null);
      setLoading(false);
      return null;
    }
    const nextUser = (await response.json()) as AuthUser;
    setUser(nextUser);
    setLoading(false);
    return nextUser;
  }, []);

  useEffect(() => {
    refreshMe();
    const requireAuth = () => setUser(null);
    const refreshAuth = () => refreshMe();
    window.addEventListener("leadforge:auth-required", requireAuth);
    window.addEventListener("leadforge:auth-refreshed", refreshAuth);
    return () => {
      window.removeEventListener("leadforge:auth-required", requireAuth);
      window.removeEventListener("leadforge:auth-refreshed", refreshAuth);
    };
  }, [refreshMe]);

  const login = useCallback(async (payload: { email: string; password: string; remember_me: boolean }) => {
    const response = await apiFetch(
      "/auth/login",
      { method: "POST", body: JSON.stringify(payload) },
      false,
    );
    const data = await parseJson<AuthResponse>(response);
    setUser(data.user);
    return data.user;
  }, []);

  const signup = useCallback(async (payload: { full_name: string; email: string; password: string; remember_me: boolean }) => {
    const response = await apiFetch(
      "/auth/signup",
      { method: "POST", body: JSON.stringify(payload) },
      false,
    );
    const data = await parseJson<AuthResponse>(response);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    await apiFetch("/auth/logout", { method: "POST" }, false).catch(() => null);
    setUser(null);
  }, []);

  const forgotPassword = useCallback(async (email: string) => {
    const response = await apiFetch(
      "/auth/forgot-password",
      { method: "POST", body: JSON.stringify({ email }) },
      false,
    );
    return parseJson<ForgotPasswordResponse>(response);
  }, []);

  const resetPassword = useCallback(async (token: string, password: string) => {
    const response = await apiFetch(
      "/auth/reset-password",
      { method: "POST", body: JSON.stringify({ token, password }) },
      false,
    );
    await parseJson<{ status: string }>(response);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      login,
      signup,
      logout,
      forgotPassword,
      resetPassword,
      refreshMe,
      oauthUrl: (provider, nextPath = "/dashboard") =>
        `${API_URL}/auth/${provider}/login?next=${encodeURIComponent(nextPath)}`,
    }),
    [forgotPassword, loading, login, logout, refreshMe, resetPassword, signup, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : "";
    throw new Error(detail || text || `Request failed: ${response.status}`);
  }
  return payload as T;
}
