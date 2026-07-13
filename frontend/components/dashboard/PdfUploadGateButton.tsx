"use client";

import React, { useEffect, useId, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  STANDALONE_PDF_RECOVERY_MESSAGE,
  STANDALONE_PDF_UPLOAD_ENABLED,
} from "@/lib/feature-flags";

type PdfUploadGateButtonProps = {
  children: React.ReactNode;
  className?: string;
  /** Prefetch /compare when upload is enabled. */
  prefetch?: boolean;
};

/** Shared recovery dialog for the temporary PDF-upload lock. */
export function PdfUploadRecoveryModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-white shadow-xl border border-slate-200 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id={titleId} className="text-lg font-bold text-slate-900">
          PDF upload under recovery
        </h2>
        <p className="mt-3 text-sm text-slate-600 leading-relaxed">
          {STANDALONE_PDF_RECOVERY_MESSAGE}
        </p>
        <button
          type="button"
          onClick={onClose}
          className="mt-5 w-full inline-flex items-center justify-center px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-[#c04a00] hover:bg-[#a84000] transition-colors"
        >
          Got it
        </button>
      </div>
    </div>
  );
}

/**
 * Looks like the normal Upload & compare CTA.
 * When standalone PDF upload is locked, opens a recovery popup instead of navigating.
 */
export function PdfUploadGateButton({
  children,
  className,
  prefetch = true,
}: PdfUploadGateButtonProps) {
  const [open, setOpen] = useState(false);

  if (STANDALONE_PDF_UPLOAD_ENABLED) {
    return (
      <Link href="/compare" prefetch={prefetch} className={className}>
        {children}
      </Link>
    );
  }

  return (
    <>
      <button
        type="button"
        className={className}
        onClick={() => setOpen(true)}
      >
        {children}
      </button>
      <PdfUploadRecoveryModal open={open} onClose={() => setOpen(false)} />
    </>
  );
}

/** If user lands on /compare while locked, show popup then send them home. */
export function StandalonePdfCompareGuard({ active }: { active: boolean }) {
  const router = useRouter();
  const [open, setOpen] = useState(active);

  useEffect(() => {
    setOpen(active);
  }, [active]);

  if (!active) return null;

  return (
    <PdfUploadRecoveryModal
      open={open}
      onClose={() => {
        setOpen(false);
        router.push("/");
      }}
    />
  );
}
