"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { TatvaUser, VerifyOtpResponse } from "./tatva-api";

const TOKEN_KEY = "token";
const REFRESH_KEY = "refreshToken";
const USER_KEY = "user";

type AuthContextValue = {
  user: TatvaUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  otpSent: boolean;
  otpError: string | null;
  sendOtp: (phoneNumber: string) => Promise<boolean>;
  verifyOtp: (phoneNumber: string, otp: string) => Promise<boolean>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
  clearOtpState: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredUser(): TatvaUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.user ?? parsed;
  } catch {
    return null;
  }
}

function getUserId(user: TatvaUser | null): string | null {
  if (!user) return null;
  return user._id || user.id || null;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<TatvaUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [otpSent, setOtpSent] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);

  const persistSession = useCallback((nextUser: TatvaUser, tokens: Record<string, unknown>) => {
    const accessToken =
      (typeof tokens.accessToken === "string" && tokens.accessToken) ||
      (typeof tokens.token === "string" && tokens.token) ||
      null;
    if (!accessToken) return;

    const refreshToken =
      typeof tokens.refreshToken === "string" ? tokens.refreshToken : undefined;

    localStorage.setItem(TOKEN_KEY, accessToken);
    if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
    localStorage.setItem(USER_KEY, JSON.stringify({ user: nextUser }));
    setUser(nextUser);
  }, []);

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);

  const refreshProfile = useCallback(async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    const current = readStoredUser();
    const userId = getUserId(current);
    if (!token || !userId) return;

    try {
      const res = await fetch(`/api/auth/profile?userId=${userId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const data = await res.json();
      const profile: TatvaUser = data.data ?? data.user ?? data;
      if (profile && (profile._id || profile.id || profile.phoneNumber)) {
        localStorage.setItem(USER_KEY, JSON.stringify({ user: profile }));
        setUser(profile);
      }
    } catch {
      /* keep cached user */
    }
  }, []);

  useEffect(() => {
    const stored = readStoredUser();
    const token = localStorage.getItem(TOKEN_KEY);
    if (stored && token) {
      setUser(stored);
      refreshProfile().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [refreshProfile]);

  const sendOtp = useCallback(async (phoneNumber: string) => {
    setOtpError(null);
    try {
      const res = await fetch("/api/auth/send-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phoneNumber }),
      });
      const data = await res.json();
      if (data.success) {
        setOtpSent(true);
        return true;
      }
      setOtpError(data.message || "Failed to send OTP.");
      return false;
    } catch {
      setOtpError("Network error. Please try again.");
      return false;
    }
  }, []);

  const verifyOtp = useCallback(
    async (phoneNumber: string, otp: string) => {
      setOtpError(null);
      try {
        const res = await fetch("/api/auth/verify-otp", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ phoneNumber, otp }),
        });
        const data: VerifyOtpResponse = await res.json();
        if (data.success && data.data?.user && data.data?.tokens) {
          persistSession(data.data.user, data.data.tokens);
          setOtpSent(false);
          return true;
        }
        setOtpError(data.message || "Invalid OTP. Please try again.");
        return false;
      } catch {
        setOtpError("Network error. Please try again.");
        return false;
      }
    },
    [persistSession]
  );

  const logout = useCallback(() => {
    clearSession();
    setOtpSent(false);
    setOtpError(null);
  }, [clearSession]);

  const clearOtpState = useCallback(() => {
    setOtpSent(false);
    setOtpError(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      otpSent,
      otpError,
      sendOtp,
      verifyOtp,
      logout,
      refreshProfile,
      clearOtpState,
    }),
    [user, isLoading, otpSent, otpError, sendOtp, verifyOtp, logout, refreshProfile, clearOtpState]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}
