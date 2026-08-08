"use client";

import React from "react";

const inputClass =
  "w-full px-4 py-3.5 border border-slate-200 rounded-xl text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#c04a00]/30 focus:border-[#c04a00] transition-all";

export { inputClass };

/** Shared terms/privacy notice — spacing via string nodes (Sonar S6851). */
export function AuthLegalFooter({ className = "mt-8" }: { className?: string }) {
  return (
    <p
      className={`${className} text-[11px] text-slate-400 text-center leading-relaxed`}
    >
      {"By continuing, you agree to our "}
      <a
        href="https://tatvaops.com/terms"
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-slate-600"
      >
        Terms of Service
      </a>
      {" and "}
      <a
        href="https://tatvaops.com/privacy"
        target="_blank"
        rel="noopener noreferrer"
        className="underline hover:text-slate-600"
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
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg border border-slate-100 px-8 py-10">
        <div className="flex flex-col items-center text-center mb-8">
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Tatva Quote Comparator
          </h1>
          <h2 className="text-lg font-semibold text-slate-800 mt-4">{title}</h2>
          <p className="text-sm text-slate-500 mt-2">{subtitle}</p>
        </div>

        {children}

        {footer}

        <AuthLegalFooter />
      </div>
    </div>
  );
}
