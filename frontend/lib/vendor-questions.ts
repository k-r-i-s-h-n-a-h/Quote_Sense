/**
 * Questions a customer should raise with vendors, derived from the comparison
 * flags — not a cheapest-by-room scoreboard.
 */

import { buildVendorLabels, type VendorLabel, type VendorMeta } from "./format";
import {
  gstCompareBanner,
  gstModesDiffer,
  pricingMethodsDiffer,
  vendorsShareCompany,
  type CrossScopeRow,
  type SpaceNote,
  type SpaceRow,
  type Vendor,
} from "./compare-types";

export type VendorQuestion = {
  id: string;
  /** The sentence to put to the vendor. */
  text: string;
  /** Why this showed up — from the comparison, not invented. */
  why: string;
  /** Empty = every panel. Set when only one quote owns the flag. */
  vendors?: Vendor[];
};

export type AskVendorPanel = {
  key: string;
  title: string;
  subtitle: string;
  vendor?: Vendor;
  company: string;
  quoteNumber: string;
  phone: string;
  questions: VendorQuestion[];
};

function who(vendor: string, labels: Record<string, VendorLabel>): string {
  return labels[vendor]?.label || vendor.split(" (")[0] || vendor;
}

function vendorsOnRow(row: SpaceRow, vendors: Vendor[]): Vendor[] {
  return vendors.filter((v) => Number(row[v] || 0) > 0);
}

function inferNoteVendors(
  note: SpaceNote,
  rows: SpaceRow[] | undefined,
  vendors: Vendor[]
): Vendor[] | undefined {
  if (note.vendor && vendors.includes(note.vendor)) return [note.vendor];
  if (!rows?.length) return undefined;
  const hit = new Set<Vendor>();
  for (const row of rows) {
    if (String(row.space_id) !== String(note.space_id)) continue;
    for (const v of vendorsOnRow(row, vendors)) hit.add(v);
  }
  return hit.size ? [...hit] : undefined;
}

export function buildVendorQuestions(input: {
  vendors: Vendor[];
  vendorMeta?: Record<string, VendorMeta>;
  spaceNotes?: SpaceNote[];
  crossScope?: CrossScopeRow[];
  rows?: SpaceRow[];
}): VendorQuestion[] {
  const vendors = input.vendors;
  const labels = buildVendorLabels(vendors, input.vendorMeta);
  const out: VendorQuestion[] = [];
  const seen = new Set<string>();

  const add = (q: VendorQuestion) => {
    if (seen.has(q.id)) return;
    seen.add(q.id);
    out.push(q);
  };

  if (gstModesDiffer(vendors, input.vendorMeta)) {
    add({
      id: "gst-entry",
      text: "Confirm whether GST is included in your quoted figures, and on what basis.",
      why: gstCompareBanner(vendors, input.vendorMeta, labels),
    });
  }

  for (const note of input.spaceNotes ?? []) {
    const owners = inferNoteVendors(note, input.rows, vendors);
    if (note.match_tier === "UNASSIGNED") {
      add({
        id: `unassigned:${note.space_id}`,
        text: `Which numbered room does "${note.space}" belong to? Do not allocate it until you confirm.`,
        why: note.note,
        vendors: owners,
      });
    }
    if (note.match_tier === "BUNDLE_NOT_DECOMPOSABLE") {
      add({
        id: `bundle:${note.space_id}`,
        text: `Please break out "${note.space}" by room or trade so it can be compared line by line.`,
        why: note.note,
        vendors: owners,
      });
    }
  }

  for (const entry of input.crossScope ?? []) {
    const names = vendors
      .map((v) => {
        const side = entry.vendors?.[v];
        if (!side) return "";
        const place = side.space ? ` in ${side.space}` : "";
        return `${who(v, labels)}${place}`;
      })
      .filter(Boolean);
    add({
      id: `cross:${entry.group || names.join("|") || "scope"}`,
      text: `Confirm whether ${names.join(" and ")} are the same ${(entry.label || "scope").toLowerCase()} — the comparison did not merge them.`,
      why: entry.note || "",
    });
  }

  const priced = (input.rows ?? []).filter((row) => {
    if (vendors.length < 2) return false;
    const a = vendors[0];
    const b = vendors[1];
    const ma = row.measures?.[a];
    const mb = row.measures?.[b];
    if (!ma || !mb) return false;
    return pricingMethodsDiffer(ma, mb);
  });
  if (priced.length) {
    const samples = priced
      .slice(0, 3)
      .map((row) => row.sub_service)
      .filter(Boolean);
    add({
      id: "pricing-methods",
      text:
        "Confirm quantities are in the same physical unit on both quotes" +
        (samples.length ? ` (e.g. ${samples.join(", ")})` : "") +
        ".",
      why: "The comparison found rows priced in different units (for example per unit vs sq ft). Those quantities are not comparable as written.",
    });
  }

  add({
    id: "standing-na",
    text: "For every line shown as N/A against you, confirm it was not quoted — not bundled inside another room or package.",
    why: "A missing cell can mean a true gap or work sitting inside another space. Only you can say which.",
  });
  add({
    id: "standing-lumpsum",
    text: "If this quote used a lumpsum or package, list exactly what is included and what is billed separately.",
    why: "Package totals cannot be compared line-by-line until the contents are named.",
  });

  return out;
}

function questionForPanel(q: VendorQuestion, vendor: Vendor | undefined): boolean {
  if (!vendor || !q.vendors?.length) return true;
  return q.vendors.includes(vendor);
}

export function buildAskVendorPanels(input: {
  vendors: Vendor[];
  vendorMeta?: Record<string, VendorMeta>;
  spaceNotes?: SpaceNote[];
  crossScope?: CrossScopeRow[];
  rows?: SpaceRow[];
}): { sameCompany: boolean; panels: AskVendorPanel[] } {
  const vendors = input.vendors;
  const labels = buildVendorLabels(vendors, input.vendorMeta);
  const sameCompany = vendorsShareCompany(vendors, labels);
  const questions = buildVendorQuestions(input);

  if (sameCompany || vendors.length < 2) {
    const first = vendors[0];
    const company = labels[first]?.company || who(first, labels);
    const quoteBits = vendors
      .map((v) => labels[v]?.quoteNumber)
      .filter(Boolean)
      .map((n) => `#${n}`);
    const phone =
      vendors
        .map((v) => String(input.vendorMeta?.[v]?.phone || "").trim())
        .find(Boolean) || "";
    return {
      sameCompany: true,
      panels: [
        {
          key: "shared",
          title: `Ask ${company}`,
          subtitle: quoteBits.length
            ? `Both quotes · ${quoteBits.join(" and ")}`
            : "Both quotes from the same vendor",
          company,
          quoteNumber: quoteBits.join(", "),
          phone,
          questions,
        },
      ],
    };
  }

  return {
    sameCompany: false,
    panels: vendors.map((vendor) => {
      const info = labels[vendor];
      const company = info?.company || who(vendor, labels);
      const quoteNumber = info?.quoteNumber || "";
      return {
        key: vendor,
        title: `Ask ${company}`,
        subtitle: quoteNumber ? `Quote #${quoteNumber}` : "This vendor's quote",
        vendor,
        company,
        quoteNumber,
        phone: String(input.vendorMeta?.[vendor]?.phone || "").trim(),
        questions: questions.filter((q) => questionForPanel(q, vendor)),
      };
    }),
  };
}

export function formatVendorBrief(
  questions: VendorQuestion[],
  checkedIds: string[],
  notes: string,
  heading = "Questions for the vendors"
): string {
  const chosen = questions.filter((q) => checkedIds.includes(q.id));
  const lines = [heading, "", ...chosen.map((q, i) => `${i + 1}. ${q.text}`)];
  const extra = notes.trim();
  if (extra) {
    lines.push("", "Additional notes", extra);
  }
  return lines.join("\n").trim();
}

/** Body + variables for the MSG91 WhatsApp template (wired next). */
export type AskVendorsWhatsAppPayload = {
  vendor_name: string;
  quote_number: string;
  question_count: string;
  questions: string;
  notes: string;
  phone: string;
};

export function whatsappPayloadForPanel(
  panel: AskVendorPanel,
  checkedIds: string[],
  notes: string
): AskVendorsWhatsAppPayload {
  const chosen = panel.questions.filter((q) => checkedIds.includes(q.id));
  const questions = chosen.map((q, i) => `${i + 1}. ${q.text}`).join("\n");
  const extra = notes.trim();
  return {
    vendor_name: panel.company,
    quote_number: panel.quoteNumber || "—",
    question_count: String(chosen.length),
    questions: questions || "—",
    notes: extra || "—",
    phone: panel.phone || "",
  };
}

/** Shown in the UI until MSG91 is connected. */
export function formatWhatsAppPreview(payload: AskVendorsWhatsAppPayload): string {
  return [
    `Hi ${payload.vendor_name},`,
    "",
    `We compared quote ${payload.quote_number} and need ${payload.question_count} confirmation(s):`,
    "",
    payload.questions,
    payload.notes !== "—" ? `\nNotes: ${payload.notes}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}
