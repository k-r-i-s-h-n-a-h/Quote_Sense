"use client";

import React from "react";
import TatvaLogo from "./TatvaLogo";

const inputClass =
  "qs-input !py-3.5";

export { inputClass };

/** Shared terms/privacy notice — spacing via string nodes (Sonar S6851). */
export function AuthLegalFooter({ className = "mt-8" }: { className?: string }) {
  return (
    <p
      className={`${className} text-[11px] text-stone-400 text-center leading-relaxed`}
    >
      {"By continuing, you agree to our "}
      <a
        href="https://tatvaops.com/terms"
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-stone-600"
      >
        Terms of Service
      </a>
      {" and "}
      <a
        href="https://tatvaops.com/privacy"
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-stone-600"
      >
        Privacy Policy
      </a>
      {"."}
    </p>
  );
}

type AuthPageLayoutProps = {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

export default function AuthPageLayout({
  title,
  subtitle,
  children,
  footer,
}: AuthPageLayoutProps) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-md qs-card px-8 py-10 shadow-[var(--shadow-md)]">
        <div className="flex flex-col items-center text-center mb-8">
          <TatvaLogo size="sm" className="mb-4" />
          <p className="qs-eyebrow">QuoteSense</p>
          <p className="text-xs text-stone-400 mt-1">TatvaOps procurement intelligence</p>
          <h1 className="text-xl font-semibold text-stone-900 tracking-tight mt-4">
            {title}
          </h1>
          <p className="text-sm text-stone-500 mt-2 leading-relaxed">{subtitle}</p>
        </div>

        {children}

        {footer}

        <AuthLegalFooter />
      </div>
    </div>
  );
}
