import { describe, expect, it } from "vitest";
import {
  buildAskVendorPanels,
  buildVendorQuestions,
  formatVendorBrief,
  whatsappPayloadForPanel,
} from "../vendor-questions";

const A = "EXCESS INTERIORS (QCN21BW)";
const B = "INT360 DESIGN (Q1K7W0G)";

describe("buildVendorQuestions", () => {
  it("always includes the standing N/A and lumpsum asks", () => {
    const qs = buildVendorQuestions({ vendors: [A, B] });
    expect(qs.map((q) => q.id)).toEqual(["standing-na", "standing-lumpsum"]);
  });

  it("adds an UNASSIGNED room to confirm before allocating", () => {
    const qs = buildVendorQuestions({
      vendors: [A, B],
      spaceNotes: [
        {
          space_id: "unassigned:ground floor bedroom",
          space: "Ground floor bedroom",
          match_tier: "UNASSIGNED",
          note: "Vendor did not specify which bedroom — confirm before allocating.",
        },
      ],
    });
    const q = qs.find((item) => item.id.startsWith("unassigned:"));
    expect(q?.text).toContain("Ground floor bedroom");
    expect(q?.why).toContain("confirm before allocating");
  });

  it("adds a bundled zone as a request to break it out", () => {
    const qs = buildVendorQuestions({
      vendors: [A, B],
      spaceNotes: [
        {
          space_id: "common",
          space: "Common",
          match_tier: "BUNDLE_NOT_DECOMPOSABLE",
          note: "priced as a single bundled scope",
          suppress_line_matching: true,
        },
      ],
    });
    expect(qs.some((q) => q.id === "bundle:common")).toBe(true);
  });

  it("adds a possible cross-scope match without merging totals", () => {
    const qs = buildVendorQuestions({
      vendors: [A, B],
      crossScope: [
        {
          group: "bathroom_fitout",
          label: "Bathroom / washroom fit-out",
          note: "Possible match — confirm with vendor.",
          vendors: {
            [A]: { space_id: "walkin", space: "Walkin Closet", amount: 1 },
            [B]: { space_id: "bath", space: "First Floor Bathroom", amount: 1 },
          },
        },
      ],
    });
    const q = qs.find((item) => item.id === "cross:bathroom_fitout");
    expect(q?.text).toMatch(/Walkin Closet/);
    expect(q?.text).toMatch(/First Floor Bathroom/);
    expect(q?.text).toMatch(/did not merge/);
  });

  it("flags unit vs area pricing as a quantity question", () => {
    const qs = buildVendorQuestions({
      vendors: [A, B],
      rows: [
        {
          category: "Interiors",
          space_id: "kitchen",
          space: "Kitchen",
          space_raw: "Kitchen",
          work_key: "rolling",
          sub_service: "Rolling shutter",
          [A]: 27258,
          [B]: 17700,
          measures: {
            [A]: {
              quantity: 1,
              rate: 27258,
              pricing_method: "Per Unit / Each",
              pricing_method_id: "pm_unit",
            },
            [B]: {
              quantity: 8,
              rate: 2212,
              pricing_method: "Area – Direct Entry (sq ft)",
              pricing_method_id: "pm_area",
            },
          },
        },
      ],
    });
    expect(qs.some((q) => q.id === "pricing-methods")).toBe(true);
    expect(qs.find((q) => q.id === "pricing-methods")?.text).toContain(
      "Rolling shutter"
    );
  });
});

describe("buildAskVendorPanels", () => {
  it("keeps one checklist when both quotes are the same company", () => {
    const { sameCompany, panels } = buildAskVendorPanels({
      vendors: [
        "INFOSYS LIMITED (Q2OE1CX)",
        "INFOSYS LIMITED (QGT3A1I)",
      ],
      vendorMeta: {
        "INFOSYS LIMITED (Q2OE1CX)": {
          company: "INFOSYS LIMITED",
          quote_number: "Q2OE1CX",
        },
        "INFOSYS LIMITED (QGT3A1I)": {
          company: "INFOSYS LIMITED",
          quote_number: "QGT3A1I",
        },
      },
    });
    expect(sameCompany).toBe(true);
    expect(panels).toHaveLength(1);
    expect(panels[0].title).toBe("Ask INFOSYS LIMITED");
    expect(panels[0].subtitle).toContain("#Q2OE1CX");
    expect(panels[0].subtitle).toContain("#QGT3A1I");
  });

  it("splits a checklist per vendor when the companies differ", () => {
    const { sameCompany, panels } = buildAskVendorPanels({
      vendors: [A, B],
      vendorMeta: {
        [A]: {
          company: "EXCESS INTERIORS",
          quote_number: "QCN21BW",
          phone: "9876543210",
        },
        [B]: {
          company: "INT360 DESIGN",
          quote_number: "Q1K7W0G",
          phone: "9123456789",
        },
      },
      spaceNotes: [
        {
          space_id: "common",
          space: "Common",
          match_tier: "BUNDLE_NOT_DECOMPOSABLE",
          vendor: B,
          note: "priced as a single bundled scope",
        },
      ],
    });
    expect(sameCompany).toBe(false);
    expect(panels.map((p) => p.title)).toEqual([
      "Ask EXCESS INTERIORS",
      "Ask INT360 DESIGN",
    ]);
    expect(panels[0].questions.some((q) => q.id === "bundle:common")).toBe(false);
    expect(panels[1].questions.some((q) => q.id === "bundle:common")).toBe(true);
    expect(panels[0].phone).toBe("9876543210");
    expect(panels[1].phone).toBe("9123456789");
  });
});

describe("formatVendorBrief", () => {
  it("lists only the ticked questions and the notes", () => {
    const brief = formatVendorBrief(
      [
        { id: "a", text: "Confirm GST.", why: "" },
        { id: "b", text: "Break out Common.", why: "" },
      ],
      ["b"],
      "Also: who supplies the WC?"
    );
    expect(brief).toContain("1. Break out Common.");
    expect(brief).not.toContain("Confirm GST");
    expect(brief).toContain("Also: who supplies the WC?");
  });

  it("treats empty notes as a dash so the template can still send", () => {
    const payload = whatsappPayloadForPanel(
      {
        key: A,
        title: "Ask EXCESS",
        subtitle: "Quote #Q1",
        company: "EXCESS INTERIORS",
        quoteNumber: "QCN21BW",
        phone: "9513158197",
        questions: [{ id: "a", text: "Confirm GST.", why: "" }],
      },
      ["a"],
      ""
    );
    expect(payload.notes).toBe("—");
    expect(payload.questions).toContain("Confirm GST");
  });
});
