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

const STEPS: { id: CompareProgressStage; label: string }[] = [
  { id: "extracting", label: "Read PDF quotes" },
  { id: "comparing", label: "Build comparison matrix" },
  { id: "recommending", label: "Write AI recommendation" },
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
    if (!hasCount) return stage === "recommending" ? 85 : stage === "comparing" ? 55 : 15;
    const base = Math.round((processed / total) * 55);
    if (stage === "comparing") return Math.max(base, 60);
    if (stage === "recommending") return Math.max(base, 85);
    return Math.max(base, 10);
  }, [hasCount, processed, total, stage]);

  const timingHint = useMemo(() => {
    if (!isPdfLane) return "Hang tight — we're crunching the numbers.";
    if (total <= 1) return "Usually 1–3 minutes per PDF quote.";
    if (total === 2) return "Usually 2–4 minutes for 2 PDFs (read in parallel).";
    return "Usually 3–5 minutes for 3 PDFs (read in parallel).";
  }, [isPdfLane, total]);

  return (
    <div
      className="mt-5 rounded-xl border border-orange-200/80 bg-gradient-to-b from-orange-50/80 to-white p-6 shadow-sm"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-col gap-5">
        <div className="flex items-start gap-4">
          <div className="relative flex h-12 w-12 shrink-0 items-center justify-center">
            <div className="absolute h-12 w-12 animate-spin rounded-full border-[3px] border-orange-200 border-t-[#c04a00]" />
            <span className="text-lg" aria-hidden>
              📊
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-slate-900">{message}</p>
            {hasCount && (
              <p className="text-xs font-medium text-[#c04a00] mt-0.5">
                {processed} of {total} quote{total === 1 ? "" : "s"} extracted
              </p>
            )}
            <p className="text-xs text-slate-500 mt-1">{timingHint}</p>
            <p className="text-[11px] text-slate-400 mt-1 tabular-nums">
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
                className={`rounded-lg border px-3 py-2.5 text-xs transition-colors ${
                  done
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : active
                      ? "border-[#c04a00]/40 bg-orange-50 text-[#9a3a00] font-medium"
                      : "border-slate-100 bg-slate-50/80 text-slate-400"
                }`}
              >
                <span className="mr-1.5">{done ? "✓" : active ? "●" : "○"}</span>
                {step.label}
              </li>
            );
          })}
        </ol>

        <div className="w-full">
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#c04a00] to-orange-400 transition-all duration-700 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-[10px] text-slate-400 mt-1.5 text-center">
            Results appear below as each step completes — you don&apos;t need to refresh.
          </p>
        </div>
      </div>
    </div>
  );
}
