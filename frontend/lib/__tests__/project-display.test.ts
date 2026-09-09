import { describe, expect, it } from "vitest";
import {
  lineIdsOfRow,
  projectRowsForDisplay,
  type BundleRow,
  type SpaceRow,
} from "../compare-types";

const A = "Cedar Works (Q-N)";
const B = "Maple Interiors (Q-S)";

function projectRow(
  lineId: string,
  extra: Partial<SpaceRow> = {}
): SpaceRow {
  return {
    space_id: "project_level",
    sub_service: extra.sub_service || "Work",
    item_name: extra.item_name || extra.sub_service || "Work",
    work_key: extra.work_key || "norm:work",
    bundle_family: extra.bundle_family || "hardware",
    source_line_ids: [lineId],
    line_ids: { [A]: [lineId], [B]: [] },
    [A]: 29146,
    [B]: 0,
    ...extra,
  } as SpaceRow;
}

function scatteredHardware(lineIds: string[]): BundleRow {
  return {
    bundle_id: "family:hardware",
    bundle_label: "Hardware",
    bundle_family: "hardware",
    has_bundle: false,
    basis: { [A]: "itemized", [B]: "itemized" },
    source_line_ids: lineIds,
    line_ids: { [A]: lineIds.slice(0, 1), [B]: lineIds.slice(1) },
    [A]: 40000,
    [B]: 38000,
  };
}

describe("projectRowsForDisplay line membership", () => {
  it("keeps a whole-home row whose family matches a recap but whose line is not in it", () => {
    const hinges = projectRow("wh:hinges", {
      sub_service: "Door closer hinges",
      item_name: "Door closer hinges",
      work_key: "norm:soft_closing_hinges",
      bundle_family: "hardware",
    });
    const recap = scatteredHardware(["room:a-hw", "room:b-hw"]);
    const visible = projectRowsForDisplay([hinges], [recap]);
    expect(visible).toEqual([hinges]);
  });

  it("still hides a whole-home row whose line id is in the recap", () => {
    const electrical = projectRow("wh:elec", {
      sub_service: "Electrical Work",
      bundle_family: "lighting",
    });
    const recap: BundleRow = {
      bundle_id: "family:lighting",
      bundle_family: "lighting",
      has_bundle: false,
      basis: { [A]: "itemized", [B]: "itemized" },
      source_line_ids: ["wh:elec", "room:b-light"],
      [A]: 17700,
      [B]: 12000,
    };
    expect(projectRowsForDisplay([electrical], [recap])).toEqual([]);
  });

  it("does not hide a whole-home hardware line just because another hardware recap exists", () => {
    const wholeHome = projectRow("wh:closers", {
      sub_service: "Soft closing - Hinges for doors",
      item_name: "Soft closing - Hinges for doors",
      work_key: "norm:soft_closing_hinges",
      bundle_family: "hardware",
    });
    const recap = scatteredHardware(["kit:tandem", "kit:cutlery"]);
    const visible = projectRowsForDisplay([wholeHome], [recap]);
    expect(visible.map((row) => row.source_line_ids)).toEqual([["wh:closers"]]);
  });

  it("never drops a source line from every painted surface", () => {
    const space: SpaceRow = {
      space_id: "kitchen",
      sub_service: "Tandem",
      source_line_ids: ["kit:tandem"],
      [A]: 12000,
      [B]: 0,
    } as SpaceRow;
    const wholeHome = projectRow("wh:closers", {
      sub_service: "Door closers",
      bundle_family: "hardware",
    });
    const recap = scatteredHardware(["kit:tandem", "kit:cutlery"]);
    const zone = { source_line_ids: ["zone:pest"] };

    const source = ["kit:tandem", "kit:cutlery", "wh:closers", "zone:pest"];
    const painted = new Set<string>([
      ...lineIdsOfRow(space),
      ...projectRowsForDisplay([wholeHome], [recap]).flatMap(lineIdsOfRow),
      ...lineIdsOfRow(recap),
      ...lineIdsOfRow(zone),
    ]);
    for (const id of source) {
      expect(painted.has(id)).toBe(true);
    }
  });
});
