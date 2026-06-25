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

export function CompareActionBar({
  project,
  selectedIds,
  limitMessage,
  onCompare,
  onClear,
}: CompareActionBarProps) {
  if (selectedIds.length === 0) return null;

  const summary = getQuoteSelectionSummary(project, selectedIds);
  const vendorCount = new Set(summary.map((s) => s.vendor.id)).size;
  const canCompare = isValidCompareCount(selectedIds.length);
  const overLimit = selectedIds.length > MAX_COMPARE_QUOTES;

  return (
    <div className="fixed bottom-0 inset-x-0 z-40 p-4 pointer-events-none">
      <div className="max-w-4xl mx-auto pointer-events-auto">
        <div className="bg-white border border-slate-200 rounded-2xl shadow-lg shadow-slate-200/60 px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-900">
              {selectedIds.length}/{MAX_COMPARE_QUOTES} quote
              {selectedIds.length !== 1 ? "s" : ""} selected
              <span className="text-slate-400 font-normal">
                {" "}
                from {vendorCount} vendor{vendorCount !== 1 ? "s" : ""}
              </span>
            </p>
            <p className="text-xs text-slate-500 mt-0.5 truncate">
              {summary.map((s) => `#${s.quote.quoteNumber}`).join(" · ")}
            </p>
            {!canCompare && !overLimit && (
              <p className="text-xs text-amber-600 mt-1">
                Select {MIN_COMPARE_QUOTES}–{MAX_COMPARE_QUOTES} quotes to compare
              </p>
            )}
            {(limitMessage || overLimit) && (
              <p className="text-xs text-amber-600 mt-1" role="alert">
                {limitMessage ||
                  `Cannot compare more than ${MAX_COMPARE_QUOTES} quotes — deselect ${selectedIds.length - MAX_COMPARE_QUOTES}.`}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={onClear}
              className="px-4 py-2.5 text-sm font-medium text-slate-600 hover:text-slate-900 rounded-xl hover:bg-slate-50 transition-colors"
            >
              Clear
            </button>
            <button
              type="button"
              disabled={!canCompare}
              onClick={onCompare}
              className="px-5 py-2.5 text-sm font-semibold text-white rounded-xl bg-[#c04a00] hover:bg-[#a84000] disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-sm"
            >
              Compare quotes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
