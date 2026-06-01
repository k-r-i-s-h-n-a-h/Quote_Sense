/** Company name without trailing "(filename.pdf)" suffix from the API. */
export function vendorCompanyName(vendor: string): string {
  const idx = vendor.lastIndexOf(" (");
  return idx > 0 ? vendor.slice(0, idx) : vendor;
}

/** Split company name into up to 2 lines for chart X-axis (no PDF filename). */
export function companyNameLines(
  vendor: string,
  maxPerLine = 18
): [string] | [string, string] {
  const name = vendorCompanyName(vendor).trim();
  if (name.length <= maxPerLine) return [name];

  const words = name.split(/\s+/);
  if (words.length > 1) {
    let line1 = "";
    const rest: string[] = [];
    for (const word of words) {
      const candidate = line1 ? `${line1} ${word}` : word;
      if (candidate.length <= maxPerLine) line1 = candidate;
      else rest.push(word);
    }
    if (rest.length) {
      let line2 = rest.join(" ");
      if (line2.length > maxPerLine + 4) {
        line2 = `${line2.slice(0, maxPerLine - 1).trim()}…`;
      }
      return [line1, line2];
    }
  }

  const mid = Math.ceil(name.length / 2);
  const splitAt = name.lastIndexOf(" ", mid);
  if (splitAt > 0) {
    return [name.slice(0, splitAt), name.slice(splitAt + 1)];
  }
  return [
    `${name.slice(0, maxPerLine - 1)}…`,
    `${name.slice(maxPerLine - 1, maxPerLine * 2 - 1)}…`,
  ];
}

/** Short company name for tilted chart X-axis labels. */
export function vendorChartLabel(vendor: string, maxLen = 14): string {
  const name = vendorCompanyName(vendor);
  if (name.length <= maxLen) return name;
  return `${name.slice(0, maxLen - 1).trim()}…`;
}

const LAKH = 100_000;

/** 0-based Y-axis: ₹K steps if every quote is under ₹1L; otherwise ₹1L steps from 0. */
export function getChartYAxisConfig(totals: number[]): {
  domain: [number, number];
  ticks: number[];
  formatTick: (value: number) => string;
} {
  const values = totals.filter((t) => Number.isFinite(t) && t > 0);
  if (values.length === 0) {
    return { domain: [0, 1], ticks: [0, 1], formatTick: () => "₹0" };
  }

  const max = Math.max(...values);
  const anyBelowLakh = values.some((v) => v < LAKH);
  const allBelowLakh = values.every((v) => v < LAKH);

  if (allBelowLakh) {
    const step = max <= 50_000 ? 10_000 : 25_000;
    const domainMax = Math.max(step, Math.ceil(max / step) * step);
    const ticks: number[] = [];
    for (let v = 0; v <= domainMax; v += step) ticks.push(v);
    return {
      domain: [0, domainMax],
      ticks,
      formatTick: (v) =>
        v >= 1000 ? `₹${Math.round(v / 1000)}K` : `₹${Math.round(v)}`,
    };
  }

  const domainMax = Math.max(LAKH, Math.ceil(max / LAKH) * LAKH);
  const ticks: number[] = [];
  for (let v = 0; v <= domainMax; v += LAKH) ticks.push(v);

  return {
    domain: [0, domainMax],
    ticks,
    formatTick: (v) => {
      if (anyBelowLakh && v < LAKH) {
        return v >= 1000 ? `₹${Math.round(v / 1000)}K` : `₹${Math.round(v)}`;
      }
      const lakhs = v / LAKH;
      return Number.isInteger(lakhs)
        ? `₹${lakhs}L`
        : `₹${lakhs.toFixed(1)}L`;
    },
  };
}

export function formatInrFull(value: number): string {
  return `₹${Number(value).toLocaleString("en-IN")}`;
}
