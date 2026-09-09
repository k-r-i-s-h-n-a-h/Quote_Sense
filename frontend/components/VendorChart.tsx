"use client";

import { useMemo } from "react";
import {
  buildVendorLabels,
  formatInrFull,
  truncateLabel,
  type VendorMeta,
} from "../lib/format";
import { vendorColor } from "../lib/vendor-colors";

type ChartRow = { vendor: string; total: number };

type ChartPoint = ChartRow & {
  company: string;
  quote: string;
  labelFull: string;
  color: string;
  widthPct: number;
  note: string;
};

export default function VendorChart({
  data,
  meta,
}: {
  data: ChartRow[];
  meta?: Record<string, VendorMeta>;
}) {
  const points: ChartPoint[] = useMemo(() => {
    const labels = buildVendorLabels(
      data.map((d) => d.vendor),
      meta
    );
    const totals = data.map((d) => Number(d.total) || 0);
    const max = Math.max(0, ...totals);
    const positive = totals.filter((t) => t > 0);
    const min = positive.length ? Math.min(...positive) : 0;

    return data.map((row, index) => {
      const info = labels[row.vendor];
      const total = Number(row.total) || 0;
      const quoteBits: string[] = [];
      if (info.quoteNumber) quoteBits.push(`#${info.quoteNumber}`);
      if (info.quoteDate) quoteBits.push(info.quoteDate);
      if (info.variant && !info.quoteNumber) {
        quoteBits.push(truncateLabel(info.variant, 20));
      }

      let note = "";
      if (total <= 0) note = "Not quoted";
      else if (min === max) note = "Matched totals";
      else if (total === min) note = "Lowest billed total";
      else note = `${formatInrFull(total - min)} more than lowest`;

      return {
        ...row,
        total,
        company: info.company || row.vendor,
        quote: quoteBits.join(" · "),
        labelFull: info.full,
        color: vendorColor(index),
        widthPct: max > 0 ? Math.max(4, (total / max) * 100) : 0,
        note,
      };
    });
  }, [data, meta]);

  if (points.length === 0) return null;

  return (
    <ul className="space-y-5" aria-label="Billed grand total per quote">
      {points.map((p) => (
        <li key={p.vendor} title={p.labelFull}>
          <div className="flex items-baseline justify-between gap-4 mb-1.5">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-stone-900 truncate">
                {p.company}
              </p>
              {p.quote ? (
                <p className="text-xs text-stone-500 mt-0.5 truncate">{p.quote}</p>
              ) : null}
            </div>
            <p className="qs-money text-lg text-stone-900 tabular-nums shrink-0">
              {p.total > 0 ? formatInrFull(p.total) : "—"}
            </p>
          </div>
          <div
            className="h-2.5 rounded-full bg-stone-100 overflow-hidden"
            aria-hidden
          >
            <div
              className="h-full rounded-full transition-[width] duration-300"
              style={{
                width: `${p.total > 0 ? p.widthPct : 0}%`,
                backgroundColor: p.color,
              }}
            />
          </div>
          <p className="mt-1.5 text-[11px] text-stone-500">{p.note}</p>
        </li>
      ))}
    </ul>
  );
}
