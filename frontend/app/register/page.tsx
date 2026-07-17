"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AuthPageLayout, { inputClass } from "@/components/AuthPageLayout";
import { WhatsAppIcon } from "@/components/WhatsAppIcon";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const { sendOtp, verifyOtp, otpSent, otpError, clearOtpState, isAuthenticated, isLoading } =
    useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    nameRef.current?.focus();
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
  const canSend =
    name.trim().length >= 2 &&
    email.includes("@") &&
    cleanedPhone.length >= 10 &&
    !loading;

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSend) return;
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
    const ok = await verifyOtp(cleanedPhone, otp.trim(), {
      name: name.trim(),
      email: email.trim(),
    });
    setLoading(false);
    if (ok) router.replace("/");
  };

  return (
    <AuthPageLayout
      title="Create account"
      subtitle="Join TatvaOps to compare quotes with AI-powered insights"
      footer={
        <p className="mt-6 text-sm text-slate-500 text-center">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-[#c04a00] hover:underline">
            Sign in
          </Link>
        </p>
      }
    >
      {!otpSent ? (
        <form onSubmit={handleSendOtp} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-slate-700 mb-1.5">
              Full name
            </label>
            <input
              id="name"
              ref={nameRef}
              type="text"
              placeholder="Enter your full name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1.5">
              Email address
            </label>
            <input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="phone" className="block text-sm font-medium text-slate-700 mb-1.5">
              Phone number
            </label>
            <input
              id="phone"
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
            disabled={!canSend}
            className="w-full py-3.5 rounded-xl font-semibold text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-gradient-to-b from-[#c04a00] to-[#9a3a00] hover:from-[#d45500] hover:to-[#a84000] shadow-sm inline-flex items-center justify-center gap-2.5"
          >
            {loading ? (
              "Sending…"
            ) : (
              <>
                <WhatsAppIcon className="w-5 h-5 text-white" />
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
              maxLength={6}
              placeholder="Enter 6-digit OTP"
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
              autoFocus
              className={`${inputClass} text-center text-lg tracking-[0.3em]`}
            />
          </div>
          <button
            type="submit"
            disabled={otp.length < 4 || loading}
            className="w-full py-3.5 rounded-xl font-semibold text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed bg-gradient-to-b from-[#c04a00] to-[#9a3a00] hover:from-[#d45500] hover:to-[#a84000] shadow-sm"
          >
            {loading ? "Creating account…" : "Create account"}
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
              Edit details
            </button>
          </div>
        </form>
      )}

      {otpError && <p className="mt-3 text-sm text-red-600 text-center">{otpError}</p>}
    </AuthPageLayout>
  );
}
