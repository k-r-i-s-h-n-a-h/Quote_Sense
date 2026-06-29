import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import { groupTableData, sumSubServiceRow, lineItemDescription } from "./compare-matrix";
import { type VendorLabel, type VendorMeta, formatQuoteCountLabel } from "./format";

type TableRow = Record<string, unknown>;

/** jsPDF built-in Helvetica — clean sans-serif for comparison exports. */
const FONT = "helvetica";

/** Typography + layout tuned for 2–3 quote columns on portrait A4. */
function pdfLayout(vendorCount: number) {
  const cols = Math.min(Math.max(vendorCount, 2), 3);
  if (cols >= 3) {
    return {
      title: 11,
      subtitle: 8,
      head: 7,
      body: 6.5,
      category: 7.5,
      subTotalLabel: 8,
      subTotalAmount: 9,
      subGap: 3,
      headMinHeight: 14,
      cellPad: 2,
      descShare: 0.26,
      avgWidth: 22,
      vendorTruncate: 18,
      variantTruncate: 16,
    };
  }
  return {
    title: 12,
    subtitle: 8.5,
    head: 8,
    body: 7,
    category: 8.5,
    subTotalLabel: 8.5,
    subTotalAmount: 9.5,
    subGap: 3.5,
    headMinHeight: 16,
    cellPad: 2.5,
    descShare: 0.3,
    avgWidth: 24,
    vendorTruncate: 20,
    variantTruncate: 18,
  };
}

const SUB_ROW_FILL: [number, number, number] = [226, 232, 240];
const SUB_AVG_FILL: [number, number, number] = [224, 231, 255];
const SUB_GAP_FILL: [number, number, number] = [248, 250, 252];

/** ASCII-safe currency — avoids broken ₹ glyph in standard PDF fonts. */
function formatPdfAmount(value: number): string {
  const n = Math.round(Number(value));
  if (!Number.isFinite(n)) return "N/A";
  const formatted = n.toLocaleString("en-IN", {
    maximumFractionDigits: 0,
  });
  return `Rs. ${formatted}`;
}

function formatPdfPrice(value: unknown): string {
  if (value === 0 || value === undefined || value === null) return "N/A";
  return formatPdfAmount(Number(value));
}

function truncate(text: string, maxLen: number): string {
  const t = text.trim();
  if (t.length <= maxLen) return t;
  return `${t.slice(0, maxLen - 1)}…`;
}

function vendorHeaderCell(
  vendor: string,
  vendorLabels: Record<string, VendorLabel>,
  vendorMeta: Record<string, VendorMeta>,
  compact = false,
  companyMax = 32,
  variantMax = 28
): string {
  const info = vendorLabels[vendor];
  const meta = vendorMeta[vendor] || {};
  const company = truncate(info?.company ?? vendor.split(" (")[0], compact ? companyMax : 32);
  const lines = [company];
  if (info?.variant) lines.push(truncate(info.variant, compact ? variantMax : 28));
  const qno = info?.quoteNumber ? `#${info.quoteNumber}` : "";
  const qdate = info?.quoteDate || meta.quote_date || "";
  if (qno || qdate) lines.push([qno, qdate].filter(Boolean).join(" · "));
  return lines.join("\n");
}

function buildColumnStyles(
  vendors: string[],
  tableWidth: number,
  layout: ReturnType<typeof pdfLayout>
): Record<number, { cellWidth: number; halign?: "right" | "left" }> {
  const descWidth = Math.min(52, tableWidth * layout.descShare);
  const avgWidth = layout.avgWidth;
  const vendorWidth = (tableWidth - descWidth - avgWidth) / Math.max(vendors.length, 1);

  const styles: Record<number, { cellWidth: number; halign?: "right" | "left" }> = {
    0: { cellWidth: descWidth, halign: "left" },
    1: { cellWidth: avgWidth, halign: "right" },
  };
  vendors.forEach((_, i) => {
    styles[i + 2] = { cellWidth: vendorWidth, halign: "right" };
  });
  return styles;
}

const TATVA_LOGO_PATH = "/tatva_assets.jpg";

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

/** Generate and download comparison matrix PDF directly (no print dialog). */
export async function downloadComparisonPdf(
  tableData: TableRow[],
  vendors: string[],
  vendorLabels: Record<string, VendorLabel>,
  vendorMeta: Record<string, VendorMeta> = {}
): Promise<void> {
  const layout = pdfLayout(vendors.length);
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 10;
  const tableWidth = pageWidth - margin * 2;

  const logo = await loadLogoForPdf();
  let headerY = 12;
  if (logo) {
    const logoW = 38;
    const logoH = (logo.height / logo.width) * logoW;
    doc.addImage(logo.dataUrl, "JPEG", margin, 6, logoW, logoH);
    headerY = 6 + logoH + 5;
  }

  const today = new Date().toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  doc.setFont(FONT, "bold");
  doc.setFontSize(layout.title);
  doc.setTextColor(15, 23, 42);
  doc.text("Tatva Quotes Comparison Matrix", margin, headerY);
  doc.setFont(FONT, "normal");
  doc.setFontSize(layout.subtitle);
  doc.setTextColor(100, 116, 139);
  doc.text(`Generated by QuoteSense · ${today}`, margin, headerY + 5);
  doc.setTextColor(0, 0, 0);

  const tableStartY = headerY + 10;

  const vendorHeaders = vendors.map((v) =>
    vendorHeaderCell(v, vendorLabels, vendorMeta, true, layout.vendorTruncate, layout.variantTruncate)
  );
  const head = [["Service Description", "Moving Avg", ...vendorHeaders]];

  type BodyCell =
    | string
    | {
        content: string;
        colSpan?: number;
        styles?: Record<string, unknown>;
      };

  const body: BodyCell[][] = [];
  const pad = layout.cellPad;

  for (const cat of groupTableData(tableData)) {
    body.push([
      {
        content: cat.category.toUpperCase(),
        colSpan: vendors.length + 2,
        styles: {
          font: FONT,
          fillColor: [238, 242, 255],
          textColor: [30, 58, 138],
          fontStyle: "bold",
          fontSize: layout.category,
          cellPadding: { top: 2, bottom: 2, left: 3, right: 3 },
        },
      },
    ]);
    for (let subIdx = 0; subIdx < cat.subs.length; subIdx++) {
      const sub = cat.subs[subIdx];
      if (subIdx > 0) {
        body.push([
          {
            content: "",
            colSpan: vendors.length + 2,
            styles: {
              fillColor: SUB_GAP_FILL,
              minCellHeight: layout.subGap,
              cellPadding: 0,
              lineWidth: 0,
            },
          },
        ]);
      }

      const totals = sumSubServiceRow(sub.rows, vendors);
      const subAvg = totals.moving_average;
      const subAvgText = subAvg > 0 ? formatPdfAmount(subAvg) : "—";

      const subCellStyle = {
        font: FONT,
        fillColor: SUB_ROW_FILL,
        fontStyle: "bold" as const,
        cellPadding: { top: 3, bottom: 3, left: 4, right: 3 },
        lineColor: [148, 163, 184] as [number, number, number],
        lineWidth: 0.2,
      };

      body.push([
        {
          content: sub.sub.toUpperCase(),
          styles: {
            ...subCellStyle,
            fontSize: layout.subTotalLabel,
            textColor: [30, 41, 59],
          },
        },
        {
          content: subAvgText,
          styles: {
            ...subCellStyle,
            fontSize: layout.subTotalAmount,
            textColor: [49, 46, 129],
            fillColor: SUB_AVG_FILL,
            halign: "right" as const,
          },
        },
        ...vendors.map((v) => ({
          content: formatPdfPrice(totals[v]),
          styles: {
            ...subCellStyle,
            fontSize: layout.subTotalAmount,
            textColor: [15, 23, 42],
            halign: "right" as const,
          },
        })),
      ]);

      for (const row of sub.rows) {
        const avg = Number(row.moving_average ?? row.market_average) || 0;
        const weight = Number(row.moving_weight) || 0;
        let avgText = avg > 0 ? formatPdfAmount(avg) : "—";
        const quoteCountLabel = formatQuoteCountLabel(weight);
        if (quoteCountLabel) avgText += `\n${quoteCountLabel}`;

        const { title, room } = lineItemDescription(row);
        const desc = room ? `${title}\n${room}` : title;

        body.push([
          {
            content: desc,
            styles: {
              font: FONT,
              fontSize: layout.body,
              cellPadding: { top: pad, bottom: pad, left: 8, right: pad },
              textColor: [51, 65, 85],
            },
          },
          avgText,
          ...vendors.map((v) => formatPdfPrice(row[v])),
        ]);
      }
    }
  }

  const columnStyles = buildColumnStyles(vendors, tableWidth, layout);

  autoTable(doc, {
    head,
    body: body as Parameters<typeof autoTable>[1]["body"],
    startY: tableStartY,
    tableWidth,
    margin: { left: margin, right: margin, top: tableStartY, bottom: 10 },
    theme: "grid",
    styles: {
      font: FONT,
      fontSize: layout.body,
      cellPadding: { top: pad, bottom: pad, left: pad, right: pad },
      overflow: "linebreak",
      valign: "middle",
      lineColor: [203, 213, 225],
      lineWidth: 0.12,
      textColor: [30, 41, 59],
    },
    headStyles: {
      font: FONT,
      fillColor: [241, 245, 249],
      textColor: [15, 23, 42],
      fontStyle: "bold",
      fontSize: layout.head,
      minCellHeight: layout.headMinHeight,
      cellPadding: { top: pad, bottom: pad, left: pad, right: pad },
      overflow: "linebreak",
    },
    bodyStyles: {
      font: FONT,
      fontSize: layout.body,
    },
    columnStyles,
    showHead: "everyPage",
    rowPageBreak: "avoid",
    horizontalPageBreak: false,
  });

  doc.save("comparator.pdf");
}
