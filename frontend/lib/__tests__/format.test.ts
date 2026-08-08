import { describe, expect, it } from "vitest";
import {
  buildVendorLabels,
  companyNameLines,
  formatInrFull,
  formatQuoteCountLabel,
  getChartYAxisConfig,
  priceVsBaseline,
  truncateLabel,
  vendorChartLabel,
  vendorCompanyName,
  vendorFileName,
} from "../format";

describe("vendorCompanyName / vendorFileName", () => {
  it("splits on first ' ('", () => {
    const v = "Acme Interiors (quote (1).pdf)";
    expect(vendorCompanyName(v)).toBe("Acme Interiors");
    expect(vendorFileName(v)).toBe("quote (1).pdf");
  });

  it("handles vendor without filename", () => {
    expect(vendorCompanyName("Solo Co")).toBe("Solo Co");
    expect(vendorFileName("Solo Co")).toBe("");
  });
});

describe("priceVsBaseline", () => {
  it("classifies below / above / neutral", () => {
    expect(priceVsBaseline(90, 100)).toBe("below");
    expect(priceVsBaseline(110, 100)).toBe("above");
    expect(priceVsBaseline(101, 100)).toBe("neutral");
    expect(priceVsBaseline(0, 100)).toBe("neutral");
  });
});

describe("format helpers", () => {
  it("truncates labels", () => {
    expect(truncateLabel("ABCDEFGHIJKLMNOP", 10)).toMatch(/…$/);
    expect(truncateLabel("short", 10)).toBe("short");
  });

  it("formats quote count label", () => {
    expect(formatQuoteCountLabel(1)).toBe("from 1 past quote");
    expect(formatQuoteCountLabel(3)).toBe("from 3 past quotes");
    expect(formatQuoteCountLabel(0)).toBe("");
  });

  it("formats INR", () => {
    expect(formatInrFull(150000)).toContain("1,50,000");
    expect(formatInrFull(Number.NaN)).toBe("₹0");
  });

  it("builds vendor chart label", () => {
    expect(vendorChartLabel("Short", 14)).toBe("Short");
    expect(vendorChartLabel("Very Long Company Name Here", 10)).toMatch(/…$/);
  });

  it("splits company name into lines", () => {
    const lines = companyNameLines("Acme Design Studio Private", 12);
    expect(lines.length).toBeGreaterThanOrEqual(1);
    expect(lines[0].length).toBeGreaterThan(0);
  });
});

describe("buildVendorLabels", () => {
  it("adds variant when same company has multiple quotes", () => {
    const vendors = [
      "Acme (option-a.pdf)",
      "Acme (option-b.pdf)",
    ];
    const labels = buildVendorLabels(vendors);
    expect(labels[vendors[0]].company).toBe("Acme");
    expect(labels[vendors[0]].variant.length).toBeGreaterThan(0);
  });
});

describe("getChartYAxisConfig", () => {
  it("handles empty totals", () => {
    const cfg = getChartYAxisConfig([]);
    expect(cfg.domain).toEqual([0, 1]);
  });

  it("uses K steps under 1L", () => {
    const cfg = getChartYAxisConfig([25_000, 40_000]);
    expect(cfg.domain[0]).toBe(0);
    expect(cfg.formatTick(10_000)).toMatch(/K|₹/);
  });

  it("uses L steps at/above 1L", () => {
    const cfg = getChartYAxisConfig([150_000, 250_000]);
    expect(cfg.formatTick(100_000)).toMatch(/L/);
  });
});
