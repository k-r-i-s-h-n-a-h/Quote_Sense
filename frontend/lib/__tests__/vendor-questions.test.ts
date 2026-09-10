import { describe, expect, it } from "vitest";
import {
  buildAskVendorPanels,
  buildVendorQuestions,
  emailPayloadForPanel,
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

  it("creates one anonymized cross-scope question per vendor", () => {
    const qs = buildVendorQuestions({
      vendors: [A, B],
      vendorMeta: {
        [A]: { company: "EXCESS INTERIORS", quote_number: "QCN21BW" },
        [B]: { company: "INT360 DESIGN", quote_number: "Q1K7W0G" },
      },
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
    const forA = qs.find((item) => item.id === `cross:bathroom_fitout:${A}`);
    const forB = qs.find((item) => item.id === `cross:bathroom_fitout:${B}`);
    expect(forA?.text).toContain("Walkin Closet");
    expect(forA?.text).toContain("#QCN21BW");
    expect(forA?.text).not.toContain("INT360");
    expect(forA?.text).not.toContain("First Floor Bathroom");
    expect(forB?.text).toContain("First Floor Bathroom");
    expect(forB?.text).toContain("#Q1K7W0G");
    expect(forB?.text).not.toContain("EXCESS");
    expect(forB?.text).not.toContain("Walkin Closet");
    expect(forA?.vendors).toEqual([A]);
    expect(forB?.vendors).toEqual([B]);
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
    expect(panels[0].quoteNumber).toBe("Q2OE1CX");
  });

  it("splits a checklist per vendor when the companies differ", () => {
    const { sameCompany, panels } = buildAskVendorPanels({
      vendors: [A, B],
      vendorMeta: {
        [A]: {
          company: "EXCESS INTERIORS",
          quote_number: "QCN21BW",
          phone: "9876543210",
          email: "quotes@excess.example",
        },
        [B]: {
          company: "INT360 DESIGN",
          quote_number: "Q1K7W0G",
          phone: "9123456789",
          email: "sales@int360.example",
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
    expect(panels[0].email).toBe("quotes@excess.example");
    expect(panels[1].email).toBe("sales@int360.example");
  });

  it("never puts the other vendor's identity in an outbound checklist", () => {
    const { panels } = buildAskVendorPanels({
      vendors: [A, B],
      vendorMeta: {
        [A]: {
          company: "EXCESS INTERIORS",
          quote_number: "QCN21BW",
        },
        [B]: {
          company: "INT360 DESIGN",
          quote_number: "Q1K7W0G",
        },
      },
      crossScope: [
        {
          group: "washroom_civil",
          label: "Washroom civil / tiling",
          vendors: {
            [A]: {
              space_id: "closet",
              space: "Walk-in Closet",
              amount: 214500,
            },
            [B]: {
              space_id: "bathroom",
              space: "First Floor Bathroom",
              amount: 236590,
            },
          },
          note:
            "Possible match between EXCESS INTERIORS and INT360 DESIGN.",
        },
      ],
    });
    const excessText = panels[0].questions.map((q) => q.text).join(" ");
    const int360Text = panels[1].questions.map((q) => q.text).join(" ");
    expect(excessText).not.toContain("INT360 DESIGN");
    expect(int360Text).not.toContain("EXCESS INTERIORS");
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
        email: "quotes@excess.example",
        questions: [{ id: "a", text: "Confirm GST.", why: "" }],
      },
      ["a"],
      ""
    );
    expect(payload.notes).toBe("—");
    expect(payload.questions).toContain("Confirm GST");
  });

  it("keeps the full ticked list for email, including empty notes", () => {
    const payload = emailPayloadForPanel(
      {
        key: A,
        title: "Ask EXCESS",
        subtitle: "Quote #Q1",
        company: "EXCESS INTERIORS",
        quoteNumber: "QCN21BW",
        phone: "9513158197",
        email: "quotes@excess.example",
        questions: [
          { id: "a", text: "Confirm GST.", why: "" },
          { id: "b", text: "List package contents.", why: "" },
        ],
      },
      ["a", "b"],
      ""
    );
    expect(payload.email).toBe("quotes@excess.example");
    expect(payload.questions).toEqual([
      "Confirm GST.",
      "List package contents.",
    ]);
    expect(payload.notes).toBe("");
  });
});
