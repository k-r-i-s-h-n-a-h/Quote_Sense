"use client";

import React, { useEffect, useState } from "react";
import {
  lookupMarketRate,
  recommendMarketRate,
  verdictStyles,
  type MarketRateLookup,
} from "@/lib/market-rate";

export type MarketRatePanelProps = {
  serviceType?: string;
  serviceCategory: string;
  subService: string;
  pricingMethod: string;
  enteredRate?: number;
  className?: string;
};

/**
 * Shown beside a PM work item when type + main service + item + pricing method
 * match a row in market_moving_averages.
 */
export default function MarketRatePanel({
  serviceType = "ESSENTIAL",
  serviceCategory,
  subService,
  pricingMethod,
  enteredRate,
  className = "",
}: MarketRatePanelProps) {
  const [data, setData] = useState<MarketRateLookup | null>(null);
  const [loading, setLoading] = useState(false);

  const ready =
    serviceCategory.trim() &&
    subService.trim() &&
    pricingMethod.trim() &&
    pricingMethod !== "Select pricing method" &&
    subService !== "Select sub-service";

  useEffect(() => {
    if (!ready) {
      setData(null);
      return;
    }

    let cancelled = false;
    setLoading(true);

    (async () => {
      const result =
        enteredRate != null && enteredRate > 0
          ? await recommendMarketRate({
              service_type: serviceType,
              service_category: serviceCategory,
              sub_service: subService,
              pricing_method: pricingMethod,
              entered_rate: enteredRate,
            })
          : await lookupMarketRate({
              service_type: serviceType,
              service_category: serviceCategory,
              sub_service: subService,
              pricing_method: pricingMethod,
            });

      if (!cancelled) {
        setData(result.recommend ? result : null);
        setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    ready,
    serviceType,
    serviceCategory,
    subService,
    pricingMethod,
    enteredRate,
  ]);

  if (!ready) return null;

  if (loading) {
    return (
      <aside className={`qs-card p-4 ${className}`}>
        <div className="h-3 w-24 qs-skeleton mb-3" />
        <div className="h-7 w-32 qs-skeleton mb-2" />
        <div className="h-3 w-full qs-skeleton" />
      </aside>
    );
  }

  if (!data?.recommend || !data.market_rate) return null;

  const styles = verdictStyles(data.verdict);
  const unit = data.pricing_method || pricingMethod;
  const entered = data.entered_rate ?? enteredRate;
  const hasEntered = entered != null && entered > 0;
  const diffPct =
    hasEntered && data.market_rate > 0
      ? ((Number(entered) - data.market_rate) / data.market_rate) * 100
      : null;

  const verdictLabel =
    data.verdict === "low"
      ? "Below market"
      : data.verdict === "high"
        ? "Above market"
        : data.verdict === "fair"
          ? "Aligned with market"
          : null;

  return (
    <aside
      className={`rounded-xl border p-4 shadow-[var(--shadow-xs)] ${styles.border} ${styles.bg} ${className}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-stone-500">
            Market position
          </p>
          <p className={`mt-1 text-xl font-bold tabular-nums ${styles.text}`}>
            ₹{data.market_rate.toLocaleString("en-IN")}
            <span className="text-sm font-normal text-stone-600">
              {" "}
              / {unit}
            </span>
          </p>
          <p className="mt-1 text-xs text-stone-600">
            Based on {data.weight} vendor quote
            {data.weight === 1 ? "" : "s"}
          </p>
        </div>
        {(verdictLabel || data.verdict) && (
          <span
            className={`shrink-0 rounded-md px-2.5 py-1 text-xs font-semibold ${styles.badge}`}
          >
            {verdictLabel || data.verdict}
          </span>
        )}
      </div>

      {hasEntered && (
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg bg-white/70 border border-white/80 px-3 py-2">
            <dt className="text-[11px] text-stone-500">Your quote</dt>
            <dd className="font-semibold tabular-nums text-stone-900">
              ₹{Number(entered).toLocaleString("en-IN")}
              <span className="text-xs font-normal text-stone-500">
                {" "}
                / {unit}
              </span>
            </dd>
          </div>
          <div className="rounded-lg bg-white/70 border border-white/80 px-3 py-2">
            <dt className="text-[11px] text-stone-500">Market average</dt>
            <dd className="font-semibold tabular-nums text-stone-900">
              ₹{data.market_rate.toLocaleString("en-IN")}
              <span className="text-xs font-normal text-stone-500">
                {" "}
                / {unit}
              </span>
            </dd>
          </div>
        </dl>
      )}

      {diffPct != null && (
        <p className={`mt-3 text-sm font-semibold tabular-nums ${styles.text}`}>
          {diffPct === 0
            ? "At market average"
            : `${diffPct > 0 ? "+" : ""}${diffPct.toFixed(1)}% vs market`}
        </p>
      )}

      {data.message && (
        <p className={`mt-2 text-sm leading-relaxed ${styles.text}`}>
          {data.message}
        </p>
      )}
    </aside>
  );
}
