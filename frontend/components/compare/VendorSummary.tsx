"use client";

import { useMemo } from "react";
import {
  buildVendorLabels,
  formatInrFull,
  type VendorMeta,
} from "@/lib/format";
import { vendorColor } from "@/lib/vendor-colors";

type ChartRow = { vendor: string; total: number };

type Props = {
  chartData: ChartRow[];
  vendors: string[];
  tableData: Record<string, unknown>[];
  meta?: Record<string, VendorMeta>;
};

function relativeLabel(total: number, min: number, max: number): string {
  if (!Number.isFinite(total) || total <= 0) return "Not quoted";
  if (min === max) return "Matched totals";
  if (total === min) return "Lowest total";
  if (total === max) return "Highest total";
  return "Mid-range";
}

export default function VendorSummary({
  chartData,
  vendors,
  tableData: _tableData,
  meta,
}: Props) {
  const labels = useMemo(
    () => buildVendorLabels(vendors, meta),
    [vendors, meta]
  );

  const rows = useMemo(() => {
    const byVendor = new Map(chartData.map((d) => [d.vendor, Number(d.total) || 0]));
    const totals = vendors.map((v) => byVendor.get(v) || 0).filter((t) => t > 0);
    const min = totals.length ? Math.min(...totals) : 0;
    const max = totals.length ? Math.max(...totals) : 0;

    return vendors.map((vendor, index) => {
      const total = byVendor.get(vendor) || 0;
      return {
        vendor,
        total,
        index,
        label: labels[vendor]?.label || vendor.split(" (")[0],
        full: labels[vendor]?.full || vendor,
        position: relativeLabel(total, min, max),
      };
    });
  }, [chartData, vendors, labels]);

  if (rows.length === 0) return null;

  return (
    <section className="qs-card p-5 md:p-6">
      <div className="mb-4">
        <h2 className="qs-section-title">Vendor overview</h2>
        <p className="qs-section-sub">Totals at a glance.</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {rows.map((row) => (
          <article
            key={row.vendor}
            className="rounded-lg border border-stone-200 bg-stone-50/40 px-4 py-3.5"
            title={row.full}
          >
            <div className="flex items-center gap-2 mb-2">
              <span
                className="h-2.5 w-2.5 rounded-full shrink-0"
                style={{ backgroundColor: vendorColor(row.index) }}
                aria-hidden
              />
              <h3 className="text-sm font-semibold text-stone-900 truncate">
                {row.label}
              </h3>
            </div>
            <p className="qs-money text-xl text-stone-900">
              {row.total > 0 ? formatInrFull(row.total) : "—"}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
              <span className="rounded-md bg-white border border-stone-200 px-1.5 py-0.5 text-stone-600">
                {row.position}
              </span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
