"use client";

import { useEffect, useMemo, useState } from "react";

export type CompareProgressStage =
  | "queued"
  | "extracting"
  | "comparing"
  | "recommending"
  | "done"
  | "";

type Props = {
  message: string;
  processed: number;
  total: number;
  stage?: CompareProgressStage;
  /** Standalone PDF lane — show typical timing hint */
  isPdfLane?: boolean;
};

const STEPS: { id: CompareProgressStage; label: string; detail: string }[] = [
  {
    id: "extracting",
    label: "Load vendor quotes",
    detail: "Reading line items and totals",
  },
  {
    id: "comparing",
    label: "Build comparison",
    detail: "Aligning categories and market estimates",
  },
  {
    id: "recommending",
    label: "Generate recommendation",
    detail: "Summarizing procurement guidance",
  },
];

function stepIndex(stage: CompareProgressStage): number {
  if (stage === "comparing") return 1;
  if (stage === "recommending" || stage === "done") return 2;
  if (stage === "extracting" || stage === "queued") return 0;
  return 0;
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m === 0) return `${s}s`;
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

export default function CompareLoadingPanel({
  message,
  processed,
  total,
  stage = "",
  isPdfLane = false,
}: Props) {
  const [elapsed, setElapsed] = useState(0);
  const activeStep = stepIndex(stage);

  useEffect(() => {
    const t0 = Date.now();
    const id = window.setInterval(() => {
      setElapsed(Math.floor((Date.now() - t0) / 1000));
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  const hasCount = total > 0;
  const pct = useMemo(() => {
    if (!hasCount)
      return stage === "recommending" ? 85 : stage === "comparing" ? 55 : 15;
    const base = Math.round((processed / total) * 55);
    if (stage === "comparing") return Math.max(base, 60);
    if (stage === "recommending") return Math.max(base, 85);
    return Math.max(base, 10);
  }, [hasCount, processed, total, stage]);

  const timingHint = useMemo(() => {
    if (!isPdfLane) return "Hang tight — building your procurement analysis.";
    if (total <= 1) return "Usually 1–3 minutes per PDF quote.";
    if (total === 2) return "Usually 2–4 minutes for 2 PDFs (read in parallel).";
    return "Usually 3–5 minutes for 3 PDFs (read in parallel).";
  }, [isPdfLane, total]);

  return (
    <div
      className="mt-2 qs-card p-6 border-[color-mix(in_srgb,var(--accent)_25%,var(--border))]"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-col gap-5">
        <div className="flex items-start gap-4">
          <div className="relative flex h-11 w-11 shrink-0 items-center justify-center">
            <div className="absolute h-11 w-11 animate-spin rounded-full border-[3px] border-stone-200 border-t-[var(--accent)]" />
            <div className="h-2 w-2 rounded-full bg-[var(--accent)]" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-stone-900">{message}</p>
            {hasCount && (
              <p className="text-xs font-medium text-[var(--accent)] mt-0.5">
                {processed} of {total} quote{total === 1 ? "" : "s"} processed
              </p>
            )}
            <p className="text-xs text-stone-500 mt-1">{timingHint}</p>
            <p className="text-[11px] text-stone-400 mt-1 tabular-nums">
              Elapsed: {formatElapsed(elapsed)}
            </p>
          </div>
        </div>

        <ol className="grid gap-2 sm:grid-cols-3">
          {STEPS.map((step, i) => {
            const done = i < activeStep;
            const active = i === activeStep;
            return (
              <li
                key={step.id}
                className={`rounded-lg border px-3 py-2.5 text-xs transition-colors duration-150 ${
                  done
                    ? "border-[var(--success-border)] bg-[var(--success-soft)] text-emerald-800"
                    : active
                      ? "border-[color-mix(in_srgb,var(--accent)_40%,var(--border))] bg-[var(--accent-soft)] text-[var(--accent)] font-medium"
                      : "border-stone-100 bg-stone-50/80 text-stone-400"
                }`}
              >
                <div className="font-semibold">
                  {done ? "Done · " : active ? "In progress · " : ""}
                  {step.label}
                </div>
                <div className="mt-0.5 opacity-80">{step.detail}</div>
              </li>
            );
          })}
        </ol>

        <div className="w-full">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-stone-200">
            <div
              className="h-full rounded-full bg-[var(--accent)] transition-all duration-500 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-[10px] text-stone-400 mt-1.5 text-center">
            Partial results appear as steps complete — no refresh needed.
          </p>
        </div>
      </div>
    </div>
  );
}
