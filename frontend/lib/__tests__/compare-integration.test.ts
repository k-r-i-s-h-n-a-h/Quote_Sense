/**
 * Integration: a real backend MatrixV1 payload through the real grouping code.
 *
 * The unit tests use hand-written rows, so they cannot catch a field-name drift
 * between the backend projection and the frontend readers. This fixture is the
 * verbatim output of `run_comparison` over the two golden quotes
 * (backend/tests/fixtures), regenerated whenever the contract changes.
 */

import { describe, expect, it } from "vitest";
import { coverageIndex, groupTableData, isSpaceComparable, sumSubServiceRow } from "../compare-matrix";
import {
  amountOf,
  bundleRowsOf,
  coverageOf,
  isLumpSumBundle,
  parseCellStatus,
  partitionBundleRows,
  projectRowsOf,
  projectRowsForDisplay,
  recapPlacementNote,
  recapPlacementNotes,
  reconcileQuoteTotals,
  spaceRowsOf,
  vendorsShareCompany,
  withInferredPlacement,
  gstCompareBanner,
  gstEntryChip,
  gstModesDiffer,
  type BundleRow,
  type MatrixV1,
} from "../compare-types";
import { buildVendorLabels, type VendorLabel } from "../format";
import payload from "./fixtures/golden-matrix.json";

const matrix = payload as unknown as MatrixV1;
const [A, B] = matrix.vendors as string[];

describe("golden MatrixV1 payload", () => {
  it("is the contract version the readers expect", () => {
    expect(matrix.contract_version).toBe("MatrixV1");
    expect(spaceRowsOf(matrix).length).toBeGreaterThan(0);
    expect(bundleRowsOf(matrix).length).toBe(2);
    expect(projectRowsOf(matrix).length).toBe(5);
    expect(coverageOf(matrix).length).toBeGreaterThan(0);
  });

  it("groups without producing duplicate work rows in a space", () => {
    const groups = groupTableData(spaceRowsOf(matrix));
    for (const cat of groups) {
      for (const space of cat.spaces) {
        const keys = space.subs.map((s) => s.workKey);
        expect(new Set(keys).size, `duplicate work in ${space.space}`).toBe(
          keys.length
        );
      }
    }
  });

  it("renders the previously-split rows as single comparisons", () => {
    const groups = groupTableData(spaceRowsOf(matrix));
    const spaces = groups.flatMap((c) => c.spaces);
    const find = (space: string, label: string) =>
      spaces
        .find((s) => s.space === space)
        ?.subs.filter((sub) => sub.sub.toLowerCase() === label.toLowerCase()) ??
      [];

    for (const [space, label, a, b] of [
      ["Master-Bedroom", "Side table", 14160, 9440],
      ["Kitchen", "Rolling shutter", 27258, 17700],
      ["Living", "False ceiling", 61950, 49560],
      ["Dining", "Crockery units", 38940, 38940],
    ] as [string, string, number, number][]) {
      const subs = find(space, label);
      expect(subs, `${label} in ${space}`).toHaveLength(1);
      const totals = sumSubServiceRow(subs[0].rows, [A, B]);
      expect(totals[A]).toBe(a);
      expect(totals[B]).toBe(b);
    }
  });

  it("never renders a bundled cell as a plain zero", () => {
    const bundled = spaceRowsOf(matrix).filter(
      (row) => parseCellStatus(row.coverage?.[A]).status === "incl_in_bundle"
    );
    expect(bundled).toHaveLength(5);
    for (const row of bundled) {
      expect(amountOf(row, A)).toBe(0);
      expect(parseCellStatus(row.coverage?.[A]).bundleLabel).toBeTruthy();
    }
  });

  it("flags the room a bundle overlaps as not comparable", () => {
    const index = coverageIndex(coverageOf(matrix));
    const groups = groupTableData(spaceRowsOf(matrix));
    const spaces = groups.flatMap((c) => c.spaces);
    const kitchen = spaces.find((s) => s.space === "Kitchen")!;
    const foyer = spaces.find((s) => s.space === "Foyer")!;
    expect(isSpaceComparable(index, kitchen.spaceId, [A, B])).toBe(false);
    expect(isSpaceComparable(index, foyer.spaceId, [A, B])).toBe(true);
  });

  it("exposes the lumpsum against the itemised sum with both bases", () => {
    const hardware = bundleRowsOf(matrix).find(
      (row) => row.bundle_family === "hardware"
    )!;
    expect(amountOf(hardware, A)).toBe(100300);
    expect(amountOf(hardware, B)).toBe(37198);
    expect(hardware.basis?.[A]).toBe("bundle");
    expect(hardware.basis?.[B]).toBe("itemized");
    expect(hardware.overlap_flags?.length).toBeGreaterThan(0);
  });

  it("splits true lumpsums from scattered itemised families", () => {
    const { lumpSums, scattered } = partitionBundleRows(bundleRowsOf(matrix));
    expect(lumpSums.map((r) => r.bundle_family)).toContain("hardware");
    expect(scattered.map((r) => r.bundle_family)).toContain("lighting");
    expect(lumpSums.every(isLumpSumBundle)).toBe(true);
    expect(scattered.every((r) => !isLumpSumBundle(r))).toBe(true);
  });

  it("keeps every bundle amount out of the space totals", () => {
    const groups = groupTableData(spaceRowsOf(matrix));
    let spaceTotalA = 0;
    for (const cat of groups) {
      for (const space of cat.spaces) {
        spaceTotalA += sumSubServiceRow(
          space.subs.flatMap((s) => s.rows),
          [A]
        )[A];
      }
    }
    const bundleA = bundleRowsOf(matrix)
      .filter((row) => row.basis?.[A] === "bundle")
      .reduce((sum, row) => sum + amountOf(row, A), 0);
    expect(bundleA).toBe(100300);
    // The lumpsum is additive to the rooms, never already inside them.
    const projectA = sumSubServiceRow(projectRowsOf(matrix), [A])[A];
    expect(spaceTotalA + projectA + bundleA).toBe(1139054);
  });

  it("reconciles tier sums to each vendor's quote total", () => {
    const quoted = Object.fromEntries(
      (matrix.chartData ?? []).map((point) => [point.vendor, point.total])
    );
    const totals = reconcileQuoteTotals(
      matrix.vendors as string[],
      spaceRowsOf(matrix),
      bundleRowsOf(matrix),
      projectRowsOf(matrix),
      quoted
    );
    for (const point of matrix.chartData ?? []) {
      expect(totals[point.vendor]?.total).toBe(Math.round(point.total));
      expect(totals[point.vendor]?.matrix + totals[point.vendor]?.other).toBe(
        Math.round(point.total)
      );
    }
    // Infosys's hardware lumpsum must appear in the breakdown, not vanish.
    expect(totals[A].bundles).toBe(100300);
  });

  it("hides Whole-home lighting when the recap already compares that family", () => {
    const visible = projectRowsForDisplay(
      projectRowsOf(matrix),
      bundleRowsOf(matrix)
    );
    expect(visible.map((row) => row.sub_service)).toEqual(
      expect.arrayContaining(["Window blinds", "Tissue paper holder"])
    );
    expect(
      visible.some((row) =>
        /lighting|adaptor|electrical/i.test(String(row.work_key))
      )
    ).toBe(false);

    const unlabeled = {
      space_id: "project_level",
      sub_service: "Electrical Work",
      item_name: "Electrical Work",
      work_key: "norm:electrical_work",
      [B]: 17700,
    } as SpaceRow;
    expect(
      projectRowsForDisplay([unlabeled], bundleRowsOf(matrix))
    ).toEqual([]);

    const quoted = Object.fromEntries(
      (matrix.chartData ?? []).map((point) => [point.vendor, point.total])
    );
    const full = reconcileQuoteTotals(
      matrix.vendors as string[],
      spaceRowsOf(matrix),
      bundleRowsOf(matrix),
      projectRowsOf(matrix),
      quoted
    );
    const ifDisplayWereUsed = reconcileQuoteTotals(
      matrix.vendors as string[],
      spaceRowsOf(matrix),
      bundleRowsOf(matrix),
      visible,
      quoted
    );
    expect(full[B].project).toBeGreaterThan(ifDisplayWereUsed[B].project);
    expect(full[B].total).toBe(Math.round(quoted[B] as number));
  });

  it("still renders when the payload is stripped back to the legacy shape", () => {
    const legacy = { tableData: matrix.tableData } as MatrixV1;
    expect(bundleRowsOf(legacy)).toEqual([]);
    expect(coverageOf(legacy)).toEqual([]);
    expect(groupTableData(spaceRowsOf(legacy)).length).toBeGreaterThan(0);
    // With no coverage the old reading applies: a zero is simply not quoted.
    const index = coverageIndex(coverageOf(legacy));
    expect(isSpaceComparable(index, "kitchen", [A, B])).toBe(true);
  });
});

describe("recap placement copy", () => {
  const sameCompanyLabels: Record<string, VendorLabel> = {
    A: {
      company: "INFOSYS LIMITED",
      variant: "",
      quoteNumber: "Q3BS200",
      quoteDate: "",
      label: "INFOSYS LIMITED",
      full: "INFOSYS LIMITED #Q3BS200",
    },
    B: {
      company: "INFOSYS LIMITED",
      variant: "",
      quoteNumber: "Q3ZWIFS",
      quoteDate: "",
      label: "INFOSYS LIMITED",
      full: "INFOSYS LIMITED #Q3ZWIFS",
    },
  };

  const mixedRow: BundleRow = {
    placement: { A: "space", B: "project" },
    A: 17299,
    B: 17700,
  };

  it("names the quote number when both quotes are the same company", () => {
    expect(vendorsShareCompany(["A", "B"], sameCompanyLabels)).toBe(true);
    expect(
      recapPlacementNote(mixedRow, "A", sameCompanyLabels, true)
    ).toBe("#Q3BS200: already in the spaces above — comparison only");
    expect(
      recapPlacementNote(mixedRow, "B", sameCompanyLabels, true)
    ).toBe(
      "#Q3ZWIFS: one whole-home figure — included in this quote, not in the space sums"
    );
  });

  it("names the company when the vendors differ", () => {
    const labels = buildVendorLabels(matrix.vendors as string[], matrix.vendorMeta);
    const lighting = bundleRowsOf(matrix).find(
      (row) => row.bundle_family === "lighting"
    )!;
    expect(lighting.placement?.[A]).toBe("space");
    expect(lighting.placement?.[B]).toBe("mixed");
    expect(vendorsShareCompany(matrix.vendors as string[], labels)).toBe(false);
    const notes = recapPlacementNotes(
      lighting,
      matrix.vendors as string[],
      labels
    );
    expect(notes[0]).toContain("INFOSYS LIMITED");
    expect(notes[0]).toContain("already in the spaces above");
    expect(notes[1]).toContain("TATA CONSULTANCY SERVICES LIMITED");
    expect(notes[1]).toContain("split across spaces and Whole home");
  });

  it("does not summarise when both quotes sit in the same place", () => {
    const bothRooms: BundleRow = {
      placement: { A: "space", B: "space" },
      A: 100,
      B: 200,
    };
    expect(recapPlacementNotes(bothRooms, ["A", "B"], sameCompanyLabels)).toEqual(
      []
    );
  });

  it("infers rooms vs whole-home when the payload has no placement field", () => {
    const row: BundleRow = {
      bundle_family: "lighting",
      basis: { A: "itemized", B: "itemized" },
      A: 17299,
      B: 17700,
    };
    const spaces = [
      {
        space_id: "bedroom",
        bundle_family: "lighting",
        work_key: "alias:electrical_points",
        A: 5617,
        B: 0,
      },
    ];
    const project = [
      {
        space_id: "project_level",
        bundle_family: "lighting",
        work_key: "alias:electrical_work",
        A: 0,
        B: 17700,
      },
    ];
    const hydrated = withInferredPlacement(row, ["A", "B"], spaces, project);
    expect(hydrated.placement?.A).toBe("space");
    expect(hydrated.placement?.B).toBe("project");
    expect(
      recapPlacementNote(hydrated, "A", sameCompanyLabels, true)
    ).toContain("#Q3BS200");
    expect(
      recapPlacementNote(hydrated, "B", sameCompanyLabels, true)
    ).toContain("#Q3ZWIFS");
  });
});

describe("GST entry flags", () => {
  const labels: Record<string, VendorLabel> = {
    A: {
      company: "INFOSYS LIMITED",
      variant: "",
      quoteNumber: "Q3BS200",
      quoteDate: "",
      label: "INFOSYS LIMITED",
      full: "INFOSYS LIMITED #Q3BS200",
    },
    B: {
      company: "INFOSYS LIMITED",
      variant: "",
      quoteNumber: "QLIX48D",
      quoteDate: "",
      label: "INFOSYS LIMITED",
      full: "INFOSYS LIMITED #QLIX48D",
    },
  };

  it("does not banner when every quote used the same GST entry", () => {
    const meta = {
      A: { gst_mode: "exclusive" as const },
      B: { gst_mode: "exclusive" as const },
    };
    expect(gstModesDiffer(["A", "B"], meta)).toBe(false);
    expect(gstCompareBanner(["A", "B"], meta, labels)).toBe("");
    expect(gstEntryChip("exclusive")).toBe("Entered excl. GST");
  });

  it("names quote numbers when one quote is excl GST and the other incl GST", () => {
    const meta = {
      A: { gst_mode: "exclusive" as const },
      B: { gst_mode: "inclusive" as const },
    };
    expect(gstModesDiffer(["A", "B"], meta)).toBe(true);
    const banner = gstCompareBanner(["A", "B"], meta, labels);
    expect(banner).toContain("#Q3BS200 was entered excluding GST");
    expect(banner).toContain("#QLIX48D was entered including GST");
    expect(banner).toContain("Amounts below include GST");
  });
});
