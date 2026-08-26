"use client";

import React, { useMemo } from "react";
import {
  buildVendorLabels,
  formatInrFull,
  type VendorMeta,
} from "@/lib/format";
import {
  coverageIndex,
  groupTableData,
  isSpaceComparable,
  sumSubServiceRow,
} from "@/lib/compare-matrix";
import {
  amountOf,
  bundlePriceNote,
  parseCellStatus,
  partitionBundleRows,
  projectRowsForDisplay,
  recapPlacementNote,
  recapPlacementNotes,
  vendorsShareCompany,
  withInferredPlacement,
  gstCompareBanner,
  gstEntryChip,
  gstModeOf,
  type BundleRow,
  type CoverageEntry,
  type SpaceRow,
} from "@/lib/compare-types";
import { vendorColor } from "@/lib/vendor-colors";

type Props = {
  tableData: SpaceRow[];
  vendors: string[];
  vendorMeta?: Record<string, VendorMeta>;
  onDownloadPdf?: () => void;
  /** Optional MatrixV1 tiers. Absent for a legacy payload. */
  spaceTier?: SpaceRow[];
  bundleTier?: BundleRow[];
  projectTier?: SpaceRow[];
  coverage?: CoverageEntry[];
};

/**
 * Renders one vendor cell. A zero is only "N/A" when the vendor genuinely did
 * not quote it — if the amount sits inside a bundle we say so instead. The old
 * table showed all three cases identically, which made a vendor with a bundled
 * scope look like a vendor with a missing scope.
 */
function AmountCell({
  row,
  vendor,
  strong,
}: {
  row: SpaceRow;
  vendor: string;
  strong?: boolean;
}) {
  const value = amountOf(row, vendor);
  const { status, bundleLabel } = parseCellStatus(row.coverage?.[vendor]);

  if (value > 0) {
    return (
      <td className="px-4 py-2.5 text-right tabular-nums">
        <span
          className={
            strong
              ? "text-base font-extrabold text-stone-900"
              : "text-sm font-medium text-stone-700"
          }
        >
          {formatInrFull(value)}
        </span>
      </td>
    );
  }

  if (status === "incl_in_bundle") {
    return (
      <td className="px-4 py-2.5 text-right align-middle">
        <span
          className="text-[10px] font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5 inline-block leading-tight"
          title={`Included in this vendor's ${bundleLabel} package — not a missing item`}
        >
          incl. in {bundleLabel || "package"}
        </span>
      </td>
    );
  }

  return (
    <td className="px-4 py-2.5 text-right tabular-nums opacity-50">
      <span
        className={
          strong
            ? "text-sm font-semibold text-rose-400 italic"
            : "text-sm font-medium text-rose-300 italic"
        }
      >
        N/A
      </span>
    </td>
  );
}

export default function ComparisonMatrix({
  tableData,
  vendors,
  vendorMeta = {},
  onDownloadPdf,
  spaceTier,
  bundleTier = [],
  projectTier,
  coverage = [],
}: Props) {
  const vendorLabels = useMemo(
    () => buildVendorLabels(vendors, vendorMeta),
    [vendors, vendorMeta]
  );
  const sameCompany = useMemo(
    () => vendorsShareCompany(vendors, vendorLabels),
    [vendors, vendorLabels]
  );
  const gstBanner = useMemo(
    () => gstCompareBanner(vendors, vendorMeta, vendorLabels),
    [vendors, vendorMeta, vendorLabels]
  );

  // Prefer the tiers when present; fall back to the flat payload so an older
  // backend renders exactly as before.
  const spaceRows = spaceTier ?? tableData;
  const grouped = useMemo(() => groupTableData(spaceRows), [spaceRows]);
  const { lumpSums, scattered } = useMemo(
    () => partitionBundleRows(bundleTier),
    [bundleTier]
  );
  const scatteredForDisplay = useMemo(
    () =>
      scattered.map((row) =>
        withInferredPlacement(row, vendors, spaceRows, projectTier ?? [])
      ),
    [scattered, vendors, spaceRows, projectTier]
  );
  const projectForDisplay = useMemo(
    () => projectRowsForDisplay(projectTier ?? [], bundleTier),
    [projectTier, bundleTier]
  );
  const projectGrouped = useMemo(
    () => (projectForDisplay.length ? groupTableData(projectForDisplay) : []),
    [projectForDisplay]
  );
  const coverIdx = useMemo(() => coverageIndex(coverage), [coverage]);
  const colCount = vendors.length + 1;

  const renderBundleRows = (
    rows: BundleRow[],
    accent: "amber" | "sky"
  ) =>
    rows.map((bundle, bi) => (
      <tr key={bundle.bundle_id || bi} className="bg-white">
        <td
          className={`py-3 pl-8 pr-4 max-w-[360px] border-l-4 ${
            accent === "amber" ? "border-amber-200" : "border-sky-200"
          }`}
        >
          <div className="text-sm font-semibold text-stone-800 leading-tight">
            {bundle.bundle_label}
          </div>
          {bundle.covered_spaces?.length ? (
            <div className="text-[10px] text-stone-500 mt-0.5">
              Across: {bundle.covered_spaces.join(" · ")}
            </div>
          ) : null}
          {bundle.overlap_flags?.length ? (
            <div className="text-[10px] text-rose-700 bg-rose-50 border border-rose-200 rounded px-1.5 py-0.5 mt-1 inline-block leading-snug">
              May overlap with a separate line for{" "}
              {bundle.overlap_flags.join(", ")} — confirm with the vendor
            </div>
          ) : null}
          {bundle.takeaway?.text ? (
            <div className="text-[10px] text-amber-950 bg-amber-50 border border-amber-200 rounded px-1.5 py-1 mt-1.5 leading-snug">
              {bundle.takeaway.text}
            </div>
          ) : null}
          {accent === "sky"
            ? recapPlacementNotes(bundle, vendors, vendorLabels).map((note) => (
                <div
                  key={note}
                  className="text-[10px] text-sky-900 bg-sky-50 border border-sky-200 rounded px-1.5 py-1 mt-1.5 leading-snug"
                >
                  {note}
                </div>
              ))
            : null}
        </td>
        {vendors.map((vendor, vIdx) => {
          const value = amountOf(bundle, vendor);
          const note = bundlePriceNote(bundle, vendor);
          const placeNote =
            accent === "sky"
              ? recapPlacementNote(bundle, vendor, vendorLabels, sameCompany)
              : "";
          return (
            <td
              key={vIdx}
              className="px-4 py-3 text-right tabular-nums align-middle"
            >
              {value > 0 ? (
                <>
                  <div className="text-sm font-bold text-stone-900">
                    {formatInrFull(value)}
                  </div>
                  {note ? (
                    <div className="text-[9px] text-stone-500 mt-0.5 normal-case">
                      {note}
                    </div>
                  ) : null}
                  {placeNote ? (
                    <div className="text-[9px] text-sky-800 mt-0.5 normal-case leading-snug max-w-[14rem] ml-auto">
                      {placeNote}
                    </div>
                  ) : null}
                </>
              ) : (
                <span className="text-sm font-medium text-rose-300 italic">
                  N/A
                </span>
              )}
            </td>
          );
        })}
      </tr>
    ));

  const renderSectionHeader = (
    title: string,
    subtitle: string,
    tone: "amber" | "sky"
  ) => (
    <>
      <tr role="presentation">
        <td
          colSpan={colCount}
          className="h-4 p-0 bg-[var(--background)] border-0"
        />
      </tr>
      <tr
        className={
          tone === "amber"
            ? "bg-amber-50 border-y-2 border-amber-200"
            : "bg-sky-50 border-y-2 border-sky-200"
        }
      >
        <td
          colSpan={colCount}
          className={`p-3 pl-4 border-l-4 ${
            tone === "amber" ? "border-amber-400" : "border-sky-400"
          }`}
        >
          <div
            className={`text-sm font-bold uppercase tracking-wider ${
              tone === "amber" ? "text-amber-900" : "text-sky-900"
            }`}
          >
            {title}
          </div>
          <div
            className={`text-[10px] mt-0.5 font-normal normal-case tracking-normal ${
              tone === "amber" ? "text-amber-800" : "text-sky-800"
            }`}
          >
            {subtitle}
          </div>
        </td>
      </tr>
    </>
  );

  const renderSpaces = (
    spaces: ReturnType<typeof groupTableData>[number]["spaces"]
  ) =>
    spaces.map((spaceGroup, si) => {
      const spaceRowsInGroup = spaceGroup.subs.flatMap((s) => s.rows);
      const spaceTotals = sumSubServiceRow(spaceRowsInGroup, vendors);
      const comparable = isSpaceComparable(
        coverIdx,
        spaceGroup.spaceId,
        vendors
      );
      const isLastSpace = si === spaces.length - 1;

      return (
        <React.Fragment key={spaceGroup.spaceId || spaceGroup.space}>
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
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-extrabold text-stone-800 uppercase tracking-wide">
                  {spaceGroup.space}
                </span>
                {!comparable && (
                  <span
                    className="text-[9px] font-semibold text-amber-800 bg-amber-100 border border-amber-300 rounded px-1.5 py-0.5 uppercase tracking-wide"
                    title="Vendors priced this space differently, so these totals are not like-for-like"
                  >
                    scopes differ
                  </span>
                )}
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
                  } ${!comparable ? "opacity-70" : ""}`}
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
            const isLast = idx === spaceGroup.subs.length - 1;
            const first = sub.rows[0] ?? {};
            const pricing = String(first.pricing_method || "");
            // A work row can be fed by several vendor lines; merge their
            // amounts but keep the first row's coverage semantics.
            const merged: SpaceRow = {
              ...first,
              ...Object.fromEntries(
                vendors.map((v) => [v, sumSubServiceRow(sub.rows, vendors)[v]])
              ),
            };
            const items = Array.from(
              new Set(
                sub.rows.flatMap((r) =>
                  Array.isArray(r.breakdown)
                    ? r.breakdown
                        .map((b) => String(b.item || "").trim())
                        .filter(Boolean)
                    : []
                )
              )
            ).filter((name) => name.toLowerCase() !== sub.sub.toLowerCase());

            return (
              <tr
                key={`${spaceGroup.spaceId}-${sub.workKey}`}
                className={`hover:bg-stone-50/80 transition-colors bg-white ${
                  isLast && !isLastSpace ? "border-b-2 border-stone-200" : ""
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
                  {items.length > 0 ? (
                    <div className="text-[10px] text-stone-400 mt-0.5 leading-snug">
                      {items.join(" · ")}
                    </div>
                  ) : null}
                </td>
                {vendors.map((vendor, vIdx) => (
                  <AmountCell key={vIdx} row={merged} vendor={vendor} />
                ))}
              </tr>
            );
          })}
        </React.Fragment>
      );
    });

  return (
    <section className="qs-card p-5 md:p-6 overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-5">
        <div>
          <h2 className="qs-section-title">Tatva Quotes Comparison Matrix</h2>
          <p className="qs-section-sub">
            Cost by space, with work items listed under each.
          </p>
          {gstBanner ? (
            <p className="mt-2 text-[11px] leading-snug text-sky-900 bg-sky-50 border border-sky-200 rounded-md px-2.5 py-1.5 max-w-3xl">
              {gstBanner}
            </p>
          ) : null}
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
                      {gstEntryChip(gstModeOf(meta)) ? (
                        <div className="text-[9px] font-semibold text-stone-500 normal-case tracking-normal mt-0.5">
                          {gstEntryChip(gstModeOf(meta))}
                        </div>
                      ) : null}
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
                {renderSpaces(cat.spaces)}
              </React.Fragment>
            ))}

            {lumpSums.length > 0 && (
              <>
                {renderSectionHeader(
                  "Lump sum packages",
                  "One vendor gave a single package price for several items; another listed them separately. Package prices are not included in the space totals above.",
                  "amber"
                )}
                {renderBundleRows(lumpSums, "amber")}
              </>
            )}

            {scatteredForDisplay.length > 0 && (
              <>
                {renderSectionHeader(
                  "Same work, different spaces",
                  "Comparison only — not extra spend. Read each quote's note: a space figure is already in the spaces above; a whole-home figure is not in those space sums and is included in this quote.",
                  "sky"
                )}
                {renderBundleRows(scatteredForDisplay, "sky")}
              </>
            )}

            {projectGrouped.length > 0 && (
              <>
                <tr role="presentation">
                  <td
                    colSpan={colCount}
                    className="h-4 p-0 bg-[var(--background)] border-0"
                  />
                </tr>
                <tr className="bg-stone-100 border-y border-stone-200">
                  <td colSpan={colCount} className="p-3 pl-4">
                    <div className="text-sm font-bold text-stone-800 uppercase tracking-wider">
                      Whole home
                    </div>
                    <div className="text-[10px] text-stone-500 mt-0.5 font-normal normal-case tracking-normal">
                      Work not tied to one space.
                    </div>
                  </td>
                </tr>
                {projectGrouped.map((cat, ci) => (
                  <React.Fragment key={`proj-${ci}`}>
                    {renderSpaces(cat.spaces)}
                  </React.Fragment>
                ))}
              </>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] text-stone-400 mt-3">
        Space headers add up the work listed under them.{" "}
        <span className="font-medium text-rose-400">N/A</span> means that vendor
        did not quote this work.{" "}
        <span className="font-medium text-amber-700">incl. in …</span> means the
        price is already inside that vendor&apos;s package, so it is not missing.
        Same work, different spaces is comparison only — a space figure is already
        in the spaces above; a whole-home figure is included in this quote, not
        in those space sums. Column labels &quot;Entered excl. GST&quot; and
        &quot;Entered incl. GST&quot; are how the vendor typed the quote; figures
        shown include GST.
      </p>
    </section>
  );
}
