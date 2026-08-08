import { afterEach, describe, expect, it, vi } from "vitest";
import {
  digitsOnly,
  isFinalizeFlagFromRecord,
  isTruthyFlag,
  parseLooseNumber,
} from "../finalize-flags";
import {
  applyFinalizedQuotesInBackground,
  filterFinalizedQuotePayloads,
} from "../market-rate-apply";
import { getBackendBase } from "../backend-url";
import {
  lookupMarketRate,
  recommendMarketRate,
  verdictStyles,
} from "../market-rate";

describe("finalize-flags", () => {
  it("isTruthyFlag", () => {
    expect(isTruthyFlag(true)).toBe(true);
    expect(isTruthyFlag(1)).toBe(true);
    expect(isTruthyFlag("yes")).toBe(true);
    expect(isTruthyFlag("TRUE")).toBe(true);
    expect(isTruthyFlag(false)).toBe(false);
    expect(isTruthyFlag("no")).toBe(false);
    expect(isTruthyFlag(null)).toBe(false);
  });

  it("detects finalize keys case-insensitively", () => {
    expect(isFinalizeFlagFromRecord({ isFinalizeQuote: true })).toBe(true);
    expect(isFinalizeFlagFromRecord({ is_finalized: "1" })).toBe(true);
    expect(isFinalizeFlagFromRecord({ isFinalizedQuote: true })).toBe(true);
    expect(isFinalizeFlagFromRecord({ status: "finalized" })).toBe(false);
    expect(isFinalizeFlagFromRecord({ isFinalizeQuote: false })).toBe(false);
  });

  it("digitsOnly and parseLooseNumber", () => {
    expect(digitsOnly("+91-98 76")).toBe("919876");
    expect(parseLooseNumber("1,25,000.5")).toBeCloseTo(125000.5);
  });
});

describe("filterFinalizedQuotePayloads", () => {
  it("unwraps nested data and filters", () => {
    const quotes = [
      { data: { quoteNumber: "A", isFinalizeQuote: true } },
      { quoteNumber: "B", is_finalized: false },
      { quote: { quoteNumber: "C", isFinalizeQuote: true } },
      "skip",
    ];
    const out = filterFinalizedQuotePayloads(quotes);
    expect(out).toHaveLength(2);
  });
});

describe("applyFinalizedQuotesInBackground", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("no-ops when none finalized", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    applyFinalizedQuotesInBackground([{ isFinalizeQuote: false }]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("posts finalized quotes", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    applyFinalizedQuotesInBackground([
      { quoteNumber: "Q1", isFinalizeQuote: true, workSummary: [] },
    ]);
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/market-rate/apply-finalized");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string);
    expect(body.quotes).toHaveLength(1);
  });

  it("swallows fetch errors", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network"))
    );
    expect(() =>
      applyFinalizedQuotesInBackground([{ isFinalizeQuote: true }])
    ).not.toThrow();
  });
});

describe("market-rate client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lookup and recommend success and error paths", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ recommend: true, message: "ok" }),
      })
      .mockResolvedValueOnce({ ok: false })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ recommend: true, verdict: "fair" }),
      })
      .mockResolvedValueOnce({ ok: false });
    vi.stubGlobal("fetch", fetchMock);

    const params = {
      service_category: "Interior",
      sub_service: "Painting",
      pricing_method: "sqft",
    };
    expect(await lookupMarketRate(params)).toEqual({
      recommend: true,
      message: "ok",
    });
    expect(await lookupMarketRate(params)).toEqual({
      recommend: false,
      message: "Could not load market data.",
    });
    expect((await recommendMarketRate({ ...params, entered_rate: 100 })).verdict).toBe(
      "fair"
    );
    expect(await recommendMarketRate(params)).toEqual({
      recommend: false,
      message: "Could not load market data.",
    });
  });

  it("verdictStyles branches", () => {
    expect(verdictStyles("low").border).toContain("amber");
    expect(verdictStyles("high").border).toContain("red");
    expect(verdictStyles("fair").border).toContain("emerald");
    expect(verdictStyles(undefined).border).toContain("slate");
  });
});

describe("getBackendBase", () => {
  const prevBackend = process.env.BACKEND_URL;
  const prevPublic = process.env.NEXT_PUBLIC_BACKEND_URL;

  afterEach(() => {
    if (prevBackend === undefined) delete process.env.BACKEND_URL;
    else process.env.BACKEND_URL = prevBackend;
    if (prevPublic === undefined) delete process.env.NEXT_PUBLIC_BACKEND_URL;
    else process.env.NEXT_PUBLIC_BACKEND_URL = prevPublic;
  });

  it("prefers BACKEND_URL and strips trailing slash", () => {
    process.env.BACKEND_URL = "https://api.example.com/";
    process.env.NEXT_PUBLIC_BACKEND_URL = "https://public.example.com";
    expect(getBackendBase()).toBe("https://api.example.com");
  });

  it("falls back to NEXT_PUBLIC then localhost", () => {
    delete process.env.BACKEND_URL;
    process.env.NEXT_PUBLIC_BACKEND_URL = "https://public.example.com";
    expect(getBackendBase()).toBe("https://public.example.com");
    delete process.env.NEXT_PUBLIC_BACKEND_URL;
    expect(getBackendBase()).toBe("http://127.0.0.1:8001");
  });
});
