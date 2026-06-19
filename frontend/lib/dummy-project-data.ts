/** Dummy project data — replace with TatvaOps API when endpoints are ready. */

export type QuoteStatus = "draft" | "submitted" | "revised";

export type VendorQuote = {
  id: string;
  quoteNumber: string;
  label: string;
  amount: number;
  date: string;
  status: QuoteStatus;
  lineItems: number;
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

export const TATVA_SERVICES: TatvaService[] = [
  { id: "interior", name: "Interior Design", icon: "🛋️" },
  { id: "construction", name: "Construction", icon: "🏗️" },
  { id: "solar", name: "Solar", icon: "☀️" },
  { id: "painting", name: "Painting", icon: "🎨" },
  { id: "plumbing", name: "Plumbing", icon: "🔧" },
  { id: "electrical", name: "Electrical", icon: "⚡" },
  { id: "landscaping", name: "Landscaping", icon: "🌿" },
  { id: "hvac", name: "HVAC", icon: "❄️" },
];

export const DUMMY_PROJECT: ProjectData = {
  id: "proj_interior_hsr_001",
  title: "3BHK Interior — HSR Layout",
  service: TATVA_SERVICES[0],
  projectCode: "0F43F5",
  clientName: "Divya MN",
  status: "quotes_received",
  brief:
    "Full interior for 3BHK including modular kitchen, wardrobes, false ceiling, and living room styling.",
  vendors: [
    {
      id: "vendor_tcs",
      companyName: "Tata Consultancy Services Limited",
      contactName: "Vidya MN",
      email: "vidya.m@tatvaops.com",
      quotes: [
        {
          id: "q_tcs_1",
          quoteNumber: "QOFOX67",
          label: "Initial proposal",
          amount: 1227554,
          date: "19/06/2026",
          status: "submitted",
          lineItems: 24,
        },
        {
          id: "q_tcs_2",
          quoteNumber: "QWBXRX8",
          label: "Revised — premium finish",
          amount: 1389200,
          date: "22/06/2026",
          status: "revised",
          lineItems: 26,
        },
      ],
    },
    {
      id: "vendor_int360",
      companyName: "INT360 DESIGN",
      contactName: "Manoj Kumar",
      email: "manoj@int360.in",
      quotes: [
        {
          id: "q_int_1",
          quoteNumber: "QAJ51Z8",
          label: "Standard package",
          amount: 1098500,
          date: "18/06/2026",
          status: "submitted",
          lineItems: 22,
        },
      ],
    },
    {
      id: "vendor_wallwood",
      companyName: "WALL AND WOOD DESIGN STUDIO",
      contactName: "Priya S",
      email: "priya@wallandwood.com",
      quotes: [
        {
          id: "q_ww_1",
          quoteNumber: "QMMP2K4",
          label: "Proposal A",
          amount: 1156000,
          date: "20/06/2026",
          status: "submitted",
          lineItems: 20,
        },
        {
          id: "q_ww_2",
          quoteNumber: "QNX7P2M",
          label: "Proposal B — minimal",
          amount: 987400,
          date: "21/06/2026",
          status: "submitted",
          lineItems: 18,
        },
        {
          id: "q_ww_3",
          quoteNumber: "QPL9K1R",
          label: "Revised after site visit",
          amount: 1043200,
          date: "23/06/2026",
          status: "revised",
          lineItems: 21,
        },
      ],
    },
  ],
};

export type ProjectSummary = Pick<
  ProjectData,
  "id" | "title" | "service" | "projectCode" | "clientName" | "status" | "brief"
> & {
  vendorCount: number;
  quoteCount: number;
  updatedAt: string;
};

export const DUMMY_PROJECTS: ProjectData[] = [
  DUMMY_PROJECT,
  {
    id: "proj_construction_whitefield",
    title: "G+2 Residential — Whitefield",
    service: TATVA_SERVICES[1],
    projectCode: "A7K2M1",
    clientName: "Krishna H",
    status: "in_progress",
    brief: "Ground plus two floors with structural work, brick masonry, and basic MEP rough-ins.",
    vendors: [
      {
        id: "v_build_1",
        companyName: "BuildRight Constructions",
        contactName: "Ramesh K",
        email: "ramesh@buildright.in",
        quotes: [
          {
            id: "q_br_1",
            quoteNumber: "QCNST01",
            label: "Phase 1 — structure",
            amount: 4850000,
            date: "15/06/2026",
            status: "submitted",
            lineItems: 18,
          },
        ],
      },
      {
        id: "v_build_2",
        companyName: "UrbanStruct Engineers",
        contactName: "Anita P",
        email: "anita@urbanstruct.com",
        quotes: [
          {
            id: "q_us_1",
            quoteNumber: "QCNST02",
            label: "Full build proposal",
            amount: 5120000,
            date: "16/06/2026",
            status: "submitted",
            lineItems: 22,
          },
          {
            id: "q_us_2",
            quoteNumber: "QCNST03",
            label: "Revised — optimized spec",
            amount: 4680000,
            date: "20/06/2026",
            status: "revised",
            lineItems: 20,
          },
        ],
      },
    ],
  },
  {
    id: "proj_solar_koramangala",
    title: "5kW Rooftop Solar — Koramangala",
    service: TATVA_SERVICES[2],
    projectCode: "SOL9X4",
    clientName: "Krishna H",
    status: "quotes_received",
    brief: "Rooftop solar installation with net metering and 5-year AMC.",
    vendors: [
      {
        id: "v_solar_1",
        companyName: "SunGrid Energy",
        contactName: "Deepak V",
        email: "deepak@sungrid.in",
        quotes: [
          {
            id: "q_sg_1",
            quoteNumber: "QSOL01",
            label: "Standard 5kW kit",
            amount: 285000,
            date: "10/06/2026",
            status: "submitted",
            lineItems: 8,
          },
          {
            id: "q_sg_2",
            quoteNumber: "QSOL02",
            label: "Premium panels + AMC",
            amount: 312000,
            date: "12/06/2026",
            status: "submitted",
            lineItems: 10,
          },
        ],
      },
      {
        id: "v_solar_2",
        companyName: "GreenWatt Solar",
        contactName: "Meera S",
        email: "meera@greenwatt.com",
        quotes: [
          {
            id: "q_gw_1",
            quoteNumber: "QSOL03",
            label: "Economy package",
            amount: 265000,
            date: "11/06/2026",
            status: "submitted",
            lineItems: 7,
          },
        ],
      },
    ],
  },
  {
    id: "proj_painting_indiranagar",
    title: "Full Home Repaint — Indiranagar",
    service: TATVA_SERVICES[3],
    projectCode: "PNT3B8",
    clientName: "Krishna H",
    status: "comparing",
    brief: "Interior and exterior repaint for 2BHK including waterproofing on terrace.",
    vendors: [
      {
        id: "v_paint_1",
        companyName: "ColourCraft Painters",
        contactName: "Suresh N",
        email: "suresh@colourcraft.in",
        quotes: [
          {
            id: "q_cc_1",
            quoteNumber: "QPNT01",
            label: "Asian Paints premium",
            amount: 185000,
            date: "08/06/2026",
            status: "submitted",
            lineItems: 12,
          },
        ],
      },
      {
        id: "v_paint_2",
        companyName: "FreshCoat Services",
        contactName: "Lakshmi R",
        email: "lakshmi@freshcoat.com",
        quotes: [
          {
            id: "q_fc_1",
            quoteNumber: "QPNT02",
            label: "Standard emulsion",
            amount: 142000,
            date: "09/06/2026",
            status: "submitted",
            lineItems: 10,
          },
          {
            id: "q_fc_2",
            quoteNumber: "QPNT03",
            label: "Revised — exterior only",
            amount: 98000,
            date: "14/06/2026",
            status: "revised",
            lineItems: 8,
          },
        ],
      },
    ],
  },
];

export function getProjectById(id: string): ProjectData | undefined {
  return DUMMY_PROJECTS.find((p) => p.id === id);
}

export function getProjectsForUser(_userName?: string | null): ProjectSummary[] {
  return DUMMY_PROJECTS.map((p) => ({
    id: p.id,
    title: p.title,
    service: p.service,
    projectCode: p.projectCode,
    clientName: p.clientName,
    status: p.status,
    brief: p.brief,
    vendorCount: p.vendors.length,
    quoteCount: p.vendors.reduce((n, v) => n + v.quotes.length, 0),
    updatedAt: p.vendors[0]?.quotes[0]?.date ?? "—",
  }));
}

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
