"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  CURRENT_APP_ID,
  CURRENT_APP_LABEL,
  getTatvaEcosystemApps,
  type TatvaApp,
} from "@/lib/tatva-ecosystem";

function GridIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  );
}

function AppTile({ app, isCurrent }: { app: TatvaApp; isCurrent: boolean }) {
  const inner = (
    <>
      <span className={`text-sm font-semibold leading-tight ${app.nameClassName}`}>
        {app.name}
      </span>
      <span className="text-xs text-stone-500 mt-0.5 line-clamp-1">
        {app.description}
      </span>
    </>
  );

  const className = `flex flex-col rounded-lg px-3 py-2.5 text-left transition-colors duration-150 ${
    isCurrent
      ? "bg-[var(--accent-soft)] ring-1 ring-[color-mix(in_srgb,var(--accent)_28%,transparent)] cursor-default"
      : "hover:bg-stone-50 cursor-pointer"
  }`;

  if (isCurrent) {
    return (
      <div className={className} aria-current="page">
        {inner}
      </div>
    );
  }

  return (
    <a
      href={app.href}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
    >
      {inner}
    </a>
  );
}

export default function TatvaEcosystemMenu() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const apps = getTatvaEcosystemApps();

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="Tatva Ecosystem apps"
        className={`inline-flex items-center justify-center w-9 h-9 rounded-lg border transition-colors duration-150 ${
          open
            ? "border-stone-300 bg-stone-100 text-stone-800"
            : "border-stone-200 text-stone-600 hover:bg-stone-50 hover:text-stone-900"
        }`}
      >
        <GridIcon />
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Tatva Ecosystem"
          className="absolute right-0 top-full mt-2 w-[min(calc(100vw-2rem),22rem)] rounded-xl border border-stone-200 bg-white shadow-[var(--shadow-lg)] z-[60] overflow-hidden animate-in fade-in zoom-in-95 duration-150"
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-stone-100">
            <span className="text-sm font-semibold text-stone-900">
              Tatva Ecosystem
            </span>
            <span className="text-xs text-stone-400">{apps.length} apps</span>
          </div>

          <div className="grid grid-cols-2 gap-1 p-2">
            {apps.map((app) => (
              <AppTile
                key={app.id}
                app={app}
                isCurrent={app.id === CURRENT_APP_ID}
              />
            ))}
          </div>

          <div className="flex items-center justify-between gap-3 px-4 py-3 border-t border-stone-100 bg-stone-50/70">
            <p className="text-xs text-stone-500">
              You&apos;re using{" "}
              <span className="font-semibold text-stone-800">
                {CURRENT_APP_LABEL}
              </span>
            </p>
            <a
              href="https://tatvaops.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-stone-500 hover:text-[var(--accent)] whitespace-nowrap transition-colors"
              onClick={() => setOpen(false)}
            >
              Manage apps →
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
