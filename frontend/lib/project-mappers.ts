/**
 * Map TatvaOps PM API payloads → QuoteSense UI models.
 */

import {
  TATVA_SERVICES,
  type ProjectData,
  type ProjectSummary,
  type ProjectVendor,
  type QuoteStatus,
  type QuoteTier,
  type TatvaService,
  type VendorQuote,
  toProjectSummary,
} from "./project-types";

type RawRecord = Record<string, unknown>;

function asRecord(value: unknown): RawRecord | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as RawRecord)
    : null;
}

function asString(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return fallback;
}

function asNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const n = parseFloat(value.replace(/,/g, ""));
    if (Number.isFinite(n)) return n;
  }
  return fallback;
}

export function unwrapApiList(payload: unknown): RawRecord[] {
  if (Array.isArray(payload)) {
    return payload.map(asRecord).filter(Boolean) as RawRecord[];
  }
  const root = asRecord(payload);
  if (!root) return [];

  const listKeys = [
    "projectRequests",
    "projects",
    "quotes",
    "items",
    "results",
    "data",
    "docs",
  ] as const;

  for (const key of listKeys) {
    const direct = root[key];
    if (Array.isArray(direct)) {
      return direct.map(asRecord).filter(Boolean) as RawRecord[];
    }
  }

  const candidates = [root.data, root.projects, root.quotes, root.items, root.results];
  for (const c of candidates) {
    if (Array.isArray(c)) {
      return c.map(asRecord).filter(Boolean) as RawRecord[];
    }
    const nested = asRecord(c);
    if (nested) {
      for (const key of listKeys) {
        const arr = nested[key];
        if (Array.isArray(arr)) {
          return arr.map(asRecord).filter(Boolean) as RawRecord[];
        }
      }
    }
  }
  return [];
}

function serviceIconForName(name: string): string {
  const lower = name.toLowerCase();
  if (lower.includes("interior")) return "🛋️";
  if (lower.includes("construction") || lower.includes("residential")) return "🏗️";
  if (lower.includes("solar")) return "☀️";
  if (lower.includes("paint")) return "🎨";
  if (lower.includes("plumb")) return "🔧";
  if (lower.includes("electr")) return "⚡";
  if (lower.includes("landscape")) return "🌿";
  if (lower.includes("hvac")) return "❄️";
  return "📋";
}

function resolveService(name: string): TatvaService {
  const match = TATVA_SERVICES.find(
    (s) => s.name.toLowerCase() === name.toLowerCase()
  );
  if (match) return match;
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0, 32) || "general";
  return { id: slug, name: name || "General", icon: serviceIconForName(name) };
}

function mapProjectStatus(raw: string, hasVendors = false): ProjectData["status"] {
  const s = raw.toLowerCase().replace(/\s+/g, "_");
  if (s.includes("compar")) return "comparing";
  if (s.includes("quote") || s.includes("received") || s.includes("submitted")) {
    return "quotes_received";
  }
  if (hasVendors && (s.includes("progress") || s.includes("created"))) {
    return "quotes_received";
  }
  return "in_progress";
}

function formatProjectDate(raw: unknown): string {
  const s = asString(raw);
  if (!s) return "—";
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
    const [y, m, d] = s.slice(0, 10).split("-");
    return `${d}/${m}/${y}`;
  }
  return s;
}

function mapAssignedVendorFromProject(raw: RawRecord): ProjectVendor | null {
  const vendorDetail = asRecord(raw.vendorId);
  if (!vendorDetail) return null;
  const id = asString(vendorDetail._id);
  if (!id) return null;
  return {
    id,
    companyName: asString(vendorDetail.companyName, "Vendor"),
    contactName: asString(vendorDetail.fullName || vendorDetail.vendorName),
    email: asString(vendorDetail.email),
    quotes: [],
  };
}

function mapAssignedVendors(raw: RawRecord): ProjectVendor[] {
  const vendors = raw.vendors;
  if (!Array.isArray(vendors)) return [];
  const byId = new Map<string, ProjectVendor>();
  for (const entry of vendors) {
    const rec = asRecord(entry);
    if (!rec) continue;
    const vendor = mapAssignedVendorFromProject(rec);
    if (vendor && !byId.has(vendor.id)) byId.set(vendor.id, vendor);
  }
  return Array.from(byId.values());
}

function formatQuoteDate(raw: unknown): string {
  const s = asString(raw);
  if (!s) return "—";
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
    const [y, m, d] = s.slice(0, 10).split("-");
    return `${d}/${m}/${y}`;
  }
  return s;
}

function mapQuoteStatus(raw: string): QuoteStatus {
  const s = raw.toLowerCase();
  if (s.includes("draft")) return "draft";
  if (s.includes("revis")) return "revised";
  return "submitted";
}

/**
 * Read the quote's tier straight from the Tatva PM record — `quoteType` is the
 * canonical field (values: "essential" | "midlevel"/"mid_level" | "luxury").
 * Falls back to a few legacy field names for older payloads.
 */
export function mapQuoteTier(raw: RawRecord): QuoteTier | undefined {
  const candidates = [
    raw.quoteType,
    raw.quotationTier,
    raw.quoteTier,
    raw.pricingTier,
    raw.tier,
    raw.packageType,
    raw.quotationType,
    raw.budgetTier,
    raw.priceBand,
  ].map((v) => asString(v).toLowerCase());

  const joined = candidates.join(" ");
  if (joined.includes("luxury") || joined.includes("premium") || joined.includes("high")) {
    return "LUXURY";
  }
  if (joined.includes("mid") || joined.includes("standard") || joined.includes("medium")) {
    return "MID_SEGMENT";
  }
  if (
    joined.includes("essential") ||
    joined.includes("budget") ||
    joined.includes("economy") ||
    joined.includes("friendly") ||
    raw.isBudgetFriendly === true
  ) {
    return "ESSENTIAL";
  }
  return undefined;
}

/**
 * Secondary line under the quote number. The quote type (Essential/Mid-segment/
 * Luxury) already has its own badge, so it's deliberately NOT repeated here.
 */
function quoteLabel(raw: RawRecord): string {
  const draft = asString(raw.draftName);
  if (draft) return draft;
  const variant = asString(raw.variantName || raw.label || raw.title);
  if (variant) return variant;
  return "";
}

function countLineItems(raw: RawRecord): number {
  const workSummary = raw.workSummary;
  if (!Array.isArray(workSummary)) return 0;
  let count = 0;
  for (const block of workSummary) {
    const blockRec = asRecord(block);
    if (!blockRec) continue;
    const services = blockRec.services;
    if (!Array.isArray(services)) continue;
    for (const svc of services) {
      const svcRec = asRecord(svc);
      const items = svcRec?.workItems;
      if (Array.isArray(items)) count += items.length;
    }
  }
  return count;
}

function extractGrandTotal(raw: RawRecord): number {
  const pricingSummary = raw.pricingSummary;
  if (Array.isArray(pricingSummary)) {
    for (const row of pricingSummary) {
      const rec = asRecord(row);
      const label = asString(rec?.label).toLowerCase();
      if (label.includes("grand") && label.includes("total")) {
        return asNumber(rec?.value);
      }
    }
    const totalRow = pricingSummary
      .map(asRecord)
      .find((r) => asString(r?.label).toLowerCase().includes("total"));
    if (totalRow) return asNumber(totalRow.value);
  }
  return asNumber(raw.projectValue || raw.grandTotal || raw.totalAmount);
}

export function mapApiProject(raw: RawRecord): ProjectData {
  const enquiry = asRecord(raw.enquiryId);
  const enquirySummary = asRecord(enquiry?.summary);
  const serviceObj = asRecord(raw.serviceId);
  const user = asRecord(raw.user);
  const address = asRecord(raw.addressId);

  const serviceName =
    asString(serviceObj?.name) ||
    asString(enquiry?.serviceName) ||
    asString(raw.projectTitle) ||
    asString(raw.serviceName) ||
    "General";

  const clientDetail = asRecord(raw.clientDetail);
  const clientName =
    asString(user?.fullName) ||
    asString(user?.name) ||
    asString(clientDetail?.clientName) ||
    asString(raw.clientName) ||
    asString(raw.customerName) ||
    "—";

  const projectCodeField = raw.projectId;
  const projectCode =
    (typeof projectCodeField === "string" && projectCodeField) ||
    asString(asRecord(projectCodeField)?.projectId) ||
    asString(raw.code) ||
    asString(raw._id).slice(-6).toUpperCase();

  const brief =
    asString(enquirySummary?.clientRequirements) ||
    asString(enquirySummary?.projectOverview) ||
    asString(raw.description) ||
    asString(raw.projectDescription) ||
    asString(address?.formattedAddress) ||
    asString(address?.locality) ||
    "TatvaOps project";

  const assignedVendors = mapAssignedVendors(raw);
  const title =
    asString(raw.title) ||
    asString(raw.name) ||
    `${serviceName} — ${projectCode}`;

  return {
    id: asString(raw._id || raw.id),
    title,
    service: resolveService(serviceName),
    projectCode,
    clientName,
    status: mapProjectStatus(asString(raw.status, "in_progress"), assignedVendors.length > 0),
    brief,
    vendors: assignedVendors,
  };
}

export function mapApiQuote(raw: RawRecord): VendorQuote {
  const tier = mapQuoteTier(raw);
  return {
    id: asString(raw._id || raw.id),
    quoteNumber: asString(raw.quoteNumber, "—"),
    label: quoteLabel(raw),
    amount: extractGrandTotal(raw),
    date: formatQuoteDate(raw.quoteDate || raw.createdAt),
    status: mapQuoteStatus(asString(raw.status, "submitted")),
    lineItems: countLineItems(raw),
    tier,
  };
}

export function mapApiQuoteToVendor(raw: RawRecord): ProjectVendor {
  const vendorDetail = asRecord(raw.vendorDetail) || {};
  const vendorId = asString(raw.vendorId || vendorDetail._id, "unknown-vendor");

  return {
    id: vendorId,
    companyName:
      asString(vendorDetail.companyName) ||
      asString(vendorDetail.vendorName) ||
      "Vendor",
    contactName: asString(vendorDetail.vendorName || vendorDetail.contactName),
    email: asString(vendorDetail.companyEmail || vendorDetail.email),
    quotes: [mapApiQuote(raw)],
  };
}

export function groupQuotesByVendor(quotes: RawRecord[]): ProjectVendor[] {
  const byVendor = new Map<string, ProjectVendor>();

  for (const raw of quotes) {
    const vendor = mapApiQuoteToVendor(raw);
    const existing = byVendor.get(vendor.id);
    if (!existing) {
      byVendor.set(vendor.id, vendor);
      continue;
    }
    const quote = vendor.quotes[0];
    if (quote && !existing.quotes.some((q) => q.id === quote.id)) {
      existing.quotes.push(quote);
    }
  }

  for (const v of byVendor.values()) {
    v.quotes.sort((a, b) => b.amount - a.amount);
  }

  return Array.from(byVendor.values());
}

export function mapApiProjectsList(payload: unknown): ProjectSummary[] {
  return unwrapApiList(payload).map((raw) => {
    const project = mapApiProject(raw);
    const quotes = unwrapApiList(raw.quotes);
    if (quotes.length > 0) {
      project.vendors = groupQuotesByVendor(quotes);
      project.status = "quotes_received";
    }
    return toProjectSummary(project, formatProjectDate(raw.updatedAt || raw.createdAt));
  });
}

export function buildProjectWithQuotes(
  projectRaw: RawRecord | null,
  projectId: string,
  quotesPayload: unknown
): ProjectData {
  const quotes = unwrapApiList(quotesPayload);
  const base = projectRaw
    ? mapApiProject(projectRaw)
    : {
        id: projectId,
        title: "Project",
        service: resolveService("General"),
        projectCode: projectId.slice(-6).toUpperCase(),
        clientName: "—",
        status: "in_progress" as const,
        brief: "TatvaOps project",
        vendors: [],
      };

  base.id = projectId;
  const quoteVendors = groupQuotesByVendor(quotes);
  if (quoteVendors.length > 0) {
    base.vendors = quoteVendors;
    base.status = "quotes_received";
  } else if (base.vendors.length === 0 && projectRaw) {
    base.vendors = mapAssignedVendors(projectRaw);
  }

  const firstQuote = quotes[0];
  if (firstQuote) {
    const clientDetail = asRecord(firstQuote.clientDetail);
    if (clientDetail) {
      base.clientName = asString(clientDetail.clientName, base.clientName);
    }
    const projectRef = asRecord(firstQuote.projectId);
    if (projectRef) {
      base.projectCode = asString(projectRef.projectId, base.projectCode);
      base.status = mapProjectStatus(asString(projectRef.status, base.status));
    }
    const title = asString(firstQuote.projectTitle);
    if (title) {
      base.title = title;
      base.service = resolveService(title);
    }
  }

  return base;
}
