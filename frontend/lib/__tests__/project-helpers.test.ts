import { describe, expect, it } from "vitest";
import {
  getProjectById,
  getProjectsForUser,
} from "../dummy-project-data";
import { isFinalizeFlag, mapApiQuote, unwrapApiList } from "../project-mappers";
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
} from "../user-display";
import {
  groupTableData,
  lineItemDescription,
  sumSubServiceRow,
} from "../compare-matrix";

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
  it("maps isFinalizeQuote true to status finalized even when status is submitted", () => {
    const q = mapApiQuote({
      _id: "abc",
      quoteNumber: "Q2F93K0",
      status: "submitted",
      isFinalizeQuote: true,
      pricingSummary: [{ label: "Grand total", value: 1125278 }],
    });
    expect(isFinalizeFlag({ isFinalizeQuote: true })).toBe(true);
    expect(q.status).toBe("finalized");
  });

  it("leaves non-finalized quotes as submitted", () => {
    const q = mapApiQuote({
      _id: "x",
      quoteNumber: "Q1",
      status: "submitted",
      isFinalizeQuote: false,
    });
    expect(q.status).toBe("submitted");
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

  it("initial letter", () => {
    expect(getUserInitial({ name: "divya" })).toBe("D");
    expect(getUserInitial(null)).toBe("?");
  });
});

describe("compare-matrix", () => {
  it("groups rows by category/sub-service", () => {
    const groups = groupTableData([
      { category: "Flooring", sub_service: "Tile", item_name: "A" },
      { category: "Flooring", sub_service: "Tile", item_name: "B" },
      { category: "Paint", sub_service: "Wall", item_name: "C" },
    ]);
    expect(groups).toHaveLength(2);
    expect(groups[0].subs[0].rows).toHaveLength(2);
  });

  it("sums sub-service rows", () => {
    const totals = sumSubServiceRow(
      [
        { VendorA: 100, moving_average: 90 },
        { VendorA: 50, moving_average: 40 },
      ],
      ["VendorA"]
    );
    expect(totals.VendorA).toBe(150);
    expect(totals.moving_average).toBe(130);
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
});
