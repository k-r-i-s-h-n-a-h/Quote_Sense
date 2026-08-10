/** Stable vendor palette shared across chart, matrix, insights, and summary cards. */

export const VENDOR_PALETTE = [
  "#2563eb", // blue
  "#7c3aed", // violet
  "#0f766e", // teal
  "#c2410c", // orange
  "#be185d", // rose
  "#0369a1", // sky
] as const;

export function vendorColor(index: number): string {
  return VENDOR_PALETTE[index % VENDOR_PALETTE.length];
}

export function vendorColorMap(vendors: string[]): Record<string, string> {
  const map: Record<string, string> = {};
  vendors.forEach((v, i) => {
    map[v] = vendorColor(i);
  });
  return map;
}
