"use client";

import React, { useMemo } from "react";
import {
  buildVendorLabels,
  formatInrFull,
  formatQuoteCountLabel,
  priceVsBaseline,
  type VendorMeta,
} from "@/lib/format";
import {
  groupTableData,
  sumSubServiceRow,
  lineItemDescription,
} from "@/lib/compare-matrix";
import { vendorColor } from "@/lib/vendor-colors";

type Props = {
  tableData: Record<string, any>[];
  vendors: string[];
  vendorMeta?: Record<string, VendorMeta>;
  onDownloadPdf?: () => void;
};

export default function ComparisonMatrix({
  tableData,
  vendors,
  vendorMeta = {},
  onDownloadPdf,
}: Props) {
  const vendorLabels = useMemo(
    () => buildVendorLabels(vendors, vendorMeta),
    [vendors, vendorMeta]
  );

  const grouped = useMemo(() => groupTableData(tableData), [tableData]);

  return (
    <section className="qs-card p-5 md:p-6 overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-5">
        <div>
          <h2 className="qs-section-title">Category comparison</h2>
          <p className="qs-section-sub">
            Line items with sub-service totals per vendor and market estimate.
          </p>
        </div>
        {onDownloadPdf ? (
          <button
            type="button"
            onClick={onDownloadPdf}
            className="qs-btn qs-btn-secondary shrink-0"
            title="Download comparison as PDF"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="w-4 h-4"
              aria-hidden
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Export PDF
          </button>
        ) : null}
      </div>

      <div className="overflow-x-auto border border-stone-200 rounded-lg qs-table-scroll max-h-[70vh]">
        <table className="w-full text-left border-collapse min-w-[900px]">
          <thead>
            <tr className="text-stone-500 uppercase text-[10px] font-bold tracking-widest">
              <th className="p-4 border-b border-stone-200 w-[250px] bg-stone-50">
                Service description
              </th>
              <th className="p-4 border-b border-stone-200 text-right w-[140px] bg-[var(--ai-soft)] text-[var(--ai)]">
                <div>Market est.</div>
                <div className="text-[9px] font-normal normal-case tracking-normal text-indigo-400 mt-0.5 leading-tight">
                  Historical avg × item qty
                </div>
              </th>
              {vendors.map((vendor, i) => {
                const info = vendorLabels[vendor];
                const meta = vendorMeta[vendor] || {};
                return (
                  <th
                    key={vendor}
                    className="p-4 border-b border-stone-200 text-right align-top max-w-[170px] bg-stone-50"
                  >
                    <div
                      className="ml-auto max-w-[170px]"
                      title={info?.full ?? vendor}
                    >
                      <div className="flex items-center justify-end gap-1.5 mb-1">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: vendorColor(i) }}
                          aria-hidden
                        />
                      </div>
                      <div className="text-[11px] font-bold leading-snug normal-case tracking-normal text-stone-800 line-clamp-2 break-words">
                        {info?.company ?? vendor.split(" (")[0]}
                      </div>
                      {info?.variant && (
                        <div className="text-[10px] font-semibold text-blue-700 normal-case tracking-normal mt-0.5 line-clamp-1">
                          {info.variant}
                        </div>
                      )}
                      {(info?.quoteNumber ||
                        info?.quoteDate ||
                        meta.quote_date) && (
                        <div className="text-[9px] font-normal text-stone-400 normal-case tracking-normal mt-0.5">
                          {info?.quoteNumber ? `#${info.quoteNumber}` : ""}
                          {info?.quoteNumber &&
                          (info?.quoteDate || meta.quote_date)
                            ? " · "
                            : ""}
                          {info?.quoteDate || meta.quote_date || ""}
                        </div>
                      )}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>

          <tbody className="divide-y divide-stone-100">
            {grouped.map((cat, ci) => (
              <React.Fragment key={ci}>
                <tr className="bg-stone-900/[0.03]">
                  <td
                    colSpan={vendors.length + 2}
                    className="p-3 pl-4 text-sm font-bold text-stone-800 uppercase tracking-wider border-y border-stone-200"
                  >
                    {cat.category}
                  </td>
                </tr>

                {cat.subs.map((sub, si) => {
                  const subTotals = sumSubServiceRow(sub.rows, vendors);
                  const subBaseline = subTotals.moving_average;
                  const isLastInCategory = si === cat.subs.length - 1;

                  return (
                    <React.Fragment key={si}>
                      {si > 0 && (
                        <tr role="presentation">
                          <td
                            colSpan={vendors.length + 2}
                            className="h-3 p-0 bg-[var(--background)] border-0"
                          />
                        </tr>
                      )}

                      <tr className="bg-stone-200/70 border-y-2 border-stone-300">
                        <td className="py-3 pl-5 pr-4 border-l-4 border-[var(--accent)]">
                          <div className="text-xs font-extrabold text-stone-800 uppercase tracking-wide">
                            {sub.sub}
                          </div>
                        </td>
                        <td
                          className="px-3 py-3 text-right align-middle bg-indigo-100/50 border-r border-stone-300"
                          title="Sum of all line-item market estimates for this service"
                        >
                          {subBaseline > 0 ? (
                            <div className="text-base font-extrabold text-indigo-900 tabular-nums">
                              {formatInrFull(subBaseline)}
                            </div>
                          ) : (
                            <span className="text-sm text-stone-400">—</span>
                          )}
                        </td>
                        {vendors.map((vendor, vIdx) => {
                          const value = Number(subTotals[vendor]) || 0;
                          const vs = priceVsBaseline(value, subBaseline);
                          return (
                            <td
                              key={vIdx}
                              className={`px-3 py-3 text-right tabular-nums align-middle ${
                                value === 0 ? "opacity-50" : ""
                              }`}
                            >
                              {value === 0 ? (
                                <span className="text-sm font-semibold text-rose-400 italic">
                                  N/A
                                </span>
                              ) : (
                                <span
                                  className={`text-base font-extrabold ${
                                    vs === "below"
                                      ? "text-emerald-800"
                                      : vs === "above"
                                        ? "text-amber-800"
                                        : "text-stone-900"
                                  }`}
                                >
                                  {formatInrFull(value)}
                                </span>
                              )}
                            </td>
                          );
                        })}
                      </tr>

                      {sub.rows.map((row, idx) => {
                        const baseline =
                          Number(row.moving_average ?? row.market_average) || 0;
                        const weight = Number(row.moving_weight) || 0;
                        const { title, room } = lineItemDescription(row);
                        const isLastLineItem = idx === sub.rows.length - 1;
                        return (
                          <tr
                            key={idx}
                            className={`hover:bg-stone-50/80 transition-colors group bg-white ${
                              isLastLineItem && !isLastInCategory
                                ? "border-b-2 border-stone-200"
                                : ""
                            }`}
                          >
                            <td className="py-2.5 pl-12 pr-4 max-w-[320px] border-l-4 border-transparent">
                              <div className="text-sm font-medium text-stone-800 leading-tight">
                                {title}
                              </div>
                              {room && (
                                <div className="text-[10px] text-stone-400 mt-0.5 uppercase tracking-wide">
                                  {room}
                                </div>
                              )}
                            </td>
                            <td
                              className="px-4 py-2.5 text-right align-top bg-indigo-50/15 border-r border-indigo-100/40"
                              title="Market Est. from historical averages across past sessions"
                            >
                              {baseline > 0 ? (
                                <>
                                  <div className="text-sm font-medium text-indigo-700 tabular-nums">
                                    {formatInrFull(baseline)}
                                  </div>
                                  {weight > 0 && (
                                    <div className="text-[10px] text-stone-400 mt-0.5">
                                      {formatQuoteCountLabel(weight)}
                                    </div>
                                  )}
                                  {(() => {
                                    const ratePerUnit =
                                      Number(
                                        (row as any).market_rate_per_unit
                                      ) || 0;
                                    const pm = String(
                                      (row as any).pricing_method || ""
                                    );
                                    if (ratePerUnit > 0 && pm) {
                                      return (
                                        <div className="text-[9px] text-indigo-300 mt-0.5 tabular-nums">
                                          ₹
                                          {ratePerUnit.toLocaleString("en-IN")}/
                                          {pm}
                                        </div>
                                      );
                                    }
                                    return null;
                                  })()}
                                </>
                              ) : (
                                <span className="text-sm text-stone-300">—</span>
                              )}
                            </td>
                            {vendors.map((vendor, vIdx) => {
                              const value = row[vendor];
                              const vs = priceVsBaseline(
                                Number(value),
                                baseline
                              );
                              return (
                                <td
                                  key={vIdx}
                                  className={`px-4 py-2.5 text-right tabular-nums ${
                                    value === 0 ? "opacity-50" : ""
                                  }`}
                                >
                                  {value === 0 ? (
                                    <span className="text-sm font-medium text-rose-300 italic">
                                      N/A
                                    </span>
                                  ) : (
                                    <span
                                      className={`text-sm font-medium ${
                                        vs === "below"
                                          ? "text-emerald-700"
                                          : vs === "above"
                                            ? "text-amber-700"
                                            : "text-stone-700"
                                      }`}
                                    >
                                      {formatInrFull(Number(value))}
                                    </span>
                                  )}
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                    </React.Fragment>
                  );
                })}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-stone-400 mt-3">
        <span className="text-emerald-700 font-medium">Green</span> = below
        market est. ·{" "}
        <span className="text-amber-700 font-medium">Amber</span> = above market
        est. · Market est. uses historical averages across past sessions, not
        only vendors in this comparison.
      </p>
    </section>
  );
}
