"use client";

import React from "react";

export default function SessionExpiredModal({
  onSignIn,
  onContinue,
}: {
  onSignIn: () => void;
  onContinue?: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-stone-900/45 px-4 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-labelledby="session-expired-title"
    >
      <div className="w-full max-w-md qs-card px-8 py-10 shadow-[var(--shadow-lg)]">
        <div className="text-center mb-6">
          <p className="qs-eyebrow">QuoteSense</p>
          <h2
            id="session-expired-title"
            className="text-xl font-semibold text-stone-900 tracking-tight mt-2"
          >
            Your session has expired
          </h2>
          <p className="text-sm text-stone-500 mt-2 leading-relaxed">
            Sign in again to load your TatvaOps projects. You can still compare
            vendor quote PDFs without signing in.
          </p>
        </div>

        <div className="space-y-3">
          <button
            type="button"
            onClick={onSignIn}
            className="qs-btn qs-btn-primary w-full !py-3.5"
          >
            Sign in again
          </button>
          {onContinue ? (
            <button
              type="button"
              onClick={onContinue}
              className="qs-btn qs-btn-secondary w-full !py-3"
            >
              Continue without projects
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
