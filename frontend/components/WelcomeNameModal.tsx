"use client";

import React, { useEffect, useRef, useState } from "react";
import { getAuthToken, getAuthUserId, useAuth } from "@/lib/auth";
import { inputClass } from "@/components/AuthPageLayout";

export default function WelcomeNameModal() {
  const { user, refreshProfile } = useAuth();
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  if (!user) return null;

  const userId = getAuthUserId(user);
  const canSubmit = name.trim().length >= 2 && !saving;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit || !userId) return;

    const token = getAuthToken();
    if (!token) {
      setError("Session expired. Please sign in again.");
      return;
    }

    setSaving(true);
    setError(null);
    const trimmedName = name.trim();

    try {
      const res = await fetch(`/api/auth/profile?userId=${encodeURIComponent(userId)}`, {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: trimmedName, fullName: trimmedName }),
      });
      const data = await res.json();
      if (!res.ok || data.success === false) {
        setError(data.message || data.error || "Could not save your name. Please try again.");
        return;
      }
      await refreshProfile();
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/50 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="welcome-name-title"
    >
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-100 px-8 py-10">
        <div className="text-center mb-6">
          <h2
            id="welcome-name-title"
            className="text-xl font-bold text-slate-900 tracking-tight"
          >
            Welcome to TatvaOps
          </h2>
          <p className="text-sm text-slate-500 mt-2">
            What should we call you? This helps personalize your dashboard.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="welcome-name" className="block text-sm font-medium text-slate-700 mb-1.5">
              Your name
            </label>
            <input
              ref={inputRef}
              id="welcome-name"
              type="text"
              autoComplete="name"
              placeholder="John Doe"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputClass}
              disabled={saving}
            />
          </div>

          {error && <p className="text-sm text-red-600 text-center">{error}</p>}

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full py-3.5 rounded-xl text-sm font-semibold text-white bg-[#c04a00] hover:bg-[#a84000] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {saving ? "Saving…" : "Continue"}
          </button>
        </form>

        <p className="mt-4 text-[11px] text-slate-400 text-center">
          You can update this anytime from your profile.
        </p>
      </div>
    </div>
  );
}
