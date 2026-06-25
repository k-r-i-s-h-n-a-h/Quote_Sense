/**
 * Dummy fallback data — used only when PM APIs are unavailable.
 * Live data comes from lib/project-api.ts.
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
  formatInr,
  findQuoteById,
  getQuoteSelectionSummary,
  toProjectSummary,
} from "./project-types";

export {
  TATVA_SERVICES,
  formatInr,
  findQuoteById,
  getQuoteSelectionSummary,
  toProjectSummary,
};
export type {
  ProjectData,
  ProjectSummary,
  ProjectVendor,
  QuoteStatus,
  QuoteTier,
  TatvaService,
  VendorQuote,
};

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
          tier: "premium",
        },
        {
          id: "q_tcs_2",
          quoteNumber: "QWBXRX8",
          label: "Revised — premium finish",
          amount: 1389200,
          date: "22/06/2026",
          status: "revised",
          lineItems: 26,
          tier: "premium",
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
          tier: "mid_level",
        },
      ],
    },
  ],
};

export const DUMMY_PROJECTS: ProjectData[] = [DUMMY_PROJECT];

export function getProjectById(id: string): ProjectData | undefined {
  return DUMMY_PROJECTS.find((p) => p.id === id);
}

export function getProjectsForUser(_userName?: string | null): ProjectSummary[] {
  return DUMMY_PROJECTS.map((p) => toProjectSummary(p));
}
