import { describe, expect, it } from "vitest";
import {
  dedupeById,
  findList,
  readTotalHint,
  shouldFetchNextPage,
} from "../projects-pagination";

describe("projects-pagination", () => {
  it("findList reads nested docs", () => {
    const loc = findList({ data: { docs: [{ _id: "a" }, { _id: "b" }] } });
    expect(loc?.items).toHaveLength(2);
    expect(loc?.path).toEqual(["data", "docs"]);
  });

  it("dedupeById drops duplicate mongo ids", () => {
    const out = dedupeById([
      { _id: "1", name: "a" },
      { _id: "1", name: "a2" },
      { _id: "2", name: "b" },
    ]);
    expect(out).toHaveLength(2);
    expect(out[0]).toMatchObject({ _id: "1", name: "a" });
  });

  it("readTotalHint from totalDocs", () => {
    expect(readTotalHint({ totalDocs: 121, data: [] })).toBe(121);
    expect(readTotalHint({ data: { total: "121" } })).toBe(121);
  });

  it("shouldFetchNextPage continues after short first page (81 vs 100)", () => {
    // Old bug: stopped when length !== page * 100, so 81 ended pagination early.
    expect(
      shouldFetchNextPage({
        page: 1,
        maxPages: 20,
        lastPageCount: 81,
        mergedCount: 81,
        totalHint: null,
      })
    ).toBe(true);
  });

  it("shouldFetchNextPage stops at total hint", () => {
    expect(
      shouldFetchNextPage({
        page: 1,
        maxPages: 20,
        lastPageCount: 81,
        mergedCount: 121,
        totalHint: 121,
      })
    ).toBe(false);
  });

  it("shouldFetchNextPage stops on empty page", () => {
    expect(
      shouldFetchNextPage({
        page: 2,
        maxPages: 20,
        lastPageCount: 0,
        mergedCount: 121,
        totalHint: null,
      })
    ).toBe(false);
  });
});
