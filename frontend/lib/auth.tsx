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
import { buildPmRedirectPath } from "./project-resolve";
import { resolveProfileName, withResolvedName } from "./user-display";

const TOKEN_KEY = "token";
const REFRESH_KEY = "refreshToken";
const USER_KEY = "user";
const AUTH_SOURCE_KEY = "authSource";

type AuthSource = "sso" | "otp";

type AuthContextValue = {
  user: TatvaUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  /** True when this session was started from a PM jwt_auth / token redirect. */
  fromPmSso: boolean;
  otpSent: boolean;
  otpError: string | null;
  sendOtp: (phoneNumber: string) => Promise<boolean>;
  verifyOtp: (
    phoneNumber: string,
    otp: string,
    profile?: { name?: string; email?: string }
  ) => Promise<boolean>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
  clearOtpState: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function readAuthSource(): AuthSource | null {
  if (typeof window === "undefined") return null;
  const value = localStorage.getItem(AUTH_SOURCE_KEY);
  return value === "sso" || value === "otp" ? value : null;
}

function writeStoredUser(user: TatvaUser, source?: AuthSource) {
  const normalized = withResolvedName(user);
  localStorage.setItem(USER_KEY, JSON.stringify({ user: normalized }));
  if (source) localStorage.setItem(AUTH_SOURCE_KEY, source);
  return normalized;
}

function readStoredUser(): TatvaUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    const user = parsed?.user ?? parsed;
    return user ? withResolvedName(user as TatvaUser) : null;
  } catch {
    return null;
  }
}

function getUserId(user: TatvaUser | null): string | null {
  if (!user) return null;
  return user._id || user.id || null;
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const segment = token.split(".")[1];
    if (!segment) return null;
    return JSON.parse(
      atob(segment.replaceAll("-", "+").replaceAll("_", "/"))
    ) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/**
 * Reject a cached JWT once its `exp` time has passed.
 *
 * Some Tatva environments return opaque access tokens, so a token that cannot
 * be decoded is left for the profile API to validate. Only a JWT with an
 * explicit, expired `exp` claim is rejected locally.
 */
export function isAccessTokenExpired(
  token: string,
  nowSeconds = Date.now() / 1000
): boolean {
  const payload = decodeJwtPayload(token);
  const expiresAt = Number(payload?.exp);
  return Number.isFinite(expiresAt) && expiresAt > 0 && expiresAt <= nowSeconds;
}

/** Read user id from a Tatva JWT payload when PM does not send user_id. */
function getUserIdFromJwt(token: string): string | null {
  const payload = decodeJwtPayload(token);
  if (!payload) return null;
  const id = payload.sub ?? payload.userId ?? payload._id ?? payload.id;
  return typeof id === "string" ? id : id != null ? String(id) : null;
}

function isValidUser(profile: TatvaUser | null | undefined): profile is TatvaUser {
  return !!(
    profile &&
    (profile._id || profile.id || profile.phoneNumber || profile.email)
  );
}

/** Handle Tatva API wrappers: { data: { user } }, { data }, { user }, or flat user. */
function parseProfileFromResponse(data: Record<string, unknown>): TatvaUser | null {
  const nested = data.data;
  if (nested && typeof nested === "object") {
    const obj = nested as Record<string, unknown>;
    if (obj.user && typeof obj.user === "object") {
      return obj.user as TatvaUser;
    }
    return nested as TatvaUser;
  }
  if (data.user && typeof data.user === "object") {
    return data.user as TatvaUser;
  }
  return data as TatvaUser;
}

function claimString(payload: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return undefined;
}

/** Build a minimal session user from a Tatva JWT when the profile API is unavailable. */
function userFromJwt(token: string, userId: string): TatvaUser | null {
  const payload = decodeJwtPayload(token);
  if (!payload) return null;

  const exp = payload.exp;
  if (typeof exp === "number" && Date.now() / 1000 > exp) return null;

  const nested =
    payload.user && typeof payload.user === "object"
      ? (payload.user as Record<string, unknown>)
      : payload;

  const firstName = claimString(nested, "firstName", "first_name", "given_name");
  const lastName = claimString(nested, "lastName", "last_name", "family_name");
  const name =
    resolveProfileName({
      name: claimString(nested, "name"),
      fullName: claimString(nested, "fullName"),
      username: claimString(nested, "username"),
      firstName,
      lastName,
    }) || undefined;

  return withResolvedName({
    _id: userId,
    email: claimString(nested, "email"),
    name,
    fullName: claimString(nested, "fullName") || name,
    username: claimString(nested, "username"),
    firstName,
    lastName,
  });
}

function mergeProfileWithJwt(profile: TatvaUser, token: string): TatvaUser {
  const userId = getUserId(profile);
  const fromJwt = userId ? userFromJwt(token, userId) : null;
  if (!fromJwt) return withResolvedName(profile);
  return withResolvedName({
    ...fromJwt,
    ...profile,
    name: resolveProfileName(profile) || fromJwt.name,
    fullName: profile.fullName?.trim() || fromJwt.fullName,
    username: profile.username || fromJwt.username,
    firstName: profile.firstName || fromJwt.firstName,
    lastName: profile.lastName || fromJwt.lastName,
    email: profile.email || fromJwt.email,
  });
}

function buildSsoRedirectUrl(params: URLSearchParams): string {
  const pathname =
    typeof window !== "undefined" ? window.location.pathname : "";
  return buildPmRedirectPath(params, pathname);
}

/** Collect SSO params from the current URL or nested inside login returnTo. */
function collectRedirectParams(): URLSearchParams | null {
  if (typeof window === "undefined") return null;

  const current = new URLSearchParams(window.location.search);
  if (current.get("jwt_auth") || current.get("token")) return current;

  const returnTo = current.get("returnTo");
  if (!returnTo) return null;

  const queryStart = returnTo.indexOf("?");
  if (queryStart < 0) return null;

  const nested = new URLSearchParams(returnTo.slice(queryStart + 1));
  if (nested.get("jwt_auth") || nested.get("token")) return nested;

  return null;
}

type BootstrapResult = { user: TatvaUser; redirectTo: string };

/**
 * TatvaOps PM redirect SSO: session_id + jwt_auth + user_id.
 * Tries profile API first, then falls back to trusting a valid JWT payload.
 */
async function bootstrapFromSearchParams(
  params: URLSearchParams
): Promise<BootstrapResult | null> {
  const urlToken = params.get("jwt_auth") ?? params.get("token");
  if (!urlToken) return null;

  const urlUserId = params.get("user_id") ?? getUserIdFromJwt(urlToken);
  if (!urlUserId) return null;

  const redirectTo = buildSsoRedirectUrl(params);

  localStorage.setItem(TOKEN_KEY, urlToken);

  try {
    const res = await fetch(
      `/api/auth/profile?userId=${encodeURIComponent(urlUserId)}`,
      {
        headers: { Authorization: `Bearer ${urlToken}` },
        signal: AbortSignal.timeout(12_000),
      }
    );

    if (res.ok) {
      const data = await res.json();
      const profile = parseProfileFromResponse(data);
      if (isValidUser(profile)) {
        const user = writeStoredUser(mergeProfileWithJwt(profile, urlToken), "sso");
        return { user, redirectTo };
      }
    }

    const fallbackUser = userFromJwt(urlToken, urlUserId);
    if (isValidUser(fallbackUser)) {
      const user = writeStoredUser(fallbackUser, "sso");
      return { user, redirectTo };
    }

    localStorage.removeItem(TOKEN_KEY);
    return null;
  } catch {
    const fallbackUser = userFromJwt(urlToken, urlUserId);
    if (isValidUser(fallbackUser)) {
      const user = writeStoredUser(fallbackUser, "sso");
      return { user, redirectTo };
    }
    localStorage.removeItem(TOKEN_KEY);
    return null;
  }
}

async function bootstrapFromRedirectParams(): Promise<BootstrapResult | null> {
  const params = collectRedirectParams();
  if (!params) return null;
  return bootstrapFromSearchParams(params);
}

function applyBootstrapRedirect(redirectTo: string) {
  if (typeof window === "undefined") return;

  const destPath = redirectTo.split("?")[0] || "/";
  if (
    window.location.pathname === destPath &&
    !window.location.search
  ) {
    return;
  }

  window.location.replace(redirectTo);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<TatvaUser | null>(null);
  const [fromPmSso, setFromPmSso] = useState(false);
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
    const normalized = writeStoredUser(mergeProfileWithJwt(nextUser, accessToken), "otp");
    setFromPmSso(false);
    setUser(normalized);
  }, []);

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(AUTH_SOURCE_KEY);
    setFromPmSso(false);
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
        signal: AbortSignal.timeout(12_000),
      });
      if (res.status === 401 || res.status === 403) {
        clearSession();
        return;
      }
      if (!res.ok) return;
      const data = await res.json();
      const profile = parseProfileFromResponse(data);
      if (isValidUser(profile)) {
        const merged = writeStoredUser(
          mergeProfileWithJwt(current ? { ...current, ...profile } : profile, token)
        );
        setUser(merged);
      }
    } catch {
      /* keep cached user */
    }
  }, [clearSession]);

  useEffect(() => {
    let cancelled = false;

    async function initAuth() {
      try {
        const fromRedirect = await bootstrapFromRedirectParams();
        if (cancelled) return;

        if (fromRedirect) {
          setFromPmSso(true);
          setUser(fromRedirect.user);
          applyBootstrapRedirect(fromRedirect.redirectTo);
          return;
        }

        const stored = readStoredUser();
        const token = localStorage.getItem(TOKEN_KEY);
        if (stored && token) {
          if (isAccessTokenExpired(token)) {
            clearSession();
            return;
          }
          setFromPmSso(readAuthSource() === "sso");
          setUser(stored);
          // Keep the auth gate loading until the server accepts the cached
          // token. This prevents the dashboard/name modal flashing before an
          // expired or revoked session is redirected to /login.
          await refreshProfile();
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    initAuth();
    return () => {
      cancelled = true;
    };
  }, [clearSession, refreshProfile]);

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
    async (
      phoneNumber: string,
      otp: string,
      profile?: { name?: string; email?: string }
    ) => {
      setOtpError(null);
      try {
        const res = await fetch("/api/auth/verify-otp", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ phoneNumber, otp }),
        });
        const data: VerifyOtpResponse = await res.json();
        if (data.success && data.data?.user && data.data?.tokens) {
          persistSession(
            withResolvedName({
              ...data.data.user,
              ...(profile?.name?.trim() ? { name: profile.name.trim() } : {}),
              ...(profile?.email?.trim() ? { email: profile.email.trim() } : {}),
            }),
            data.data.tokens
          );
          setOtpSent(false);

          const userId = getUserId(data.data.user);
          const accessToken =
            data.data.tokens.accessToken || (data.data.tokens as { token?: string }).token;
          const name = profile?.name?.trim();
          const email = profile?.email?.trim();

          if (userId && accessToken && (name || email)) {
            try {
              await fetch(`/api/auth/profile?userId=${userId}`, {
                method: "PUT",
                headers: {
                  Authorization: `Bearer ${accessToken}`,
                  "Content-Type": "application/json",
                },
                body: JSON.stringify({
                  ...(name ? { name } : {}),
                  ...(email ? { email } : {}),
                }),
              });
              await refreshProfile();
            } catch {
              /* session is valid; profile can be updated later */
            }
          }

          return true;
        }
        setOtpError(data.message || "Invalid OTP. Please try again.");
        return false;
      } catch {
        setOtpError("Network error. Please try again.");
        return false;
      }
    },
    [persistSession, refreshProfile]
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
      fromPmSso,
      otpSent,
      otpError,
      sendOtp,
      verifyOtp,
      logout,
      refreshProfile,
      clearOtpState,
    }),
    [
      user,
      isLoading,
      fromPmSso,
      otpSent,
      otpError,
      sendOtp,
      verifyOtp,
      logout,
      refreshProfile,
      clearOtpState,
    ]
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

/** Resolve Tatva user id from stored profile or JWT (SSO / OTP). */
export function getAuthUserId(user: TatvaUser | null): string | null {
  const fromUser = getUserId(user);
  if (fromUser) return fromUser;
  const token = getAuthToken();
  if (!token) return null;
  return getUserIdFromJwt(token);
}
