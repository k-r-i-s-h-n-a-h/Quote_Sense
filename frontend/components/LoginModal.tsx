"use client";

import React, { useEffect, useRef, useState } from "react";
import TatvaLogo from "./TatvaLogo";
import { WhatsAppIcon } from "./WhatsAppIcon";
import { useAuth } from "@/lib/auth";

type LoginModalProps = {
  open: boolean;
  onClose: () => void;
};

export default function LoginModal({ open, onClose }: LoginModalProps) {
  const { sendOtp, verifyOtp, otpSent, otpError, clearOtpState } = useAuth();
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const phoneRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setPhone("");
      setOtp("");
      setResendCooldown(0);
      clearOtpState();
      setTimeout(() => phoneRef.current?.focus(), 100);
    }
  }, [open, clearOtpState]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = window.setTimeout(() => setResendCooldown((s) => s - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [resendCooldown]);

  if (!open) return null;

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

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otp.trim()) return;
    setLoading(true);
    const ok = await verifyOtp(cleanedPhone, otp.trim());
    setLoading(false);
    if (ok) onClose();
  };

  const canSend = cleanedPhone.length >= 10 && !loading;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-title"
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"
        onClick={onClose}
        aria-label="Close login"
      />

      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl px-8 py-10 animate-in fade-in zoom-in-95 duration-200">
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors"
          aria-label="Close"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>

        <div className="flex flex-col items-center text-center mb-8">
          <TatvaLogo size="md" className="mb-6" />
          <h2 id="login-title" className="text-xl font-bold text-slate-900 tracking-tight">
            Sign in or create an account
          </h2>
          <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-[0.2em] mt-2">
            Welcome to Tatva
          </p>
        </div>

        {!otpSent ? (
          <form onSubmit={handleSendOtp} className="space-y-4">
            <input
              ref={phoneRef}
              type="tel"
              inputMode="numeric"
              placeholder="Enter your Phone number"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full px-4 py-3.5 border border-slate-200 rounded-xl text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#c04a00]/30 focus:border-[#c04a00] transition-all"
            />
            <button
              type="submit"
              disabled={!canSend}
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
            <p className="text-sm text-slate-500 text-center mb-1">
              OTP sent to <span className="font-medium text-slate-700">+91 {cleanedPhone}</span>
            </p>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              placeholder="Enter 6-digit OTP"
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
              autoFocus
              className="w-full px-4 py-3.5 border border-slate-200 rounded-xl text-slate-800 text-center text-lg tracking-[0.3em] placeholder:text-slate-400 placeholder:tracking-normal placeholder:text-base focus:outline-none focus:ring-2 focus:ring-[#c04a00]/30 focus:border-[#c04a00] transition-all"
            />
            <button
              type="submit"
              disabled={otp.length < 4 || loading}
              className="w-full py-3.5 rounded-xl font-semibold text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-gradient-to-b from-[#c04a00] to-[#9a3a00] hover:from-[#d45500] hover:to-[#a84000] shadow-sm"
            >
              {loading ? "Verifying…" : "Verify & Sign In"}
            </button>
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

        {otpError && (
          <p className="mt-3 text-sm text-red-600 text-center">{otpError}</p>
        )}

        <p className="mt-8 text-[11px] text-slate-400 text-center leading-relaxed">
          By continuing, you agree to our{" "}
          <a href="https://tatvaops.com/terms" target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-600">
            Terms of Service
          </a>{" "}
          and{" "}
          <a href="https://tatvaops.com/privacy" target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-600">
            Privacy Policy
          </a>
          .
        </p>
      </div>
    </div>
  );
}
