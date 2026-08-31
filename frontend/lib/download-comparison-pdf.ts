import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import {
  coverageIndex,
  exclusiveWorkLabels,
  groupTableData,
  isSpaceComparable,
  quotedWorkCounts,
  sumSubServiceRow,
} from "./compare-matrix";
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
  rowComparisonSummary,
  spaceHeaderSummary,
  type BundleRow,
  type CoverageEntry,
  type SpaceRow,
} from "./compare-types";
import { formatInrFull, type VendorLabel, type VendorMeta } from "./format";
import { PDF_FONT_FAMILY, registerPdfUnicodeFont } from "./pdf-unicode-font";

type TableRow = SpaceRow;

/** Optional MatrixV1 tiers. Absent for a legacy payload, which exports as before. */
export type PdfTiers = {
  bundleTier?: BundleRow[];
  projectTier?: SpaceRow[];
  coverage?: CoverageEntry[];
};

export type PdfDetailLevel = "spaces" | "full";

export type PdfExportOptions = {
  projectTitle?: string;
  projectCode?: string;
  /** `spaces` = header totals only; `full` = every work line (default). */
  detail?: PdfDetailLevel;
};

type BodyCell =
  | string
  | {
      content: string;
      colSpan?: number;
      styles?: Record<string, unknown>;
    };

const TATVA_LOGO_PATH = "/tatva_assets.jpg";

const INK: [number, number, number] = [28, 25, 23];
const MUTED: [number, number, number] = [87, 83, 78];
const RULE: [number, number, number] = [214, 211, 209];
const HEAD_FILL: [number, number, number] = [28, 25, 23];
const HEAD_TEXT: [number, number, number] = [250, 248, 245];
const ACCENT: [number, number, number] = [192, 74, 0];
const SPACE_FILL: [number, number, number] = [245, 241, 235];
const BAND_FILL: [number, number, number] = [250, 248, 245];
const AMBER_FILL: [number, number, number] = [255, 251, 235];
const AMBER_TEXT: [number, number, number] = [120, 53, 15];
const AMBER_NOTE: [number, number, number] = [69, 26, 3];
const SKY_FILL: [number, number, number] = [240, 249, 255];
const SKY_TEXT: [number, number, number] = [12, 74, 110];
const SKY_NOTE: [number, number, number] = [12, 74, 110];
const ROSE_FILL: [number, number, number] = [255, 241, 242];
const ROSE_TEXT: [number, number, number] = [136, 19, 55];
const INFO_FILL: [number, number, number] = [240, 249, 255];
const INFO_TEXT: [number, number, number] = [12, 74, 110];

function pdfLayout(vendorCount: number) {
  const cols = Math.min(Math.max(vendorCount, 2), 3);
  return {
    title: 12,
    subtitle: 8,
    meta: 7.5,
    head: cols >= 3 ? 7 : 8,
    body: 8,
    note: 7,
    category: 8,
    subTotalLabel: 8.5,
    subTotalAmount: 9.5,
    subGap: 2.2,
    headMinHeight: 22,
    cellPad: 2.2,
    descShare: cols >= 3 ? 0.26 : 0.30,
    headerH: 32,
    footerH: 14,
    margin: 10,
  };
}

function formatPdfAmount(value: number, unicode: boolean): string {
  if (unicode) return formatInrFull(value);
  const n = Math.round(Number(value));
  if (!Number.isFinite(n)) return "N/A";
  return `INR ${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatPdfPrice(value: unknown, unicode: boolean): string {
  if (value === 0 || value === undefined || value === null) return "N/A";
  return formatPdfAmount(Number(value), unicode);
}

/**
 * Cell text for a work row. The PDF has no tooltips and gets forwarded to people
 * who never saw the app, so a bundled amount must not print as a bare "N/A" —
 * that is how a vendor gets wrongly excluded from a shortlist.
 */
function cellText(
  row: SpaceRow,
  vendor: string,
  total: number,
  unicode: boolean
): string {
  if (total > 0) return formatPdfAmount(total, unicode);
  const { status, bundleLabel } = parseCellStatus(row.coverage?.[vendor]);
  if (status === "incl_in_bundle") {
    return `incl. in ${bundleLabel || "package"}`;
  }
  if (status === "incl_in_parent") {
    return `incl. in ${bundleLabel || "parent space"}`;
  }
  return "N/A";
}

function vendorHeaderCell(
  vendor: string,
  vendorLabels: Record<string, VendorLabel>,
  vendorMeta: Record<string, VendorMeta>
): string {
  const info = vendorLabels[vendor];
  const meta = vendorMeta[vendor] || {};
  const company = (info?.company ?? vendor.split(" (")[0]).trim();
  const lines = [company];
  if (info?.variant) lines.push(info.variant);
  const qno = info?.quoteNumber ? `Quote ${info.quoteNumber}` : "";
  const qdate = info?.quoteDate || meta.quote_date || "";
  if (qno || qdate) lines.push([qno, qdate].filter(Boolean).join("  ·  "));
  const gstChip = gstEntryChip(gstModeOf(meta));
  if (gstChip) lines.push(gstChip);
  return lines.join("\n");
}

function quoteIndexLine(
  vendors: string[],
  vendorLabels: Record<string, VendorLabel>
): string {
  return vendors
    .map((vendor) => {
      const info = vendorLabels[vendor];
      const company = (info?.company ?? vendor.split(" (")[0]).trim();
      const qno = info?.quoteNumber ? `Quote ${info.quoteNumber}` : "";
      return qno ? `${company} · ${qno}` : company;
    })
    .join("   |   ");
}

function centeredCell(
  content: string,
  styles: Record<string, unknown> = {}
): BodyCell {
  return {
    content,
    styles: { halign: "center", valign: "middle", ...styles },
  };
}

function buildColumnStyles(
  vendors: string[],
  tableWidth: number,
  layout: ReturnType<typeof pdfLayout>
): Record<number, { cellWidth: number; halign?: "left" | "center" }> {
  const descCap = vendors.length >= 3 ? 42 : 52;
  const descWidth = Math.min(descCap, tableWidth * layout.descShare);
  const summaryWidth = Math.min(42, tableWidth * 0.22);
  const vendorWidth =
    (tableWidth - descWidth - summaryWidth) / Math.max(vendors.length, 1);
  const styles: Record<number, { cellWidth: number; halign?: "left" | "center" }> =
    {
      0: { cellWidth: descWidth, halign: "left" },
    };
  vendors.forEach((_, i) => {
    styles[i + 1] = { cellWidth: vendorWidth, halign: "center" };
  });
  styles[vendors.length + 1] = { cellWidth: summaryWidth, halign: "left" };
  return styles;
}

function loadLogoForPdf(): Promise<{
  dataUrl: string;
  width: number;
  height: number;
} | null> {
  if (typeof window === "undefined") return Promise.resolve(null);
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d");
        if (!ctx) {
          resolve(null);
          return;
        }
        ctx.drawImage(img, 0, 0);
        resolve({
          dataUrl: canvas.toDataURL("image/jpeg", 0.92),
          width: img.naturalWidth,
          height: img.naturalHeight,
        });
      } catch {
        resolve(null);
      }
    };
    img.onerror = () => resolve(null);
    img.src = TATVA_LOGO_PATH;
  });
}

function drawLetterhead(
  doc: jsPDF,
  font: string,
  layout: ReturnType<typeof pdfLayout>,
  logo: { dataUrl: string; width: number; height: number } | null,
  opts: {
    projectTitle: string;
    projectCode: string;
    quoteLine: string;
    generated: string;
  }
) {
  const pageWidth = doc.internal.pageSize.getWidth();
  const m = layout.margin;
  const y0 = 8;
  let textX = m;

  if (logo) {
    const logoW = 28;
    const logoH = Math.min(10, (logo.height / logo.width) * logoW);
    doc.addImage(logo.dataUrl, "JPEG", m, y0, logoW, logoH);
    textX = m + logoW + 5;
  }

  const rightWidth = Math.min(72, pageWidth * 0.36);
  const rightX = pageWidth - m;
  const titleWidth = rightX - rightWidth - 8 - textX;

  doc.setFont(font, "bold");
  doc.setFontSize(7);
  doc.setTextColor(...ACCENT);
  doc.text("TATVA OPS", textX, y0 + 3);

  doc.setFontSize(12);
  doc.setTextColor(...INK);
  const titleLines = doc.splitTextToSize(opts.projectTitle, Math.max(titleWidth, 60));
  doc.text(titleLines, textX, y0 + 9);

  doc.setFont(font, "normal");
  doc.setFontSize(layout.meta);
  doc.setTextColor(...MUTED);
  if (opts.projectCode) {
    doc.text(`Project ${opts.projectCode}`, textX, y0 + 15.5);
  }

  doc.setFont(font, "bold");
  doc.setFontSize(7);
  doc.setTextColor(...INK);
  doc.text("QUOTES IN THIS COMPARISON", rightX, y0 + 3, { align: "right" });
  doc.setFont(font, "normal");
  doc.setFontSize(7);
  doc.setTextColor(...MUTED);
  const quoteLines = doc.splitTextToSize(opts.quoteLine.replace(/ {3}\| {3}/g, "\n"), rightWidth);
  doc.text(quoteLines, rightX, y0 + 8, { align: "right" });
  doc.text(opts.generated, rightX, layout.headerH - 6, { align: "right" });

  const ruleY = layout.headerH - 3;
  doc.setDrawColor(...ACCENT);
  doc.setLineWidth(0.7);
  doc.line(m, ruleY, pageWidth - m, ruleY);
  doc.setDrawColor(...RULE);
  doc.setLineWidth(0.2);
  doc.line(m, ruleY + 1.1, pageWidth - m, ruleY + 1.1);
}

function drawFooter(
  doc: jsPDF,
  font: string,
  layout: ReturnType<typeof pdfLayout>,
  page: number,
  pageCount: number
) {
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const m = layout.margin;
  const y = pageHeight - 7;
  doc.setDrawColor(...RULE);
  doc.setLineWidth(0.25);
  doc.line(m, y - 4, pageWidth - m, y - 4);
  doc.setFont(font, "normal");
  doc.setFontSize(7);
  doc.setTextColor(...MUTED);
  doc.text("Tatva Ops  ·  Quote comparison  ·  Prepared for the client", m, y);
  doc.text(`Page ${page} of ${pageCount}`, pageWidth - m, y, { align: "right" });
}

function sectionCell(
  title: string,
  subtitle: string,
  colSpan: number,
  font: string,
  layout: ReturnType<typeof pdfLayout>,
  fill: [number, number, number],
  text: [number, number, number]
): BodyCell[] {
  return [
    {
      content: subtitle ? `${title}\n${subtitle}` : title,
      colSpan,
      styles: {
        font,
        fillColor: fill,
        textColor: text,
        fontStyle: "bold",
        fontSize: layout.category,
        cellPadding: { top: 3.2, bottom: 3.2, left: 4, right: 4 },
      },
    },
  ];
}

function noteRow(
  content: string,
  colSpan: number,
  font: string,
  layout: ReturnType<typeof pdfLayout>,
  fill: [number, number, number],
  text: [number, number, number]
): BodyCell[] {
  return [
    {
      content,
      colSpan,
      styles: {
        font,
        fontStyle: "normal",
        fillColor: fill,
        textColor: text,
        fontSize: layout.note,
        cellPadding: { top: 2.4, bottom: 2.6, left: 6, right: 4 },
      },
    },
  ];
}

function sanitizeFilePart(value: string): string {
  return value.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-|-$/g, "");
}

/** Generate and download comparison matrix PDF directly (no print dialog). */
export async function downloadComparisonPdf(
  tableData: TableRow[],
  vendors: string[],
  vendorLabels: Record<string, VendorLabel>,
  vendorMeta: Record<string, VendorMeta> = {},
  tiers: PdfTiers = {},
  options: PdfExportOptions = {}
): Promise<void> {
  const layout = pdfLayout(vendors.length);
  const detail: PdfDetailLevel = options.detail === "spaces" ? "spaces" : "full";
  const spacesOnly = detail === "spaces";
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const unicode = await registerPdfUnicodeFont(doc);
  const font = unicode ? PDF_FONT_FAMILY : "helvetica";
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = layout.margin;
  const tableWidth = pageWidth - margin * 2;

  const logo = await loadLogoForPdf();
  const today = new Date().toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  const projectTitle =
    options.projectTitle?.trim() || "Quote comparison";
  const projectCode = options.projectCode?.trim() || "";
  const quoteLine = quoteIndexLine(vendors, vendorLabels);
  const generated = `Generated ${today}`;

  doc.setProperties({
    title: projectCode
      ? `${projectTitle} (${projectCode}) — comparison`
      : `${projectTitle} — comparison`,
    author: "Tatva Ops",
    subject: "Vendor quote comparison",
    creator: "QuoteSense",
  });

  doc.setFont(font, "normal");
  doc.setFontSize(layout.body);

  const pad = layout.cellPad;
  const colSpan = vendors.length + 2;
  const body: BodyCell[][] = [];

  const bundleTier = tiers.bundleTier ?? [];
  const projectTier = tiers.projectTier ?? [];
  const projectForDisplay = projectRowsForDisplay(projectTier, bundleTier);
  const coverIdx = coverageIndex(tiers.coverage ?? []);
  const spaceRows = projectTier.length
    ? tableData.filter((r) => String(r.space_id ?? "") !== "project_level")
    : tableData;

  const gstBanner = gstCompareBanner(vendors, vendorMeta, vendorLabels);
  if (gstBanner) {
    body.push(noteRow(gstBanner, colSpan, font, layout, INFO_FILL, INFO_TEXT));
  }
  if (spacesOnly) {
    body.push(
      noteRow(
        "Space-level summary — work lines omitted. Open PDF: detailed for the full breakdown. Item counts are on each space total. Lump-sum packages and recaps are included below.",
        colSpan,
        font,
        layout,
        BAND_FILL,
        MUTED
      )
    );
  }

  const grouped = groupTableData(spaceRows);
  for (const cat of grouped) {
    if (grouped.length > 1) {
      body.push(
        sectionCell(
          cat.category.toUpperCase(),
          "",
          colSpan,
          font,
          layout,
          BAND_FILL,
          INK
        )
      );
    }
    for (let spaceIdx = 0; spaceIdx < cat.spaces.length; spaceIdx++) {
      const spaceGroup = cat.spaces[spaceIdx];
      if (spaceIdx > 0) {
        body.push([
          {
            content: "",
            colSpan,
            styles: {
              fillColor: [255, 255, 255],
              minCellHeight: layout.subGap,
              cellPadding: 0,
              lineWidth: 0,
            },
          },
        ]);
      }

      const groupedSpaceRows = spaceGroup.subs.flatMap((s) => s.rows);
      const totals = sumSubServiceRow(groupedSpaceRows, vendors);
      const comparable = isSpaceComparable(
        coverIdx,
        spaceGroup.spaceId,
        vendors
      );
      const spaceTitle = comparable
        ? spaceGroup.space.toUpperCase()
        : `${spaceGroup.space.toUpperCase()}   ·   scopes differ — not like-for-like`;

      const itemCounts = quotedWorkCounts(spaceGroup, vendors);
      const exclusiveLabels = exclusiveWorkLabels(spaceGroup, vendors);

      const spaceCellStyle = {
        font,
        fillColor: SPACE_FILL,
        fontStyle: "bold" as const,
        cellPadding: { top: 3.2, bottom: 3.2, left: 4, right: 3 },
      };

      const headerSummary = spaceHeaderSummary(
        totals,
        vendors,
        vendors
          .map((v) => coverIdx.get(`${spaceGroup.spaceId}||${v}`))
          .filter((e): e is NonNullable<typeof e> => Boolean(e)),
        { itemCounts, exclusiveLabels, comparable }
      );

      body.push([
        {
          content: spaceTitle,
          styles: {
            ...spaceCellStyle,
            fontSize: layout.subTotalLabel,
            textColor: comparable ? INK : AMBER_TEXT,
          },
        },
        ...vendors.map((v) => {
          const price = formatPdfPrice(totals[v], unicode);
          const n = itemCounts[v] || 0;
          const withCount =
            price === "N/A" ? price : `${price}\n${n} ${n === 1 ? "item" : "items"}`;
          return centeredCell(withCount, {
            ...spaceCellStyle,
            fontSize: layout.subTotalAmount,
            textColor: INK,
          });
        }),
        {
          content: headerSummary,
          styles: {
            ...spaceCellStyle,
            fontStyle: "normal",
            fontSize: layout.note,
            halign: "left",
            textColor: MUTED,
          },
        },
      ]);

      if (!spacesOnly) {
        for (const sub of spaceGroup.subs) {
          const subTotals = sumSubServiceRow(sub.rows, vendors);
          const first = sub.rows[0] ?? ({} as SpaceRow);
          const merged: SpaceRow = {
            ...first,
            ...Object.fromEntries(
              vendors.map((v) => [v, Number(subTotals[v]) || 0])
            ),
          };
          body.push([
            {
              content: sub.sub,
              styles: {
                font,
                fontSize: layout.body,
                cellPadding: { top: pad, bottom: pad, left: 8, right: pad },
                textColor: [51, 65, 85],
              },
            },
            ...vendors.map((v) =>
              centeredCell(cellText(first, v, Number(subTotals[v]) || 0, unicode))
            ),
            {
              content: rowComparisonSummary(merged, vendors),
              styles: {
                font,
                fontSize: layout.note,
                halign: "left",
                textColor: MUTED,
                cellPadding: { top: pad, bottom: pad, left: pad, right: pad },
              },
            },
          ]);
        }
      }
    }
  }

  if (bundleTier.length > 0) {
    const { lumpSums, scattered } = partitionBundleRows(bundleTier);
    const sameCompany = vendorsShareCompany(vendors, vendorLabels);
    const scatteredForDisplay = scattered.map((row) =>
      withInferredPlacement(row, vendors, spaceRows, projectTier)
    );

    const pushBundleSection = (
      title: string,
      subtitle: string,
      rows: BundleRow[],
      fill: [number, number, number],
      text: [number, number, number],
      withPlacement = false
    ) => {
      if (rows.length === 0) return;
      body.push(sectionCell(title, subtitle, colSpan, font, layout, fill, text));
      for (const bundle of rows) {
        const labelBits = [
          bundle.bundle_label,
          bundle.covered_spaces?.length
            ? `Across: ${bundle.covered_spaces.join(", ")}`
            : "",
        ]
          .filter(Boolean)
          .join("\n");

        body.push([
          {
            content: labelBits,
            styles: {
              font,
              fontSize: layout.body,
              fontStyle: "bold",
              cellPadding: { top: pad + 0.4, bottom: pad, left: 8, right: pad },
              textColor: INK,
            },
          },
          ...vendors.map((v) => {
            const value = amountOf(bundle, v);
            if (value <= 0) return centeredCell("N/A");
            const note = bundlePriceNote(bundle, v);
            return centeredCell(
              [formatPdfAmount(value, unicode), note && `(${note})`]
                .filter(Boolean)
                .join("\n")
            );
          }),
          {
            content: bundle.takeaway?.text?.trim() || "",
            styles: {
              font,
              fontSize: layout.note,
              halign: "left",
              textColor: MUTED,
            },
          },
        ]);

        if (bundle.overlap_flags?.length) {
          body.push(
            noteRow(
              `May overlap with a separate line for ${bundle.overlap_flags.join(", ")} — confirm with the vendor.`,
              colSpan,
              font,
              layout,
              ROSE_FILL,
              ROSE_TEXT
            )
          );
        }
        if (bundle.takeaway?.text) {
          body.push(
            noteRow(
              bundle.takeaway.text.trim(),
              colSpan,
              font,
              layout,
              AMBER_FILL,
              AMBER_NOTE
            )
          );
        }
        if (withPlacement) {
          const placeNotes = recapPlacementNotes(bundle, vendors, vendorLabels);
          for (const note of placeNotes) {
            body.push(
              noteRow(note, colSpan, font, layout, SKY_FILL, SKY_NOTE)
            );
          }
          // Per-vendor placement still belongs under the figures when notes
          // differ; keep a compact right-aligned reminder only if there is no
          // combined recap sentence.
          if (placeNotes.length === 0) {
            const perVendor = vendors
              .map((v) => recapPlacementNote(bundle, v, vendorLabels, sameCompany))
              .filter(Boolean);
            if (perVendor.length) {
              body.push(
                noteRow(perVendor.join("  ·  "), colSpan, font, layout, SKY_FILL, SKY_NOTE)
              );
            }
          }
        }
      }
    };

    pushBundleSection(
      "LUMP SUM PACKAGES",
      "Not included in the space totals above. One vendor priced a package; another listed the same kind of work line by line.",
      lumpSums,
      AMBER_FILL,
      AMBER_TEXT
    );
    pushBundleSection(
      "SAME WORK, DIFFERENT SPACES",
      "Comparison only — not extra spend. A space figure is already in the spaces above; a whole-home figure is included in this quote, not in those space sums.",
      scatteredForDisplay,
      SKY_FILL,
      SKY_TEXT,
      true
    );
  }

  if (projectForDisplay.length > 0) {
    body.push(
      sectionCell(
        "WHOLE HOME",
        "Work not tied to one space.",
        colSpan,
        font,
        layout,
        BAND_FILL,
        INK
      )
    );
    for (const cat of groupTableData(projectForDisplay)) {
      for (const spaceGroup of cat.spaces) {
        if (spacesOnly) {
          const groupedSpaceRows = spaceGroup.subs.flatMap((s) => s.rows);
          const totals = sumSubServiceRow(groupedSpaceRows, vendors);
          const itemCounts = quotedWorkCounts(spaceGroup, vendors);
          const exclusiveLabels = exclusiveWorkLabels(spaceGroup, vendors);
          const comparable = isSpaceComparable(
            coverIdx,
            spaceGroup.spaceId,
            vendors
          );
          body.push([
            {
              content: spaceGroup.space.toUpperCase(),
              styles: {
                font,
                fontSize: layout.subTotalLabel,
                fontStyle: "bold",
                fillColor: SPACE_FILL,
                cellPadding: { top: pad, bottom: pad, left: 8, right: pad },
                textColor: INK,
              },
            },
            ...vendors.map((v) => {
              const price = formatPdfPrice(totals[v], unicode);
              const n = itemCounts[v] || 0;
              const withCount =
                price === "N/A"
                  ? price
                  : `${price}\n${n} ${n === 1 ? "item" : "items"}`;
              return centeredCell(withCount);
            }),
            {
              content: spaceHeaderSummary(
                totals,
                vendors,
                vendors
                  .map((v) => coverIdx.get(`${spaceGroup.spaceId}||${v}`))
                  .filter((e): e is NonNullable<typeof e> => Boolean(e)),
                { itemCounts, exclusiveLabels, comparable }
              ),
              styles: {
                font,
                fontSize: layout.note,
                halign: "left",
                textColor: MUTED,
              },
            },
          ]);
          continue;
        }
        for (const sub of spaceGroup.subs) {
          const subTotals = sumSubServiceRow(sub.rows, vendors);
          const first = sub.rows[0] ?? ({} as SpaceRow);
          const merged: SpaceRow = {
            ...first,
            ...Object.fromEntries(
              vendors.map((v) => [v, Number(subTotals[v]) || 0])
            ),
          };
          body.push([
            {
              content: sub.sub,
              styles: {
                font,
                fontSize: layout.body,
                cellPadding: { top: pad, bottom: pad, left: 8, right: pad },
                textColor: [51, 65, 85],
              },
            },
            ...vendors.map((v) =>
              centeredCell(cellText(first, v, Number(subTotals[v]) || 0, unicode))
            ),
            {
              content: rowComparisonSummary(merged, vendors),
              styles: {
                font,
                fontSize: layout.note,
                halign: "left",
                textColor: MUTED,
                cellPadding: { top: pad, bottom: pad, left: pad, right: pad },
              },
            },
          ]);
        }
      }
    }
  }

  body.push(
    noteRow(
      [
        '"N/A" = that vendor did not quote this work.  "incl. in …" = price is already inside that vendor\'s package or parent space.',
        "Comparison summary explains a quantity or rate gap; it does not change the rupees.",
        "Lump sum packages are separate from space totals. Same work, different spaces is comparison only.",
        '"Entered excl. GST" / "Entered incl. GST" is how the vendor typed the quote. Figures shown include GST so columns can be compared.',
      ].join("\n"),
      colSpan,
      font,
      layout,
      [255, 255, 255],
      MUTED
    )
  );

  const columnStyles = buildColumnStyles(vendors, tableWidth, layout);

  autoTable(doc, {
    head: [
      [
        "Space / work",
        ...vendors.map((v) => vendorHeaderCell(v, vendorLabels, vendorMeta)),
        "Comparison summary",
      ],
    ],
    body: body as Parameters<typeof autoTable>[1]["body"],
    startY: layout.headerH + 2,
    tableWidth,
    margin: {
      left: margin,
      right: margin,
      top: layout.headerH + 2,
      bottom: layout.footerH,
    },
    theme: "plain",
    styles: {
      font,
      fontSize: layout.body,
      cellPadding: { top: pad, bottom: pad, left: pad, right: pad },
      overflow: "linebreak",
      valign: "middle",
      lineWidth: 0,
      textColor: INK,
    },
    headStyles: {
      font,
      fillColor: HEAD_FILL,
      textColor: HEAD_TEXT,
      fontStyle: "bold",
      fontSize: layout.head,
      minCellHeight: layout.headMinHeight,
      cellPadding: { top: 3, bottom: 3.2, left: 3.2, right: 3.2 },
      overflow: "linebreak",
      valign: "middle",
      halign: "center",
    },
    bodyStyles: {
      font,
      fontSize: layout.body,
    },
    columnStyles,
    showHead: "everyPage",
    rowPageBreak: "avoid",
    horizontalPageBreak: false,
    didParseCell: (data) => {
      const spanned = Number(data.cell.colSpan || 1) > 1;
      if (data.section === "head") {
        data.cell.styles.halign =
          data.column.index === vendors.length + 1 ? "left" : "center";
        return;
      }
      if (data.section === "body" && data.column.index > 0 && !spanned) {
        data.cell.styles.halign =
          data.column.index === vendors.length + 1 ? "left" : "center";
      }
    },
    didDrawCell: (data) => {
      if (data.section !== "body" && data.section !== "head") return;
      const { x, y, width, height } = data.cell;
      doc.setDrawColor(...RULE);
      doc.setLineWidth(0.18);
      doc.line(x, y + height, x + width, y + height);
    },
    didDrawPage: () => {
      drawLetterhead(doc, font, layout, logo, {
        projectTitle,
        projectCode,
        quoteLine,
        generated,
      });
    },
  });

  const pageCount = doc.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    drawFooter(doc, font, layout, i, pageCount);
  }

  const fileBits = [
    "Tatva-comparison",
    sanitizeFilePart(projectCode),
    spacesOnly ? "spaces" : "detailed",
  ]
    .filter(Boolean)
    .join("-");
  doc.save(`${fileBits || "Tatva-comparison"}.pdf`);
}
