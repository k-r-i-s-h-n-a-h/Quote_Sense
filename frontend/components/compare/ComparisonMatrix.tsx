"use client";

import React, { useMemo } from "react";
import {
  buildVendorLabels,
  formatInrFull,
  type VendorMeta,
} from "@/lib/format";
import { groupTableData, sumSubServiceRow } from "@/lib/compare-matrix";
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
  const colCount = vendors.length + 1;

  return (
    <section className="qs-card p-5 md:p-6 overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-5">
        <div>
          <h2 className="qs-section-title">Tatva Quotes Comparison Matrix</h2>
          <p className="qs-section-sub">
            Cost by room, with sub-services listed under each space.
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
        <table className="w-full text-left border-collapse min-w-[720px]">
          <thead>
            <tr className="text-stone-500 uppercase text-[10px] font-bold tracking-widest">
              <th className="p-4 border-b border-stone-200 w-[280px] bg-stone-50">
                Space / work
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
                {grouped.length > 1 ? (
                  <tr className="bg-stone-900/[0.03]">
                    <td
                      colSpan={colCount}
                      className="p-3 pl-4 text-sm font-bold text-stone-800 uppercase tracking-wider border-y border-stone-200"
                    >
                      {cat.category}
                    </td>
                  </tr>
                ) : null}

                {cat.spaces.map((spaceGroup, si) => {
                  const spaceRows = spaceGroup.subs.flatMap((s) => s.rows);
                  const spaceTotals = sumSubServiceRow(spaceRows, vendors);
                  const isLastSpace = si === cat.spaces.length - 1;

                  return (
                    <React.Fragment key={spaceGroup.space}>
                      {si > 0 && (
                        <tr role="presentation">
                          <td
                            colSpan={colCount}
                            className="h-3 p-0 bg-[var(--background)] border-0"
                          />
                        </tr>
                      )}

                      <tr className="bg-stone-200/70 border-y-2 border-stone-300">
                        <td className="py-3 pl-5 pr-4 border-l-4 border-[var(--accent)]">
                          <div className="text-xs font-extrabold text-stone-800 uppercase tracking-wide">
                            {spaceGroup.space}
                          </div>
                          {spaceGroup.spaceRaw &&
                          spaceGroup.spaceRaw !== spaceGroup.space ? (
                            <div className="text-[10px] text-stone-500 mt-0.5 font-normal normal-case tracking-normal">
                              {spaceGroup.spaceRaw}
                            </div>
                          ) : null}
                        </td>
                        {vendors.map((vendor, vIdx) => {
                          const value = Number(spaceTotals[vendor]) || 0;
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
                                <span className="text-base font-extrabold text-stone-900">
                                  {formatInrFull(value)}
                                </span>
                              )}
                            </td>
                          );
                        })}
                      </tr>

                      {spaceGroup.subs.map((sub, idx) => {
                        const subTotals = sumSubServiceRow(sub.rows, vendors);
                        const isLast = idx === spaceGroup.subs.length - 1;
                        const pricing = String(
                          (sub.rows[0] as { pricing_method?: string } | undefined)
                            ?.pricing_method || ""
                        );
                        return (
                          <tr
                            key={`${spaceGroup.space}-${sub.sub}`}
                            className={`hover:bg-stone-50/80 transition-colors bg-white ${
                              isLast && !isLastSpace
                                ? "border-b-2 border-stone-200"
                                : ""
                            }`}
                          >
                            <td className="py-2.5 pl-12 pr-4 max-w-[360px] border-l-4 border-transparent">
                              <div className="text-sm font-medium text-stone-800 leading-tight">
                                {sub.sub}
                              </div>
                              {pricing ? (
                                <div className="text-[10px] text-stone-400 mt-0.5">
                                  {pricing}
                                </div>
                              ) : null}
                              {(() => {
                                const items = Array.from(
                                  new Set(
                                    sub.rows.flatMap((r) =>
                                      Array.isArray((r as { breakdown?: { item?: string }[] }).breakdown)
                                        ? (r as { breakdown: { item?: string }[] }).breakdown
                                            .map((b) => String(b.item || "").trim())
                                            .filter(Boolean)
                                        : []
                                    )
                                  )
                                ).filter((name) => name.toLowerCase() !== sub.sub.toLowerCase());
                                if (items.length === 0) return null;
                                return (
                                  <div className="text-[10px] text-stone-400 mt-0.5 leading-snug">
                                    {items.join(" · ")}
                                  </div>
                                );
                              })()}
                            </td>
                            {vendors.map((vendor, vIdx) => {
                              const value = Number(subTotals[vendor]) || 0;
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
                                    <span className="text-sm font-medium text-stone-700">
                                      {formatInrFull(value)}
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
        Header totals are the sum of sub-services in that space. N/A means that
        vendor did not quote this work in this room.
      </p>
    </section>
  );
}
