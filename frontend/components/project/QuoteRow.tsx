"use client";

import React from "react";
import type { QuoteStatus, QuoteTier, VendorQuote } from "@/lib/project-types";
import { formatInr, QUOTE_TIER_LABELS } from "@/lib/project-types";

const TIER_STYLE: Record<QuoteTier, string> = {
  ESSENTIAL: "bg-lime-50 text-lime-800",
  MID_SEGMENT: "bg-sky-50 text-sky-700",
  LUXURY: "bg-violet-50 text-violet-700",
};

const STATUS_STYLE: Record<QuoteStatus, string> = {
  draft: "bg-slate-100 text-slate-600",
  submitted: "bg-emerald-50 text-emerald-700",
  revised: "bg-amber-50 text-amber-700",
  finalized: "bg-violet-50 text-violet-800",
};

type QuoteRowProps = {
  quote: VendorQuote;
  vendorName: string;
  selected: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onToggle: () => void;
};

export function QuoteRow({
  quote,
  vendorName,
  selected,
  disabled = false,
  disabledReason,
  onToggle,
}: QuoteRowProps) {
  return (
    <label
      className={`flex items-center gap-3 p-3 rounded-lg border transition-all ${
        disabled
          ? "border-slate-100 bg-slate-50/60 opacity-55 cursor-not-allowed"
          : selected
            ? "border-[#c04a00] bg-orange-50/50 ring-1 ring-[#c04a00]/20 cursor-pointer"
            : "border-slate-100 hover:border-slate-200 hover:bg-slate-50/80 cursor-pointer"
      }`}
      title={
        disabled
          ? disabledReason || "Maximum 3 quotes — deselect one to pick another"
          : undefined
      }
    >
      <input
        type="checkbox"
        checked={selected}
        disabled={disabled}
        onChange={onToggle}
        className="w-4 h-4 rounded border-slate-300 text-[#c04a00] focus:ring-[#c04a00]/30 shrink-0 disabled:cursor-not-allowed"
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-slate-900 text-sm">#{quote.quoteNumber}</span>
          <span
            className={`text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded ${STATUS_STYLE[quote.status]}`}
            title={
              quote.status === "finalized"
                ? "Customer selected this as the final quote (isFinalizeQuote)"
                : "Quote status"
            }
          >
            {quote.status === "finalized" ? "finalized" : quote.status}
          </span>
          {quote.tier && (
            <span
              className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${TIER_STYLE[quote.tier]}`}
            >
              {QUOTE_TIER_LABELS[quote.tier]}
            </span>
          )}
        </div>
        {quote.label && (
          <p className="text-xs text-slate-500 mt-0.5 truncate">{quote.label}</p>
        )}
        <p className="text-[11px] text-slate-400 mt-0.5">
          {vendorName} · {quote.lineItems} items · {quote.date}
        </p>
      </div>
      <div className="text-right shrink-0">
        <p className="font-bold text-slate-900 tabular-nums text-sm">{formatInr(quote.amount)}</p>
      </div>
    </label>
  );
}
