"use client";

import React from "react";
import type { ProjectVendor, QuoteTier } from "@/lib/project-types";
import { QUOTE_TIER_LABELS } from "@/lib/project-types";
import { MAX_COMPARE_QUOTES, MIN_COMPARE_QUOTES } from "@/lib/compare-limits";
import { QuoteRow } from "./QuoteRow";

type VendorCardProps = {
  vendor: ProjectVendor;
  selectedQuoteIds: Set<string>;
  selectionFull: boolean;
  /** Quote type of the currently selected quotes — new picks must match it. */
  selectedTier?: QuoteTier;
  onToggleQuote: (quoteId: string) => void;
  onCompareVendorQuotes: (vendorId: string) => void;
};

export function VendorCard({
  vendor,
  selectedQuoteIds,
  selectionFull,
  selectedTier,
  onToggleQuote,
  onCompareVendorQuotes,
}: VendorCardProps) {
  const vendorSelectedCount = vendor.quotes.filter((q) => selectedQuoteIds.has(q.id)).length;
  const canCompare = vendor.quotes.length >= MIN_COMPARE_QUOTES;
  const compareCount = Math.min(vendor.quotes.length, MAX_COMPARE_QUOTES);
  const hasMoreThanMax = vendor.quotes.length > MAX_COMPARE_QUOTES;

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
              {hasMoreThanMax && (
                <span className="text-amber-600"> · max {MAX_COMPARE_QUOTES} for compare</span>
              )}
              {vendorSelectedCount > 0 && (
                <span className="text-[#c04a00] font-medium"> · {vendorSelectedCount} selected</span>
              )}
            </p>
          </div>
        </div>
        {canCompare && (
          <button
            type="button"
            onClick={() => onCompareVendorQuotes(vendor.id)}
            className="shrink-0 text-xs font-medium text-[#c04a00] hover:text-[#a84000] px-3 py-1.5 rounded-lg border border-[#c04a00]/25 hover:bg-orange-50 transition-colors"
            title={
              hasMoreThanMax
                ? `Only ${MAX_COMPARE_QUOTES} quotes can be compared at a time`
                : undefined
            }
          >
            {hasMoreThanMax
              ? `Compare ${MAX_COMPARE_QUOTES} quotes`
              : `Compare all (${compareCount})`}
          </button>
        )}
      </div>

      <div className="p-4 space-y-2">
        {vendor.quotes.map((quote) => {
          const selected = selectedQuoteIds.has(quote.id);
          const tierMismatch = Boolean(
            selectedTier && quote.tier && quote.tier !== selectedTier
          );
          const disabled = (selectionFull || tierMismatch) && !selected;
          return (
            <QuoteRow
              key={quote.id}
              quote={quote}
              vendorName={vendor.companyName}
              selected={selected}
              disabled={disabled}
              disabledReason={
                tierMismatch && selectedTier
                  ? `You've selected ${QUOTE_TIER_LABELS[selectedTier]} quotes — pick another ${QUOTE_TIER_LABELS[selectedTier]} quote to compare`
                  : undefined
              }
              onToggle={() => onToggleQuote(quote.id)}
            />
          );
        })}
      </div>
    </section>
  );
}
