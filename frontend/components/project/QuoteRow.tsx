"use client";

import React from "react";
import type { VendorQuote } from "@/lib/project-types";
import { formatInr } from "@/lib/project-types";
import { MAX_COMPARE_QUOTES } from "@/lib/compare-limits";
import { QuoteStatusBadge, TierBadge } from "@/components/ui/Badge";

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
  const showFinalized = quote.isFinalizeQuote === true;

  return (
    <label
      data-quote-number={quote.quoteNumber}
      data-is-finalize-quote={showFinalized ? "true" : "false"}
      className={`flex items-center gap-3 p-3.5 rounded-lg border transition-all duration-150 ${
        disabled
          ? "border-stone-100 bg-stone-50/70 opacity-60 cursor-not-allowed"
          : selected
            ? "border-[var(--accent)] bg-[var(--accent-soft)] ring-1 ring-[var(--accent-ring)] cursor-pointer"
            : "border-stone-200 hover:border-stone-300 hover:bg-stone-50/80 cursor-pointer"
      }`}
      title={
        disabled
          ? disabledReason ||
            `Maximum ${MAX_COMPARE_QUOTES} quotes — deselect one to pick another`
          : undefined
      }
    >
      <span className="relative flex items-center justify-center shrink-0">
        <input
          type="checkbox"
          checked={selected}
          disabled={disabled}
          onChange={onToggle}
          className="peer sr-only"
        />
        <span
          aria-hidden
          className={`flex h-5 w-5 items-center justify-center rounded-md border transition-colors duration-150 ${
            selected
              ? "border-[var(--accent)] bg-[var(--accent)] text-white"
              : "border-stone-300 bg-white"
          } ${disabled ? "opacity-50" : ""}`}
        >
          {selected ? (
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path
                d="M2.5 6.2L4.8 8.5L9.5 3.5"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          ) : null}
        </span>
      </span>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-stone-900 text-sm">
            #{quote.quoteNumber}
          </span>
          <QuoteStatusBadge status={quote.status} />
          {showFinalized ? (
            <span
              className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-md bg-violet-700 text-white"
              title="isFinalizeQuote: true"
              data-testid="quote-finalized-badge"
            >
              Finalized
            </span>
          ) : null}
          {quote.tier ? <TierBadge tier={quote.tier} /> : null}
        </div>
        {quote.label ? (
          <p className="text-xs text-stone-500 mt-0.5 truncate">{quote.label}</p>
        ) : null}
        <p className="text-[11px] text-stone-400 mt-0.5">
          {vendorName}
          {quote.lineItems > 0 ? ` · ${quote.lineItems} items` : ""}
          {quote.date && quote.date !== "—" ? ` · ${quote.date}` : ""}
        </p>
        {disabled && disabledReason ? (
          <p className="text-[11px] text-amber-700 mt-1 leading-snug">
            {disabledReason}
          </p>
        ) : null}
      </div>
      <div className="text-right shrink-0">
        <p className="qs-money text-stone-900 text-sm">{formatInr(quote.amount)}</p>
      </div>
    </label>
  );
}
