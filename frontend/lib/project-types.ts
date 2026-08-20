/** Shared project / quote types for dashboard + compare UI. */

export type QuoteStatus = "draft" | "submitted" | "revised" | "finalized";

/** Quote type as set on the Tatva PM platform (matches backend service_type). */
export type QuoteTier = "ESSENTIAL" | "MID_SEGMENT" | "LUXURY";

export type VendorQuote = {
  id: string;
  quoteNumber: string;
  label: string;
  amount: number;
  date: string;
  status: QuoteStatus;
  /** True when Tatva isFinalizeQuote is true — shows a separate FINALIZED badge. */
  isFinalizeQuote?: boolean;
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
  envKey?: string;
};

export type ProjectData = {
  id: string;
  title: string;
  service: TatvaService;
  projectCode: string;
  clientName: string;
  status: "in_progress" | "quotes_received" | "comparing" | "completed";
  brief: string;
  vendors: ProjectVendor[];
};

export type ProjectSummary = Pick<
  ProjectData,
  "id" | "title" | "service" | "projectCode" | "clientName" | "status" | "brief"
> & {
  vendorCount: number;
  quoteCount: number;
  /** Quote-level only — does not change project.status. */
  finalizedQuoteCount: number;
  updatedAt: string;
};

export const TATVA_SERVICES: TatvaService[] = [
  {
    id: "interior",
    name: "Residential Interior",
    icon: "🛋️",
    envKey: "NEXT_PUBLIC_SERVICE_INTERIORS",
  },
  {
    id: "construction",
    name: "Residential Construction",
    icon: "🏗️",
    envKey: "NEXT_PUBLIC_SERVICE_CONSTRUCTION",
  },
  {
    id: "solar",
    name: "Solar, Energy & Automation Solutions",
    icon: "☀️",
    envKey: "NEXT_PUBLIC_SERVICE_SOLAR",
  },
  {
    id: "painting",
    name: "Property Management & Rental Operations",
    icon: "🎨",
    envKey: "NEXT_PUBLIC_SERVICE_PAINTING",
  },
  {
    id: "plumbing",
    name: "Facility Management and Security",
    icon: "🔧",
    envKey: "NEXT_PUBLIC_SERVICE_PLUMBING",
  },
  {
    id: "electrical",
    name: "Home Renovation",
    icon: "⚡",
    envKey: "NEXT_PUBLIC_SERVICE_ELECTRICAL",
  },
  {
    id: "event_management",
    name: "Event Management",
    icon: "🎪",
    envKey: "NEXT_PUBLIC_SERVICE_EVENT_MANAGEMENT",
  },
  {
    id: "property_development",
    name: "Property Advisory, Sales & Leasing",
    icon: "🏢",
    envKey: "NEXT_PUBLIC_SERVICE_PROPERTY_DEVELOPMENT",
  },
  {
    id: "home_automation",
    name: "Home Maintenance & Appliance Care",
    icon: "🏠",
    envKey: "NEXT_PUBLIC_SERVICE_HOME_AUTOMATION",
  },
  {
    id: "farm_infrastructure",
    name: "Farm Infrastructure Setup",
    icon: "🌾",
    envKey: "NEXT_PUBLIC_SERVICE_FARM_INFRASTRUCTURE",
  },
  {
    id: "irrigation_automation",
    name: "Irrigation Automation",
    icon: "💧",
    envKey: "NEXT_PUBLIC_SERVICE_IRRIGATION_AUTOMATION",
  },
];

export const QUOTE_TIER_LABELS: Record<QuoteTier, string> = {
  ESSENTIAL: "Essential",
  MID_SEGMENT: "Mid-segment",
  LUXURY: "Luxury",
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
  const quoteCount = project.vendors.reduce((n, v) => n + v.quotes.length, 0);
  const finalizedQuoteCount = project.vendors.reduce(
    (n, v) => n + v.quotes.filter((q) => q.status === "finalized").length,
    0
  );
  return {
    id: project.id,
    title: project.title,
    service: project.service,
    projectCode: project.projectCode,
    clientName: project.clientName,
    status: project.status,
    brief: project.brief,
    vendorCount: project.vendors.length,
    quoteCount,
    finalizedQuoteCount,
    updatedAt:
      updatedAt ??
      project.vendors[0]?.quotes[0]?.date ??
      "—",
  };
}
