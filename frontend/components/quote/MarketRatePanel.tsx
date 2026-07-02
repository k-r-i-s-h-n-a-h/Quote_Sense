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
      <aside
        className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm ${className}`}
      >
        <p className="text-xs text-slate-500">Checking market rates…</p>
      </aside>
    );
  }

  if (!data?.recommend || !data.market_rate) return null;

  const styles = verdictStyles(data.verdict);
  const unit = data.pricing_method || pricingMethod;

  return (
    <aside
      className={`rounded-xl border p-4 shadow-sm ${styles.border} ${styles.bg} ${className}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Market guidance
          </p>
          <p className={`mt-1 text-lg font-bold ${styles.text}`}>
            ~₹{data.market_rate.toLocaleString("en-IN")}
            <span className="text-sm font-normal text-slate-600"> / {unit}</span>
          </p>
          <p className="mt-1 text-xs text-slate-600">
            Based on {data.weight} vendor quote{data.weight === 1 ? "" : "s"}
          </p>
        </div>
        {data.verdict && (
          <span
            className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${styles.badge}`}
          >
            {data.verdict}
          </span>
        )}
      </div>
      {data.message && (
        <p className={`mt-3 text-sm leading-relaxed ${styles.text}`}>{data.message}</p>
      )}
      {data.band_low != null && data.band_high != null && (
        <p className="mt-2 text-xs text-slate-600">
          Typical range: ₹{data.band_low.toLocaleString("en-IN")} – ₹
          {data.band_high.toLocaleString("en-IN")} / {unit}
        </p>
      )}
    </aside>
  );
}
