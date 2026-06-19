"use client";

import React from "react";
import type { ProjectVendor } from "@/lib/dummy-project-data";
import { QuoteRow } from "./QuoteRow";

type VendorCardProps = {
  vendor: ProjectVendor;
  selectedQuoteIds: Set<string>;
  onToggleQuote: (quoteId: string) => void;
  onCompareVendorQuotes: (vendorId: string) => void;
};

export function VendorCard({
  vendor,
  selectedQuoteIds,
  onToggleQuote,
  onCompareVendorQuotes,
}: VendorCardProps) {
  const vendorSelectedCount = vendor.quotes.filter((q) => selectedQuoteIds.has(q.id)).length;
  const canCompareAll = vendor.quotes.length >= 2;

  return (
    <section className="qs-card overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center text-slate-600 font-bold text-sm shrink-0">
            {vendor.companyName.charAt(0)}
          </div>
          <div className="min-w-0">
            <h3 className="font-semibold text-slate-900 text-sm leading-snug truncate">
              {vendor.companyName}
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              {vendor.contactName} · {vendor.email}
            </p>
            <p className="text-[11px] text-slate-400 mt-1">
              {vendor.quotes.length} quote{vendor.quotes.length !== 1 ? "s" : ""} submitted
              {vendorSelectedCount > 0 && (
                <span className="text-[#c04a00] font-medium"> · {vendorSelectedCount} selected</span>
              )}
            </p>
          </div>
        </div>
        {canCompareAll && (
          <button
            type="button"
            onClick={() => onCompareVendorQuotes(vendor.id)}
            className="shrink-0 text-xs font-medium text-[#c04a00] hover:text-[#a84000] px-3 py-1.5 rounded-lg border border-[#c04a00]/25 hover:bg-orange-50 transition-colors"
          >
            Compare all ({vendor.quotes.length})
          </button>
        )}
      </div>

      <div className="p-4 space-y-2">
        {vendor.quotes.map((quote) => (
          <QuoteRow
            key={quote.id}
            quote={quote}
            vendorName={vendor.companyName}
            selected={selectedQuoteIds.has(quote.id)}
            onToggle={() => onToggleQuote(quote.id)}
          />
        ))}
      </div>
    </section>
  );
}
