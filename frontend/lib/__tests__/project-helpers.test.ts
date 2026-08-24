import { describe, expect, it } from "vitest";
import {
  getProjectById,
  getProjectsForUser,
} from "../dummy-project-data";
import {
  buildProjectWithQuotes,
  groupQuotesByVendor,
  isFinalizeFlag,
  mapApiProject,
  mapApiProjectsList,
  mapApiQuote,
  mapQuoteTier,
  unwrapApiList,
} from "../project-mappers";
import {
  findQuoteById,
  formatInr,
  getQuoteSelectionSummary,
  toProjectSummary,
} from "../project-types";
import type { TatvaUser } from "../tatva-api";
import {
  getUserDisplayName,
  getUserInitial,
  userNeedsName,
  withResolvedName,
} from "../user-display";
import {
  coverageIndex,
  groupTableData,
  isSpaceComparable,
  lineItemDescription,
  sumSubServiceRow,
} from "../compare-matrix";
import {
  amountOf,
  bundleRowsOf,
  coverageOf,
  parseCellStatus,
  projectRowsOf,
  spaceRowsOf,
} from "../compare-types";

describe("unwrapApiList", () => {
  it("unwraps nested data.docs", () => {
    const rows = unwrapApiList({ data: { docs: [{ id: "1" }] } });
    expect(rows).toHaveLength(1);
    expect(rows[0].id).toBe("1");
  });

  it("accepts plain arrays", () => {
    expect(unwrapApiList([{ id: "a" }])).toHaveLength(1);
  });

  it("returns [] for junk", () => {
    expect(unwrapApiList(null)).toEqual([]);
    expect(unwrapApiList("x")).toEqual([]);
  });
});


describe("isFinalizeQuote mapping", () => {
  it("keeps status submitted and sets isFinalizeQuote when flag true", () => {
    const q = mapApiQuote({
      _id: "abc",
      quoteNumber: "Q2F93K0",
      status: "submitted",
      isFinalizeQuote: true,
      pricingSummary: [{ label: "Grand total", value: 1125278 }],
    });
    expect(isFinalizeFlag({ isFinalizeQuote: true })).toBe(true);
    expect(q.status).toBe("submitted");
    expect(q.isFinalizeQuote).toBe(true);
  });

  it("leaves non-finalized quotes as submitted with flag false", () => {
    const q = mapApiQuote({
      _id: "x",
      quoteNumber: "Q1",
      status: "submitted",
      isFinalizeQuote: false,
    });
    expect(q.status).toBe("submitted");
    expect(q.isFinalizeQuote).toBe(false);
  });

  it("parses comma amounts and workSummary line counts", () => {
    const q = mapApiQuote({
      _id: "n",
      quoteNumber: "Q9",
      quoteType: "mid_level",
      pricingSummary: [{ label: "Grand Total", value: "1,25,000" }],
      workSummary: [
        {
          services: [{ workItems: [{ a: 1 }, { b: 2 }] }],
        },
      ],
    });
    expect(q.amount).toBe(125000);
    expect(q.lineItems).toBe(2);
    expect(q.tier).toBe("MID_SEGMENT");
  });
});

describe("mapApiProject / grouping / build", () => {
  it("maps a project with vendors and completed status", () => {
    const p = mapApiProject({
      _id: "p1",
      status: "completed",
      projectTitle: "Custom Build",
      projectId: "PRJ-9",
      vendors: [
        {
          vendorId: {
            _id: "v1",
            companyName: "Acme",
            fullName: "Ann",
            email: "a@x.com",
          },
        },
      ],
    });
    expect(p.id).toBe("p1");
    expect(p.status).toBe("completed");
    expect(p.vendors).toHaveLength(1);
    expect(p.vendors[0].companyName).toBe("Acme");
  });

  it("maps lux/essential tiers", () => {
    expect(mapQuoteTier({ quoteType: "luxury" })).toBe("LUXURY");
    expect(mapQuoteTier({ quoteType: "essential" })).toBe("ESSENTIAL");
    expect(mapQuoteTier({})).toBeUndefined();
  });

  it("groups multiple quotes for the same vendor", () => {
    const vendors = groupQuotesByVendor([
      {
        _id: "q1",
        quoteNumber: "A",
        vendorId: "v1",
        vendorDetail: { companyName: "Acme" },
        pricingSummary: [{ label: "Grand total", value: 100 }],
      },
      {
        _id: "q2",
        quoteNumber: "B",
        vendorId: "v1",
        vendorDetail: { companyName: "Acme" },
        pricingSummary: [{ label: "Grand total", value: 200 }],
      },
    ]);
    expect(vendors).toHaveLength(1);
    expect(vendors[0].quotes).toHaveLength(2);
    expect(vendors[0].quotes[0].amount).toBe(200);
  });

  it("builds project with quotes and list summaries", () => {
    const quote = {
      _id: "q1",
      quoteNumber: "Q1",
      vendorId: "v9",
      vendorDetail: { companyName: "BuildCo", vendorName: "Bob" },
      clientDetail: { clientName: "Client X" },
      projectTitle: "Interior Fitout",
      pricingSummary: [{ label: "Grand total", value: 50 }],
    };
    const built = buildProjectWithQuotes(null, "proj-zz", [quote]);
    expect(built.id).toBe("proj-zz");
    expect(built.clientName).toBe("Client X");
    expect(built.vendors[0].companyName).toBe("BuildCo");
    expect(built.status).toBe("quotes_received");

    const withRaw = buildProjectWithQuotes(
      { _id: "proj-zz", status: "in_progress", projectTitle: "Raw" },
      "proj-zz",
      [quote]
    );
    expect(withRaw.status).toBe("quotes_received");

    const list = mapApiProjectsList({
      projects: [
        {
          _id: "p2",
          status: "in_progress",
          quotes: [quote],
          updatedAt: "2026-01-02T00:00:00Z",
        },
      ],
    });
    expect(list[0].quoteCount).toBeGreaterThan(0);
  });
});

describe("project-types helpers", () => {
  const project = getProjectById("proj_interior_hsr_001")!;

  it("loads dummy project", () => {
    expect(project).toBeDefined();
    expect(project.vendors.length).toBeGreaterThan(0);
  });

  it("formatInr returns a currency-like string", () => {
    expect(formatInr(1000)).toMatch(/1,000|₹|INR/);
  });

  it("findQuoteById / selection summary", () => {
    const first = project.vendors[0].quotes[0];
    expect(findQuoteById(project, first.id)?.quote.id).toBe(first.id);
    expect(findQuoteById(project, "missing")).toBeNull();
    expect(getQuoteSelectionSummary(project, [first.id])).toHaveLength(1);
  });

  it("toProjectSummary counts quotes", () => {
    const summary = toProjectSummary(project);
    expect(summary.quoteCount).toBe(3);
    expect(summary.vendorCount).toBe(2);
  });

  it("getProjectsForUser returns summaries", () => {
    expect(getProjectsForUser("anyone").length).toBeGreaterThan(0);
  });
});

describe("user-display", () => {
  it("prefers name over fallback", () => {
    const user: TatvaUser = { name: "Krishna" };
    expect(getUserDisplayName(user)).toBe("Krishna");
    expect(getUserDisplayName(null)).toBe("there");
  });

  it("detects missing name", () => {
    const unnamed: TatvaUser = { phoneNumber: "999" };
    expect(userNeedsName(unnamed)).toBe(true);
    expect(userNeedsName({ name: "A" })).toBe(false);
  });

  it("uses PM username or first/last name when name is empty", () => {
    expect(getUserDisplayName({ username: "Priya" })).toBe("Priya");
    expect(userNeedsName({ username: "Priya" })).toBe(false);
    expect(getUserDisplayName({ firstName: "Ann", lastName: "Rao" })).toBe("Ann Rao");
    expect(userNeedsName({ firstName: "Ann", lastName: "Rao" })).toBe(false);
  });

  it("moves a phone stored in email onto phoneNumber", () => {
    const normalized = withResolvedName({ email: "9999910620" });
    expect(normalized.email).toBeUndefined();
    expect(normalized.phoneNumber).toBe("9999910620");
  });

  it("initial letter", () => {
    expect(getUserInitial({ name: "divya" })).toBe("D");
    expect(getUserInitial(null)).toBe("?");
  });
});

describe("compare-matrix", () => {
  it("groups rows by category then canonical space then sub-service", () => {
    const groups = groupTableData([
      { category: "Interiors", space: "GF-Bedroom1", sub_service: "Wardrobe", item_name: "Wardrobe" },
      { category: "Interiors", space: "GF-Bedroom1", sub_service: "Loft", item_name: "Loft" },
      { category: "Interiors", space: "Kitchen", sub_service: "Cabinets", item_name: "Cabinets" },
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].spaces).toHaveLength(2);
    expect(groups[0].spaces[0].space).toBe("GF-Bedroom1");
    expect(groups[0].spaces[0].subs).toHaveLength(2);
    expect(groups[0].spaces[1].space).toBe("Kitchen");
  });

  it("clusters Bedroom 1 + GF Bedroom 1 when space is already canonical", () => {
    const groups = groupTableData([
      { space: "GF-Bedroom1", space_raw: "Bedroom 1", sub_service: "Wardrobe", VendorA: 100 },
      { space: "GF-Bedroom1", space_raw: "Ground Floor Bedroom 1", sub_service: "Wardrobe", VendorB: 90 },
    ]);
    expect(groups[0].spaces).toHaveLength(1);
    expect(groups[0].spaces[0].space).toBe("GF-Bedroom1");
    expect(groups[0].spaces[0].subs[0].rows).toHaveLength(2);
  });

  it("sums sub-service rows", () => {
    const totals = sumSubServiceRow(
      [
        { VendorA: 100 },
        { VendorA: 50 },
      ],
      ["VendorA"]
    );
    expect(totals.VendorA).toBe(150);
  });

  it("lineItemDescription drops redundant room", () => {
    expect(lineItemDescription({ item_name: "Tile", room: "Tile" })).toEqual({
      title: "Tile",
      room: "",
    });
    expect(
      lineItemDescription({ work_item: "Wardrobe", room: "Bedroom" })
    ).toEqual({ title: "Wardrobe", room: "Bedroom" });
  });

  it("groups on work_key so differently worded labels share a row", () => {
    const groups = groupTableData([
      {
        space_id: "mbr",
        space: "Master-Bedroom",
        work_key: "alias:side_table",
        sub_service: "Side table",
        VendorA: 14160,
      },
      {
        space_id: "mbr",
        space: "Master-Bedroom",
        work_key: "alias:side_table",
        sub_service: "Side Table",
        VendorB: 9440,
      },
    ]);
    expect(groups[0].spaces[0].subs).toHaveLength(1);
    expect(groups[0].spaces[0].subs[0].rows).toHaveLength(2);
  });

  it("keeps different work_keys apart even when labels match", () => {
    const groups = groupTableData([
      { space_id: "kitchen", work_key: "alias:base_unit", sub_service: "Unit" },
      { space_id: "kitchen", work_key: "alias:wall_unit", sub_service: "Unit" },
    ]);
    expect(groups[0].spaces[0].subs).toHaveLength(2);
  });

  it("falls back to the label when a legacy payload has no work_key", () => {
    const groups = groupTableData([
      { space: "Kitchen", sub_service: "Base Unit", VendorA: 10 },
      { space: "Kitchen", sub_service: "Base Unit", VendorB: 20 },
      { space: "Kitchen", sub_service: "Wall Unit", VendorA: 30 },
    ]);
    expect(groups[0].spaces[0].subs).toHaveLength(2);
    expect(groups[0].spaces[0].subs[0].rows).toHaveLength(2);
  });

  it("accumulates distinct vendor wordings on the space header", () => {
    const groups = groupTableData([
      { space_id: "mbr", space: "Master-Bedroom", space_raw: "Master bedroom", sub_service: "A" },
      { space_id: "mbr", space: "Master-Bedroom", space_raw: "MBR Dressing unit", sub_service: "B" },
      { space_id: "mbr", space: "Master-Bedroom", space_raw: "Master bedroom", sub_service: "C" },
    ]);
    const raw = groups[0].spaces[0].spaceRaw;
    expect(raw).toContain("Master bedroom");
    expect(raw).toContain("MBR Dressing unit");
    // A repeated wording must not be listed twice.
    expect(raw.match(/Master bedroom/g)).toHaveLength(1);
  });

  it("preserves payload order rather than sorting", () => {
    const groups = groupTableData([
      { space_id: "kitchen", space: "Kitchen", sub_service: "Zebra" },
      { space_id: "foyer", space: "Foyer", sub_service: "Alpha" },
    ]);
    expect(groups[0].spaces.map((s) => s.space)).toEqual(["Kitchen", "Foyer"]);
  });

  it("sumSubServiceRow coerces malformed amounts to zero, not NaN", () => {
    const totals = sumSubServiceRow(
      [{ VendorA: "abc" }, { VendorA: 50 }],
      ["VendorA"]
    );
    expect(totals.VendorA).toBe(50);
  });
});

describe("compare coverage semantics", () => {
  it("parses a bundled cell status and names the bundle", () => {
    expect(parseCellStatus("incl_in_bundle:Hardware & accessories")).toEqual({
      status: "incl_in_bundle",
      bundleLabel: "Hardware & accessories",
    });
    expect(parseCellStatus("quoted").status).toBe("quoted");
    expect(parseCellStatus("not_quoted").status).toBe("not_quoted");
    // A legacy payload has no coverage at all; default to the old reading.
    expect(parseCellStatus(undefined).status).toBe("not_quoted");
  });

  it("marks a space not comparable when any vendor is bundled there", () => {
    const index = coverageIndex([
      {
        space_id: "kitchen",
        space: "Kitchen",
        vendor: "A",
        status: "quoted",
        comparable: false,
      },
      {
        space_id: "foyer",
        space: "Foyer",
        vendor: "A",
        status: "quoted",
        comparable: true,
      },
    ]);
    expect(isSpaceComparable(index, "kitchen", ["A"])).toBe(false);
    expect(isSpaceComparable(index, "foyer", ["A"])).toBe(true);
    // An unknown space has no bundle evidence, so treat it as comparable.
    expect(isSpaceComparable(index, "living", ["A"])).toBe(true);
  });

  it("amountOf never returns NaN", () => {
    expect(amountOf({ A: 100 }, "A")).toBe(100);
    expect(amountOf({ A: "oops" }, "A")).toBe(0);
    expect(amountOf({}, "A")).toBe(0);
  });

  it("tier accessors fall back to the legacy flat payload", () => {
    const legacy = {
      tableData: [
        { space_id: "kitchen", sub_service: "Base" },
        { space_id: "project_level", sub_service: "Blinds" },
      ],
    };
    expect(spaceRowsOf(legacy)).toHaveLength(1);
    expect(projectRowsOf(legacy)).toHaveLength(1);
    // No bundle section for a payload that predates the tiers.
    expect(bundleRowsOf(legacy)).toEqual([]);
    expect(coverageOf(legacy)).toEqual([]);
  });
});

describe("exact QA payload isFinalizeQuote:true", () => {
  it("maps Q2F93K0 shape with dual signals (submitted + finalized flag)", () => {
    const q = mapApiQuote({
      _id: "6a76ebf1f181b15829a606b8",
      quoteNumber: "Q2F93K0",
      status: "submitted",
      quoteType: "essential",
      isFinalizeQuote: true,
      pricingSummary: [{ label: "Grand total", value: 1125278.49 }],
      workSummary: [{ services: [{ workItems: [{ a: 1 }] }] }],
    });
    expect(q.status).toBe("submitted");
    expect(q.isFinalizeQuote).toBe(true);
    expect(q.quoteNumber).toBe("Q2F93K0");
  });

  it("buildProjectWithQuotes keeps submitted + isFinalizeQuote flag", () => {
    const payload = {
      success: true,
      data: [
        {
          _id: "6a76ebf1f181b15829a606b8",
          quoteNumber: "Q2F93K0",
          status: "submitted",
          isFinalizeQuote: true,
          vendorId: "v1",
          vendorDetail: {
            companyName: "Tata Consultancy Services Limited",
            vendorName: "vidya",
            companyEmail: "vidya.m@tatvaops.com",
          },
          pricingSummary: [{ label: "Grand total", value: 1125278.49 }],
        },
      ],
    };
    const project = buildProjectWithQuotes(null, "mongo1", payload);
    expect(project.vendors[0].quotes[0].status).toBe("submitted");
    expect(project.vendors[0].quotes[0].isFinalizeQuote).toBe(true);
  });

  it("false flag stays submitted without finalize", () => {
    const q = mapApiQuote({
      _id: "x",
      quoteNumber: "Q1",
      status: "submitted",
      isFinalizeQuote: false,
    });
    expect(q.status).toBe("submitted");
    expect(q.isFinalizeQuote).toBe(false);
  });
});
