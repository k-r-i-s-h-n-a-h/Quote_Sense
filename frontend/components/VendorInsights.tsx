"use client";

import { useMemo, useState } from "react";
import {
  buildVendorLabels,
  formatInrFull,
  type VendorMeta,
} from "../lib/format";
import { vendorColor } from "../lib/vendor-colors";

type Row = Record<string, any>;

type Stat = {
  vendor: string;
  name: string;
  total: number;
  items: number;
  index: number;
};

const ALL = "__all__";

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
      const space = String(r.space || r.room || "").trim();
      if (space && !seen.includes(space)) seen.push(space);
    }
    return seen;
  }, [tableData]);

  const [selected, setSelected] = useState<string>(ALL);

  const rows = useMemo(
    () =>
      selected === ALL
        ? tableData
        : tableData.filter((r) => String(r.space || r.room || "") === selected),
    [selected, tableData]
  );

  const stats: Stat[] = useMemo(() => {
    return vendors
      .map((v, index) => {
        let total = 0;
        let items = 0;
        for (const r of rows) {
          const val = Number(r[v]) || 0;
          if (val > 0) {
            total += val;
            items += 1;
          }
        }
        return { vendor: v, name: nameOf(v), total, items, index };
      })
      .sort((a, b) => a.total - b.total);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, vendors, labels]);

  const funded = stats.filter((s) => s.total > 0);
  const maxTotal = Math.max(1, ...stats.map((s) => s.total));
  const cheapest = funded[0];
  const priciest = funded[funded.length - 1];

  const bestByCategory = useMemo(() => {
    return categories.map((cat) => {
      const catRows = tableData.filter(
        (r) => String(r.space || r.room || "") === cat
      );
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

  const label = selected === ALL ? "all spaces" : selected;

  const savingsPct =
    cheapest && priciest && priciest.total > 0 && cheapest !== priciest
      ? Math.round(((priciest.total - cheapest.total) / priciest.total) * 100)
      : 0;

  return (
    <section className="qs-card p-5 md:p-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-5">
        <div>
          <h2 className="qs-section-title">Space insights</h2>
          <p className="qs-section-sub">
            Scan who is cheapest overall and by room.
          </p>
        </div>
        <label className="text-sm sm:w-64">
          <span className="block text-stone-500 mb-1 text-xs font-medium">
            Space filter
          </span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="qs-select"
          >
            <option value={ALL}>All spaces (total)</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>

      {cheapest && (
        <div className="mb-5 rounded-lg bg-[var(--success-soft)] border border-[var(--success-border)] p-4">
          <p className="text-sm text-emerald-950 leading-relaxed">
            <span className="font-semibold">{cheapest.name}</span> has the lowest
            cost for <span className="font-medium">{label}</span> at{" "}
            <span className="font-semibold tabular-nums">
              {formatInrFull(cheapest.total)}
            </span>
            {savingsPct > 0 && priciest ? (
              <>
                {" "}
                — about <span className="font-semibold">{savingsPct}%</span>{" "}
                cheaper than {priciest.name} (
                {formatInrFull(priciest.total)}).
              </>
            ) : (
              "."
            )}
          </p>
        </div>
      )}

      <div className="space-y-3">
        {stats.map((s) => {
          const isBest = cheapest && s.vendor === cheapest.vendor && s.total > 0;
          const widthPct =
            s.total > 0 ? Math.max(4, (s.total / maxTotal) * 100) : 0;
          return (
            <div key={s.vendor} className="flex items-center gap-3">
              <div
                className="w-28 sm:w-40 shrink-0 text-right text-xs font-semibold text-stone-700 truncate"
                title={labels[s.vendor]?.full || s.vendor}
              >
                {s.name}
              </div>
              <div className="flex-1 h-7 bg-stone-100 rounded-md overflow-hidden relative">
                {s.total > 0 ? (
                  <div
                    className="h-full rounded-md transition-all duration-200 flex items-center justify-end pr-2"
                    style={{
                      width: `${widthPct}%`,
                      backgroundColor: isBest
                        ? "#047857"
                        : vendorColor(s.index),
                    }}
                  >
                    <span className="text-[11px] font-bold text-white whitespace-nowrap tabular-nums">
                      {formatInrFull(s.total)}
                    </span>
                  </div>
                ) : (
                  <span className="absolute left-2 top-1/2 -translate-y-1/2 text-[11px] italic text-stone-400">
                    Not quoted
                  </span>
                )}
              </div>
              <div className="w-20 shrink-0 text-[11px] text-stone-400">
                {s.items > 0 ? `${s.items} item${s.items > 1 ? "s" : ""}` : "—"}
                {isBest && (
                  <span className="ml-1 inline-block rounded bg-emerald-100 text-emerald-800 px-1.5 py-0.5 font-bold">
                    Best
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-[11px] text-stone-400 mt-3">
        Lower bar = lower price. Item count shows how much of this space each
        vendor quoted — a low price with few items may mean smaller scope.
      </p>

      {bestByCategory.length > 0 && (
        <div className="mt-7 pt-5 border-t border-stone-100">
          <h3 className="text-xs font-semibold text-stone-500 uppercase tracking-wide mb-3">
            Lowest cost by space
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {bestByCategory.map(({ category, best }) => (
              <button
                key={category}
                type="button"
                onClick={() => setSelected(category)}
                className={`text-left rounded-lg border p-3 transition-colors duration-150 ${
                  selected === category
                    ? "border-[var(--ai-border)] bg-[var(--ai-soft)]"
                    : "border-stone-200 hover:border-stone-300 hover:bg-stone-50"
                }`}
              >
                <div className="text-[11px] font-semibold text-stone-500 uppercase truncate">
                  {category}
                </div>
                {best ? (
                  <>
                    <div
                      className="text-sm font-semibold text-stone-900 truncate"
                      title={best.vendor}
                    >
                      {nameOf(best.vendor)}
                    </div>
                    <div className="text-xs text-emerald-700 font-semibold tabular-nums">
                      {formatInrFull(best.total)}
                    </div>
                  </>
                ) : (
                  <div className="text-sm text-stone-400 italic">No quotes</div>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
