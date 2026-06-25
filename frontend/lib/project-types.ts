/** Shared project / quote types for dashboard + compare UI. */

export type QuoteStatus = "draft" | "submitted" | "revised";

/** PM platform tier flags (premium / mid / budget). */
export type QuoteTier = "premium" | "mid_level" | "budget_friendly";

export type VendorQuote = {
  id: string;
  quoteNumber: string;
  label: string;
  amount: number;
  date: string;
  status: QuoteStatus;
  lineItems: number;
  tier?: QuoteTier;
};

export type ProjectVendor = {
  id: string;
  companyName: string;
  contactName: string;
  email: string;
  quotes: VendorQuote[];
};

export type TatvaService = {
  id: string;
  name: string;
  icon: string;
};

export type ProjectData = {
  id: string;
  title: string;
  service: TatvaService;
  projectCode: string;
  clientName: string;
  status: "in_progress" | "quotes_received" | "comparing";
  brief: string;
  vendors: ProjectVendor[];
};

export type ProjectSummary = Pick<
  ProjectData,
  "id" | "title" | "service" | "projectCode" | "clientName" | "status" | "brief"
> & {
  vendorCount: number;
  quoteCount: number;
  updatedAt: string;
};

export const TATVA_SERVICES: TatvaService[] = [
  { id: "interior", name: "Interior Design", icon: "🛋️" },
  { id: "construction", name: "Residential Construction", icon: "🏗️" },
  { id: "solar", name: "Solar", icon: "☀️" },
  { id: "painting", name: "Painting", icon: "🎨" },
  { id: "plumbing", name: "Plumbing", icon: "🔧" },
  { id: "electrical", name: "Electrical", icon: "⚡" },
  { id: "landscaping", name: "Landscaping", icon: "🌿" },
  { id: "hvac", name: "HVAC", icon: "❄️" },
];

export const QUOTE_TIER_LABELS: Record<QuoteTier, string> = {
  premium: "Premium",
  mid_level: "Mid level",
  budget_friendly: "Budget friendly",
};

export function formatInr(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function findQuoteById(project: ProjectData, quoteId: string) {
  for (const vendor of project.vendors) {
    const quote = vendor.quotes.find((q) => q.id === quoteId);
    if (quote) return { vendor, quote };
  }
  return null;
}

export function getQuoteSelectionSummary(
  project: ProjectData,
  selectedIds: string[]
) {
  return selectedIds
    .map((id) => findQuoteById(project, id))
    .filter(Boolean) as { vendor: ProjectVendor; quote: VendorQuote }[];
}

export function toProjectSummary(
  project: ProjectData,
  updatedAt?: string
): ProjectSummary {
  return {
    id: project.id,
    title: project.title,
    service: project.service,
    projectCode: project.projectCode,
    clientName: project.clientName,
    status: project.status,
    brief: project.brief,
    vendorCount: project.vendors.length,
    quoteCount: project.vendors.reduce((n, v) => n + v.quotes.length, 0),
    updatedAt:
      updatedAt ??
      project.vendors[0]?.quotes[0]?.date ??
      "—",
  };
}
