"use client";

import { useMemo, useState } from "react";
import {
  buildVendorLabels,
  formatInrFull,
  type VendorMeta,
} from "../lib/format";

type Row = Record<string, any>;

type Stat = {
  vendor: string;
  name: string;
  total: number;
  items: number;
};

const ALL = "__all__";

const BAR_COLORS = [
  "#3b82f6",
  "#8b5cf6",
  "#f59e0b",
  "#ec4899",
  "#14b8a6",
  "#ef4444",
];

export default function VendorInsights({
  tableData,
  vendors,
  meta,
}: {
  tableData: Row[];
  vendors: string[];
  meta?: Record<string, VendorMeta>;
}) {
  const labels = useMemo(
    () => buildVendorLabels(vendors, meta),
    [vendors, meta]
  );

  const nameOf = (v: string) => labels[v]?.label || v.split(" (")[0];

  const categories = useMemo(() => {
    const seen: string[] = [];
    for (const r of tableData) {
      if (r.category && !seen.includes(r.category)) seen.push(r.category);
    }
    return seen;
  }, [tableData]);

  const [selected, setSelected] = useState<string>(ALL);

  const rows = useMemo(
    () =>
      selected === ALL
        ? tableData
        : tableData.filter((r) => r.category === selected),
    [selected, tableData]
  );

  const stats: Stat[] = useMemo(() => {
    return vendors
      .map((v) => {
        let total = 0;
        let items = 0;
        for (const r of rows) {
          const val = Number(r[v]) || 0;
          if (val > 0) {
            total += val;
            items += 1;
          }
        }
        return { vendor: v, name: nameOf(v), total, items };
      })
      .sort((a, b) => a.total - b.total);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, vendors, labels]);

  const funded = stats.filter((s) => s.total > 0);
  const maxTotal = Math.max(1, ...stats.map((s) => s.total));
  const cheapest = funded[0];
  const priciest = funded[funded.length - 1];

  // "Lowest cost" vendor per category — the at-a-glance "who is good at what".
  const bestByCategory = useMemo(() => {
    return categories.map((cat) => {
      const catRows = tableData.filter((r) => r.category === cat);
      let best: { vendor: string; total: number } | null = null;
      for (const v of vendors) {
        let total = 0;
        for (const r of catRows) total += Number(r[v]) || 0;
        if (total > 0 && (best === null || total < best.total)) {
          best = { vendor: v, total };
        }
      }
      return { category: cat, best };
    });
  }, [categories, tableData, vendors]);

  const label = selected === ALL ? "all services" : selected;

  const savingsPct =
    cheapest && priciest && priciest.total > 0 && cheapest !== priciest
      ? Math.round(((priciest.total - cheapest.total) / priciest.total) * 100)
      : 0;

  return (
    <div className="qs-card p-6 md:p-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Who fits best, at a glance</h2>
          <p className="text-sm text-slate-500 mt-1">
            Pick a service to see which quote costs the least for that work.
          </p>
        </div>
        <label className="text-sm">
          <span className="block text-gray-500 mb-1 font-medium">Service</span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="w-full sm:w-64 border border-gray-300 rounded-lg px-3 py-2 text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={ALL}>All services (total)</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Plain-language headline */}
      {cheapest && (
        <div className="mb-6 rounded-lg bg-green-50 border border-green-200 p-4">
          <p className="text-sm text-green-900">
            <span className="font-bold">{cheapest.name}</span> has the lowest cost
            for <span className="font-semibold">{label}</span> at{" "}
            <span className="font-bold">{formatInrFull(cheapest.total)}</span>
            {savingsPct > 0 && priciest ? (
              <>
                {" "}— about <span className="font-bold">{savingsPct}%</span> cheaper
                than {priciest.name} ({formatInrFull(priciest.total)}).
              </>
            ) : (
              <>.</>
            )}
          </p>
        </div>
      )}

      {/* Horizontal cost bars (lower = better; cheapest highlighted green) */}
      <div className="space-y-4">
        {stats.map((s, i) => {
          const isBest = cheapest && s.vendor === cheapest.vendor && s.total > 0;
          const widthPct = s.total > 0 ? Math.max(4, (s.total / maxTotal) * 100) : 0;
          return (
            <div key={s.vendor} className="flex items-center gap-3">
              <div
                className="w-32 sm:w-44 shrink-0 text-right text-xs font-semibold text-gray-700 truncate"
                title={labels[s.vendor]?.full || s.vendor}
              >
                {s.name}
              </div>
              <div className="flex-1 h-7 bg-gray-100 rounded-md overflow-hidden relative">
                {s.total > 0 ? (
                  <div
                    className="h-full rounded-md transition-all duration-700 flex items-center justify-end pr-2"
                    style={{
                      width: `${widthPct}%`,
                      backgroundColor: isBest
                        ? "#16a34a"
                        : BAR_COLORS[i % BAR_COLORS.length],
                    }}
                  >
                    <span className="text-[11px] font-bold text-white whitespace-nowrap">
                      {formatInrFull(s.total)}
                    </span>
                  </div>
                ) : (
                  <span className="absolute left-2 top-1/2 -translate-y-1/2 text-[11px] italic text-gray-400">
                    Not quoted
                  </span>
                )}
              </div>
              <div className="w-20 shrink-0 text-[11px] text-gray-400">
                {s.items > 0 ? `${s.items} item${s.items > 1 ? "s" : ""}` : "—"}
                {isBest && (
                  <span className="ml-1 inline-block rounded bg-green-100 text-green-700 px-1.5 py-0.5 font-bold">
                    Best
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-[11px] text-gray-400 mt-3">
        Lower bar = lower price. The item count shows how much of this service each
        vendor actually quoted, so a low price with few items may mean smaller scope.
      </p>

      {/* At-a-glance: lowest-cost vendor for every service */}
      {bestByCategory.length > 0 && (
        <div className="mt-8 pt-6 border-t border-gray-100">
          <h3 className="text-sm font-bold text-gray-700 uppercase tracking-wide mb-3">
            Lowest cost by service
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {bestByCategory.map(({ category, best }) => (
              <button
                key={category}
                onClick={() => setSelected(category)}
                className={`text-left rounded-lg border p-3 transition-colors ${
                  selected === category
                    ? "border-blue-400 bg-blue-50"
                    : "border-gray-200 hover:border-blue-300 hover:bg-gray-50"
                }`}
              >
                <div className="text-[11px] font-semibold text-gray-500 uppercase truncate">
                  {category}
                </div>
                {best ? (
                  <>
                    <div className="text-sm font-bold text-gray-900 truncate" title={best.vendor}>
                      {nameOf(best.vendor)}
                    </div>
                    <div className="text-xs text-green-700 font-semibold">
                      {formatInrFull(best.total)}
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-gray-400 italic">No quotes</div>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
