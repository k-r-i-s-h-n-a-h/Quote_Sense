"use client";

import React from "react";
import type { QuoteStatus, VendorQuote } from "@/lib/dummy-project-data";
import { formatInr } from "@/lib/dummy-project-data";

const STATUS_STYLE: Record<QuoteStatus, string> = {
  draft: "bg-slate-100 text-slate-600",
  submitted: "bg-emerald-50 text-emerald-700",
  revised: "bg-amber-50 text-amber-700",
};

type QuoteRowProps = {
  quote: VendorQuote;
  vendorName: string;
  selected: boolean;
  onToggle: () => void;
};

export function QuoteRow({ quote, vendorName, selected, onToggle }: QuoteRowProps) {
  return (
    <label
      className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
        selected
          ? "border-[#c04a00] bg-orange-50/50 ring-1 ring-[#c04a00]/20"
          : "border-slate-100 hover:border-slate-200 hover:bg-slate-50/80"
      }`}
    >
      <input
        type="checkbox"
        checked={selected}
        onChange={onToggle}
        className="w-4 h-4 rounded border-slate-300 text-[#c04a00] focus:ring-[#c04a00]/30 shrink-0"
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-slate-900 text-sm">#{quote.quoteNumber}</span>
          <span className={`text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded ${STATUS_STYLE[quote.status]}`}>
            {quote.status}
          </span>
        </div>
        <p className="text-xs text-slate-500 mt-0.5 truncate">{quote.label}</p>
        <p className="text-[11px] text-slate-400 mt-0.5">{vendorName} · {quote.lineItems} items · {quote.date}</p>
      </div>
      <div className="text-right shrink-0">
        <p className="font-bold text-slate-900 tabular-nums text-sm">{formatInr(quote.amount)}</p>
      </div>
    </label>
  );
}
