"use client";

import React, { useMemo, useState } from "react";
import {
  buildVendorLabels,
  formatInrFull,
  type VendorMeta,
} from "@/lib/format";
import {
  coverageIndex,
  exclusiveWorkLabels,
  groupTableData,
  isSpaceComparable,
  quotedWorkCounts,
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
  rowComparisonSummary,
  spaceHeaderSummary,
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
import TatvaLogo from "@/components/TatvaLogo";
import PdfExportButtons, {
  type PdfDetailLevel,
} from "@/components/compare/PdfExportButtons";

type Props = {
  tableData: SpaceRow[];
  vendors: string[];
  vendorMeta?: Record<string, VendorMeta>;
  onDownloadPdf?: (detail: PdfDetailLevel) => void | Promise<void>;
  /** Optional MatrixV1 tiers. Absent for a legacy payload. */
  spaceTier?: SpaceRow[];
  bundleTier?: BundleRow[];
  projectTier?: SpaceRow[];
  coverage?: CoverageEntry[];
  projectTitle?: string;
  projectCode?: string;
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
      <td className="px-4 py-2.5 text-center tabular-nums">
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

  if (status === "incl_in_bundle" || status === "incl_in_parent") {
    return (
      <td className="px-4 py-2.5 text-center align-middle">
        <span
          className="text-[10px] font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5 inline-block leading-tight"
          title={
            status === "incl_in_parent"
              ? `Priced inside ${bundleLabel || "the parent space"} — not a missing item`
              : `Included in this vendor's ${bundleLabel} package — not a missing item`
          }
        >
          incl. in {bundleLabel || (status === "incl_in_parent" ? "parent space" : "package")}
        </span>
      </td>
    );
  }

  return (
    <td className="px-4 py-2.5 text-center tabular-nums opacity-50">
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
  projectTitle,
  projectCode,
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
  const allSpaceIds = useMemo(() => {
    const ids: string[] = [];
    for (const cat of grouped) {
      for (const space of cat.spaces) ids.push(space.spaceId);
    }
    for (const cat of projectGrouped) {
      for (const space of cat.spaces) ids.push(space.spaceId);
    }
    return ids;
  }, [grouped, projectGrouped]);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const toggleSpace = (spaceId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(spaceId)) next.delete(spaceId);
      else next.add(spaceId);
      return next;
    });
  };
  const expandAll = () => setExpanded(new Set(allSpaceIds));
  const collapseAll = () => setExpanded(new Set());
  const colCount = vendors.length + 2;

  const renderBundleRows = (
    rows: BundleRow[],
    accent: "amber" | "sky"
  ) =>
    rows.map((bundle, bi) => {
      const placeNotes =
        accent === "sky"
          ? recapPlacementNotes(bundle, vendors, vendorLabels)
          : [];
      const perVendorNotes =
        accent === "sky" && placeNotes.length === 0
          ? vendors
              .map((vendor) =>
                recapPlacementNote(bundle, vendor, vendorLabels, sameCompany)
              )
              .filter(Boolean)
          : [];
      const hasNotes = Boolean(
        bundle.overlap_flags?.length ||
          bundle.takeaway?.text ||
          placeNotes.length ||
          perVendorNotes.length
      );

      return (
        <React.Fragment key={bundle.bundle_id || bi}>
          <tr className="bg-white">
            <td
              className={`py-3 pl-6 pr-4 border-l-4 ${
                accent === "amber" ? "border-amber-300" : "border-sky-300"
              }`}
            >
              <div className="text-sm font-semibold text-stone-800 leading-tight">
                {bundle.bundle_label}
              </div>
              {bundle.covered_spaces?.length ? (
                <div className="text-[11px] text-stone-500 mt-0.5">
                  Across: {bundle.covered_spaces.join(" · ")}
                </div>
              ) : null}
            </td>
            {vendors.map((vendor, vIdx) => {
              const value = amountOf(bundle, vendor);
              const note = bundlePriceNote(bundle, vendor);
              return (
                <td
                  key={vIdx}
                  className="px-4 py-3 text-center tabular-nums align-middle"
                >
                  {value > 0 ? (
                    <>
                      <div className="text-sm font-bold text-stone-900">
                        {formatInrFull(value)}
                      </div>
                      {note ? (
                        <div className="text-[10px] text-stone-500 mt-0.5 normal-case">
                          {note}
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
            <td className="px-3 py-3 text-left align-middle text-[11px] leading-snug text-stone-600">
              {bundle.takeaway?.text || ""}
            </td>
          </tr>
          {hasNotes ? (
            <tr>
              <td
                colSpan={colCount}
                className={`px-6 py-2.5 border-l-4 ${
                  accent === "amber"
                    ? "border-amber-300 bg-amber-50/80"
                    : "border-sky-300 bg-sky-50/80"
                }`}
              >
                <div className="space-y-1.5 max-w-4xl">
                  {bundle.overlap_flags?.length ? (
                    <p className="text-[11px] text-rose-800 bg-rose-50 border border-rose-200 rounded-md px-2.5 py-1.5 leading-snug">
                      May overlap with a separate line for{" "}
                      {bundle.overlap_flags.join(", ")} — confirm with the
                      vendor
                    </p>
                  ) : null}
                  {bundle.takeaway?.text ? (
                    <p className="text-[12px] text-amber-950 leading-relaxed">
                      {bundle.takeaway.text}
                    </p>
                  ) : null}
                  {placeNotes.map((note) => (
                    <p
                      key={note}
                      className="text-[12px] text-sky-950 leading-relaxed"
                    >
                      {note}
                    </p>
                  ))}
                  {perVendorNotes.map((note) => (
                    <p
                      key={note}
                      className="text-[12px] text-sky-950 leading-relaxed"
                    >
                      {note}
                    </p>
                  ))}
                </div>
              </td>
            </tr>
          ) : null}
        </React.Fragment>
      );
    });

  const renderSectionHeader = (
    title: string,
    subtitle: string,
    tone: "amber" | "sky"
  ) => (
    <>
      <tr role="presentation">
        <td
          colSpan={colCount}
          className="h-3 p-0 bg-white border-0"
        />
      </tr>
      <tr
        className={
          tone === "amber"
            ? "bg-amber-50"
            : "bg-sky-50"
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
      const open = expanded.has(spaceGroup.spaceId);
      const itemCounts = quotedWorkCounts(spaceGroup, vendors);
      const exclusiveLabels = exclusiveWorkLabels(spaceGroup, vendors);
      const headerSummary = spaceHeaderSummary(
        spaceTotals,
        vendors,
        vendors
          .map((v) => coverIdx.get(`${spaceGroup.spaceId}||${v}`))
          .filter((e): e is NonNullable<typeof e> => Boolean(e)),
        { itemCounts, exclusiveLabels, comparable }
      );

      return (
        <React.Fragment key={spaceGroup.spaceId || spaceGroup.space}>
          {si > 0 && (
            <tr role="presentation">
              <td
                colSpan={colCount}
                className="h-2.5 p-0 bg-white border-0"
              />
            </tr>
          )}

          <tr className="bg-[#f5f1eb]">
            <td className="py-3 pl-5 pr-4 border-l-4 border-[var(--accent)]">
              <button
                type="button"
                onClick={() => toggleSpace(spaceGroup.spaceId)}
                className="flex items-start gap-2 text-left w-full"
                aria-expanded={open}
              >
                <span
                  className={`mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center text-stone-500 transition-transform ${
                    open ? "rotate-90" : ""
                  }`}
                  aria-hidden
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="h-4 w-4"
                  >
                    <path
                      fillRule="evenodd"
                      d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                      clipRule="evenodd"
                    />
                  </svg>
                </span>
                <span>
                  <span className="flex items-center gap-2 flex-wrap">
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
                  </span>
                  {spaceGroup.spaceRaw &&
                  spaceGroup.spaceRaw !== spaceGroup.space ? (
                    <span className="block text-[10px] text-stone-500 mt-0.5 font-normal normal-case tracking-normal">
                      {spaceGroup.spaceRaw}
                    </span>
                  ) : null}
                </span>
              </button>
            </td>
            {vendors.map((vendor, vIdx) => {
              const value = Number(spaceTotals[vendor]) || 0;
              const nItems = itemCounts[vendor] || 0;
              const entry = coverIdx.get(`${spaceGroup.spaceId}||${vendor}`);
              const elsewhere =
                entry?.status === "incl_in_parent" ||
                entry?.status === "incl_in_bundle";
              const elseLabel =
                entry?.status === "incl_in_parent"
                  ? entry.parent_space || "parent space"
                  : entry?.bundle_label || "package";
              return (
                <td
                  key={vIdx}
                  className={`px-3 py-3 text-center tabular-nums align-middle ${
                    value === 0 ? "opacity-50" : ""
                  } ${!comparable ? "opacity-70" : ""}`}
                >
                  {value === 0 && elsewhere ? (
                    <span className="text-[10px] font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5 inline-block leading-tight">
                      incl. in {elseLabel}
                    </span>
                  ) : value === 0 ? (
                    <span className="text-sm font-semibold text-rose-400 italic">
                      N/A
                    </span>
                  ) : (
                    <>
                      <span className="text-base font-extrabold text-stone-900">
                        {formatInrFull(value)}
                      </span>
                      <span className="block text-[10px] font-medium text-stone-500 mt-0.5 normal-case tracking-normal">
                        {nItems} {nItems === 1 ? "item" : "items"}
                      </span>
                    </>
                  )}
                </td>
              );
            })}
            <td className="px-3 py-3 text-left align-middle text-[11px] leading-snug text-stone-600">
              {headerSummary}
            </td>
          </tr>

          {open
            ? spaceGroup.subs.map((sub) => {
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
                className="hover:bg-stone-50/90 transition-colors bg-white"
              >
                <td className="py-2.5 pl-10 pr-4 border-l-4 border-transparent">
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
                <td className="px-3 py-2.5 text-left align-middle text-[11px] leading-snug text-stone-600">
                  {rowComparisonSummary(merged, vendors)}
                </td>
              </tr>
            );
          })
            : null}
        </React.Fragment>
      );
    });

  const quoteLine = vendors
    .map((vendor) => {
      const info = vendorLabels[vendor];
      const company = info?.company ?? vendor.split(" (")[0];
      return info?.quoteNumber ? `${company} · Quote ${info.quoteNumber}` : company;
    })
    .join("  ·  ");

  return (
    <section className="qs-card p-5 md:p-6 overflow-hidden">
      <div className="flex flex-col gap-4 mb-5 pb-4 border-b border-stone-200">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div className="flex items-start gap-3 min-w-0">
            <TatvaLogo size="sm" className="mt-0.5 shrink-0" />
            <div className="min-w-0">
              <p className="qs-eyebrow">Quote comparison</p>
              <h2 className="qs-section-title mt-0.5">
                {projectTitle || "Tatva Quotes Comparison Matrix"}
              </h2>
              <p className="qs-section-sub">
                {[
                  projectCode ? `Project ${projectCode}` : "",
                  "Space totals first — open a row for the work list",
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              {quoteLine ? (
                <p className="mt-1.5 text-[11px] text-stone-600 leading-snug">
                  {quoteLine}
                </p>
              ) : null}
            </div>
          </div>
          {onDownloadPdf ? (
            <PdfExportButtons onExport={onDownloadPdf} />
          ) : null}
        </div>
        {gstBanner ? (
          <p className="text-[11px] leading-snug text-sky-900 bg-sky-50 border border-sky-200 rounded-md px-2.5 py-1.5 max-w-3xl">
            {gstBanner}
          </p>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-2">
        <button
          type="button"
          onClick={expandAll}
          className="text-[11px] font-medium text-stone-600 underline-offset-2 hover:underline"
        >
          Expand all work
        </button>
        <span className="text-stone-300" aria-hidden>
          ·
        </span>
        <button
          type="button"
          onClick={collapseAll}
          className="text-[11px] font-medium text-stone-600 underline-offset-2 hover:underline"
        >
          Collapse to space totals
        </button>
      </div>
      <div className="overflow-x-auto border border-stone-300 rounded-md qs-table-scroll qs-table-doc max-h-[70vh]">
        <table className="w-full text-left border-collapse min-w-[960px] table-fixed">
          <thead>
            <tr>
              <th className="p-3.5 w-[26%] text-center text-[10px] font-bold tracking-[0.14em] uppercase text-stone-100">
                Space / work
              </th>
              {vendors.map((vendor, i) => {
                const info = vendorLabels[vendor];
                const meta = vendorMeta[vendor] || {};
                return (
                  <th
                    key={vendor}
                    className="p-3.5 text-center align-top"
                  >
                    <div title={info?.full ?? vendor}>
                      <div className="flex items-center justify-center gap-1.5 mb-1">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: vendorColor(i) }}
                          aria-hidden
                        />
                      </div>
                      <div className="text-[12px] font-semibold leading-snug normal-case tracking-normal text-white break-words">
                        {info?.company ?? vendor.split(" (")[0]}
                      </div>
                      {info?.variant && (
                        <div className="text-[10px] font-medium text-stone-300 normal-case tracking-normal mt-0.5">
                          {info.variant}
                        </div>
                      )}
                      {(info?.quoteNumber ||
                        info?.quoteDate ||
                        meta.quote_date) && (
                        <div className="text-[10px] font-medium text-amber-200/90 normal-case tracking-normal mt-1">
                          {info?.quoteNumber ? `Quote ${info.quoteNumber}` : ""}
                          {info?.quoteNumber &&
                          (info?.quoteDate || meta.quote_date)
                            ? " · "
                            : ""}
                          {info?.quoteDate || meta.quote_date || ""}
                        </div>
                      )}
                      {gstEntryChip(gstModeOf(meta)) ? (
                        <div className="text-[9px] font-medium text-stone-400 normal-case tracking-normal mt-0.5">
                          {gstEntryChip(gstModeOf(meta))}
                        </div>
                      ) : null}
                    </div>
                  </th>
                );
              })}
              <th className="p-3.5 w-[22%] text-left align-middle text-[10px] font-bold tracking-[0.14em] uppercase text-stone-100">
                Comparison summary
              </th>
            </tr>
          </thead>

          <tbody>
            {grouped.map((cat, ci) => (
              <React.Fragment key={ci}>
                {grouped.length > 1 ? (
                  <tr className="bg-stone-900/[0.03]">
                    <td
                      colSpan={colCount}
                      className="p-3 pl-4 text-sm font-bold text-stone-800 uppercase tracking-wider"
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
                    className="h-3 p-0 bg-white border-0"
                  />
                </tr>
                <tr className="bg-stone-100">
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
        Space headers add up the work listed under them. Open a space to see
        the work list. Item counts on the header show how much of that space
        each vendor quoted — a low total with few items may mean smaller scope.{" "}
        <span className="font-medium text-rose-400">N/A</span> means that vendor
        did not quote this work.{" "}
        <span className="font-medium text-amber-700">incl. in …</span> means the
        price is already inside that vendor&apos;s package or parent space, so it is
        not missing. Comparison summary explains a rate or quantity gap from the
        quote payload; it does not change the rupees.
        Same work, different spaces is comparison only — a space figure is already
        in the spaces above; a whole-home figure is included in this quote, not
        in those space sums. Column labels &quot;Entered excl. GST&quot; and
        &quot;Entered incl. GST&quot; are how the vendor typed the quote; figures
        shown include GST.
      </p>
    </section>
  );
}
