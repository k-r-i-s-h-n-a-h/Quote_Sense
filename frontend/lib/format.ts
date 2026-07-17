/**
 * The API sends "Company Name (source_filename.pdf)". Split on the FIRST " ("
 * so filenames that themselves contain "(1)"/"(2)" don't break the parsing.
 */
export function vendorCompanyName(vendor: string): string {
  const idx = vendor.indexOf(" (");
  return idx > 0 ? vendor.slice(0, idx).trim() : vendor.trim();
}

/** Filename portion of a "Company (file)" vendor string, if any. */
export function vendorFileName(vendor: string): string {
  const idx = vendor.indexOf(" (");
  if (idx < 0) return "";
  let file = vendor.slice(idx + 2);
  if (file.endsWith(")")) file = file.slice(0, -1);
  return file.trim();
}

function cleanFileName(file: string): string {
  return file
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/\s*\(\d+\)\s*$/, "")
    .trim();
}

/**
 * Reduce a set of similar filenames to just their distinguishing part by
 * stripping the words they all share at the start and end.
 * e.g. "Dura Plywood II Client ... Linea Vita" -> "Dura Plywood".
 */
function distinguishingTokens(names: string[]): string[] {
  if (names.length <= 1) return names.slice();
  const tokenized = names.map((n) => n.split(/\s+/).filter(Boolean));

  let lead = 0;
  while (
    tokenized.every((t) => t.length > lead + 1) &&
    tokenized.every((t) => t[lead] === tokenized[0][lead])
  ) {
    lead++;
  }

  let trail = 0;
  while (
    tokenized.every((t) => t.length - 1 - trail > lead) &&
    tokenized.every(
      (t) => t[t.length - 1 - trail] === tokenized[0][tokenized[0].length - 1 - trail]
    )
  ) {
    trail++;
  }

  return tokenized.map((t) => {
    const slice = t.slice(lead, t.length - trail);
    return (slice.length ? slice : t).join(" ");
  });
}

export type VendorMeta = {
  company?: string;
  filename?: string;
  quote_number?: string;
  quote_date?: string;
};

export type VendorLabel = {
  company: string;
  variant: string;
  quoteNumber: string;
  quoteDate: string;
  /** Short primary text for a chart tick. */
  label: string;
  /** One-line full description for tooltips. */
  full: string;
};

/**
 * Build a display label per vendor string. When several quotes share the same
 * company name (e.g. same vendor, different material options), a distinguishing
 * "variant" is derived from the filename. Quote number and date come from the
 * backend metadata (vendorMeta) when available.
 */
export function buildVendorLabels(
  vendors: string[],
  meta?: Record<string, VendorMeta>
): Record<string, VendorLabel> {
  const companies = vendors.map(
    (v, i) => meta?.[v]?.company?.trim() || vendorCompanyName(v)
  );
  const counts: Record<string, number> = {};
  companies.forEach((c) => (counts[c] = (counts[c] || 0) + 1));

  const cleanedFiles = vendors.map(
    (v) => cleanFileName(meta?.[v]?.filename || vendorFileName(v))
  );
  const variants = distinguishingTokens(cleanedFiles);

  const result: Record<string, VendorLabel> = {};
  vendors.forEach((vendor, i) => {
    const company = companies[i];
    const quoteNumber = (meta?.[vendor]?.quote_number || "").trim();
    const quoteDate = (meta?.[vendor]?.quote_date || "").trim();
    let variant =
      counts[company] > 1 ? variants[i] || cleanedFiles[i] || "" : "";

    // Filenames often embed the quote number (e.g. "... QMXMB8E.pdf").
    // Drop that from the variant so charts/matrix don't show "QMXMB8E #QMXMB8E".
    if (quoteNumber && variant) {
      const q = quoteNumber.toLowerCase();
      const tokens = variant.split(/\s+/).filter(Boolean);
      const filtered = tokens.filter(
        (tok) => tok.replace(/^#/, "").toLowerCase() !== q
      );
      variant = filtered.join(" ").trim();
    }

    const label = variant ? `${company} — ${variant}` : company;

    const fullParts = [label];
    if (quoteNumber) fullParts.push(`#${quoteNumber}`);
    if (quoteDate) fullParts.push(quoteDate);
    const full = fullParts.join("  ·  ");

    result[vendor] = { company, variant, quoteNumber, quoteDate, label, full };
  });
  return result;
}

/** Truncate a label to fit a tilted chart tick. */
export function truncateLabel(name: string, maxLen = 16): string {
  if (name.length <= maxLen) return name;
  return `${name.slice(0, maxLen - 1).trim()}…`;
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
  const n = Math.round(Number(value));
  if (!Number.isFinite(n)) return "₹0";
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

/** Compare a vendor price to the moving-average baseline. */
export function priceVsBaseline(
  price: number,
  baseline: number
): "below" | "above" | "neutral" {
  if (!baseline || baseline <= 0 || !price || price <= 0) return "neutral";
  const diffPct = ((price - baseline) / baseline) * 100;
  if (Math.abs(diffPct) < 2) return "neutral";
  return diffPct < 0 ? "below" : "above";
}

/**
 * Moving-average sample size label.
 * Shown as "from N past quote(s)" to make clear this is historical data,
 * not a count of the vendors in the current comparison.
 */
export function formatQuoteCountLabel(count: number): string {
  const n = Math.round(Number(count));
  if (!Number.isFinite(n) || n <= 0) return "";
  return `from ${n} past ${n === 1 ? "quote" : "quotes"}`;
}
