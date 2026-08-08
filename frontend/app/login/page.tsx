"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AuthPageLayout, { inputClass } from "@/components/AuthPageLayout";
import { WhatsAppIcon } from "@/components/WhatsAppIcon";
import { useAuth } from "@/lib/auth";

function safeReturnTo(raw: string | null): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//")) return "/";
  return raw;
}

/** After sign-in, land on projects unless resuming a compare session. */
function cleanReturnTo(raw: string): string {
  const queryStart = raw.indexOf("?");
  const path = queryStart < 0 ? raw : raw.slice(0, queryStart) || "/";

  if (path.startsWith("/project/")) {
    return "/";
  }

  if (queryStart >= 0) {
    const params = new URLSearchParams(raw.slice(queryStart + 1));
    const sessionId = params.get("session_id");
    if (sessionId) {
      return `/compare?session_id=${encodeURIComponent(sessionId)}`;
    }
  }

  return path;
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex items-center justify-center">
          <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { sendOtp, verifyOtp, otpSent, otpError, clearOtpState, isAuthenticated, isLoading } =
    useAuth();
  const returnTo = cleanReturnTo(safeReturnTo(searchParams.get("returnTo")));
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const phoneRef = useRef<HTMLInputElement>(null);
  const verifyingRef = useRef(false);

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace(returnTo);
    }
  }, [isAuthenticated, isLoading, router, returnTo]);

  useEffect(() => {
    phoneRef.current?.focus();
  }, []);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = window.setTimeout(() => setResendCooldown((s) => s - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [resendCooldown]);

  if (isLoading || isAuthenticated) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
      </div>
    );
  }

  const cleanedPhone = phone.replace(/\D/g, "");

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (cleanedPhone.length < 10) return;
    setLoading(true);
    const ok = await sendOtp(cleanedPhone);
    setLoading(false);
    if (ok) {
      setOtp("");
      setResendCooldown(30);
    }
  };

  const handleResendOtp = async () => {
    if (cleanedPhone.length < 10 || loading || resendCooldown > 0) return;
    setLoading(true);
    const ok = await sendOtp(cleanedPhone);
    setLoading(false);
    if (ok) {
      setOtp("");
      setResendCooldown(30);
    }
  };

  const submitOtp = async (code: string) => {
    const trimmed = code.replace(/\D/g, "").slice(0, 6);
    if (trimmed.length !== 6 || verifyingRef.current) return;
    verifyingRef.current = true;
    setLoading(true);
    try {
      const ok = await verifyOtp(cleanedPhone, trimmed);
      if (ok) router.replace(returnTo);
    } finally {
      setLoading(false);
      verifyingRef.current = false;
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    await submitOtp(otp);
  };

  const handleOtpChange = (value: string) => {
    const digits = value.replace(/\D/g, "").slice(0, 6);
    setOtp(digits);
    if (digits.length === 6) {
      void submitOtp(digits);
    }
  };

  return (
    <AuthPageLayout
      title="Sign in"
      subtitle="Welcome back — enter your phone number to continue"
      footer={
        <p className="mt-6 text-sm text-slate-500 text-center">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="font-medium text-[#c04a00] hover:underline">
            Create one
          </Link>
        </p>
      }
    >
      {!otpSent ? (
        <form onSubmit={handleSendOtp} className="space-y-4">
          <div>
            <label htmlFor="phone" className="block text-sm font-medium text-slate-700 mb-1.5">
              Phone number
            </label>
            <input
              id="phone"
              ref={phoneRef}
              type="tel"
              inputMode="numeric"
              placeholder="Enter your phone number"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className={inputClass}
            />
          </div>
          <button
            type="submit"
            disabled={cleanedPhone.length < 10 || loading}
            className="w-full py-3.5 rounded-xl font-semibold text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-gradient-to-b from-slate-500 to-slate-700 hover:from-slate-600 hover:to-slate-800 shadow-sm inline-flex items-center justify-center gap-2.5"
          >
            {loading ? (
              "Sending…"
            ) : (
              <>
                <WhatsAppIcon className="w-5 h-5 text-[#25D366]" />
                Get OTP on WhatsApp
              </>
            )}
          </button>
        </form>
      ) : (
        <form onSubmit={handleVerifyOtp} className="space-y-4">
          <p className="text-sm text-slate-500 text-center">
            OTP sent to <span className="font-medium text-slate-700">+91 {cleanedPhone}</span>
          </p>
          <div>
            <label htmlFor="otp" className="block text-sm font-medium text-slate-700 mb-1.5">
              One-time password
            </label>
            <input
              id="otp"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="Enter 6-digit OTP"
              value={otp}
              onChange={(e) => handleOtpChange(e.target.value)}
              disabled={loading}
              autoFocus
              className={`${inputClass} text-center text-lg tracking-[0.3em]`}
            />
            <p className="mt-2 text-xs text-slate-500 text-center">
              {loading ? "Verifying…" : "Sign-in runs automatically after 6 digits"}
            </p>
          </div>
          <div className="flex items-center justify-center gap-3 text-sm">
            <button
              type="button"
              onClick={handleResendOtp}
              disabled={loading || resendCooldown > 0}
              className="text-[#c04a00] hover:underline transition-colors disabled:opacity-50 disabled:no-underline disabled:cursor-not-allowed"
            >
              {resendCooldown > 0 ? `Resend OTP in ${resendCooldown}s` : "Resend OTP"}
            </button>
            <span className="text-slate-300" aria-hidden>
              ·
            </span>
            <button
              type="button"
              onClick={() => {
                clearOtpState();
                setOtp("");
                setResendCooldown(0);
              }}
              className="text-slate-500 hover:text-[#c04a00] transition-colors"
            >
              Change phone number
            </button>
          </div>
        </form>
      )}

      {otpError && <p className="mt-3 text-sm text-red-600 text-center">{otpError}</p>}
    </AuthPageLayout>
  );
}
