import { describe, expect, it } from "vitest";
import {
  MAX_COMPARE_QUOTES,
  clampQuoteIds,
  compareCountPhrase,
  dedupeQuoteIds,
  isValidCompareCount,
} from "../compare-limits";

describe("dedupeQuoteIds", () => {
  it("removes duplicates and blanks", () => {
    expect(dedupeQuoteIds(["a", " a ", "b", "", "a"])).toEqual(["a", "b"]);
  });
});

describe("clampQuoteIds", () => {
  it("caps at MAX_COMPARE_QUOTES", () => {
    expect(clampQuoteIds(["1", "2", "3", "4"])).toHaveLength(MAX_COMPARE_QUOTES);
  });
});

describe("compareCountPhrase", () => {
  it("is a single number when min equals max", () => {
    expect(compareCountPhrase()).toBe("2");
  });
});

describe("isValidCompareCount", () => {
  it("allows exactly MAX_COMPARE_QUOTES (min and max are 2)", () => {
    expect(isValidCompareCount(1)).toBe(false);
    expect(isValidCompareCount(2)).toBe(true);
    expect(isValidCompareCount(3)).toBe(false);
    expect(isValidCompareCount(4)).toBe(false);
  });
});
