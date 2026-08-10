"use client";

import React from "react";
import { getQuoteSelectionSummary, type ProjectData } from "@/lib/project-types";
import {
  MAX_COMPARE_QUOTES,
  MIN_COMPARE_QUOTES,
  isValidCompareCount,
} from "@/lib/compare-limits";

type CompareActionBarProps = {
  project: ProjectData;
  selectedIds: string[];
  limitMessage?: string | null;
  onCompare: () => void;
  onClear: () => void;
};

function selectionCopy(count: number): string {
  if (count <= 0) return "Select 2–3 quotes to compare";
  if (count === 1) return "Select at least 1 more quote";
  if (count === 2) return "2 quotes selected";
  if (count === 3) return "3 quotes selected";
  return `${count} quotes selected`;
}

export function CompareActionBar({
  project,
  selectedIds,
  limitMessage,
  onCompare,
  onClear,
}: CompareActionBarProps) {
  const count = selectedIds.length;
  if (count === 0) return null;

  const summary = getQuoteSelectionSummary(project, selectedIds);
  const vendorCount = new Set(summary.map((s) => s.vendor.id)).size;
  const canCompare = isValidCompareCount(count);
  const overLimit = count > MAX_COMPARE_QUOTES;
  const needed = Math.max(0, MIN_COMPARE_QUOTES - count);

  return (
    <div className="fixed bottom-0 inset-x-0 z-40 p-3 sm:p-4 pointer-events-none pb-[max(0.75rem,env(safe-area-inset-bottom))]">
      <div className="max-w-4xl mx-auto pointer-events-auto">
        <div className="bg-white/95 backdrop-blur-md border border-stone-200 rounded-xl shadow-[var(--shadow-lg)] px-4 py-3.5 sm:px-5 sm:py-4 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-stone-900">
              {selectionCopy(count)}
              <span className="text-stone-400 font-normal">
                {" "}
                · {vendorCount} vendor{vendorCount !== 1 ? "s" : ""}
              </span>
            </p>
            <p className="text-xs text-stone-500 mt-0.5 truncate">
              {summary.map((s) => `#${s.quote.quoteNumber}`).join(" · ")}
            </p>
            {!canCompare && !overLimit && needed > 0 && (
              <p className="text-xs text-amber-700 mt-1">
                Select {MIN_COMPARE_QUOTES}–{MAX_COMPARE_QUOTES} quotes of the same
                tier to compare
              </p>
            )}
            {(limitMessage || overLimit) && (
              <p className="text-xs text-amber-700 mt-1" role="alert">
                {limitMessage ||
                  `Cannot compare more than ${MAX_COMPARE_QUOTES} quotes — deselect ${count - MAX_COMPARE_QUOTES}.`}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={onClear}
              className="qs-btn qs-btn-ghost flex-1 sm:flex-none"
            >
              Clear
            </button>
            <button
              type="button"
              disabled={!canCompare}
              onClick={onCompare}
              className="qs-btn qs-btn-primary flex-1 sm:flex-none"
            >
              Compare quotes →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
