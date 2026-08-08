import { NextRequest, NextResponse } from "next/server";
import { getBackendBase } from "@/lib/backend-url";
import { TATVA_VENDOR_API } from "@/lib/tatva-api";

type RouteContext = { params: Promise<{ projectId: string }> };

/** Fire-and-forget: teach QuoteSense ObjectIds from Tatva quote payloads. */
function syncMarketRateCatalog(quotesPayload: unknown): void {
  const url = `${getBackendBase()}/api/market-rate/sync-catalog`;
  void fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(quotesPayload ?? {}),
  }).catch(() => {
    /* catalog sync is best-effort — never block project quotes */
  });
}

/**
 * Merge isFinalizeQuote Mongo payloads into market_moving_averages.
 * Awaited (with short timeout) so hosted FE reliably hits the Render backend
 * instead of silently targeting localhost when NEXT_PUBLIC_* is wrong.
 */
async function applyFinalizedQuotesFromPayload(
  quotesPayload: unknown
): Promise<{ ok: boolean; detail?: string }> {
  const url = `${getBackendBase()}/api/market-rate/apply-finalized`;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 25_000);
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(quotesPayload ?? {}),
      signal: controller.signal,
    });
    clearTimeout(timer);
    const body = (await res.json().catch(() => ({}))) as {
      quotes_applied?: number;
      message?: string;
    };
    if (!res.ok) {
      return { ok: false, detail: body.message || `HTTP ${res.status}` };
    }
    return {
      ok: true,
      detail: `quotes_applied=${body.quotes_applied ?? 0}`,
    };
  } catch (e) {
    const msg = e instanceof Error ? e.message : "apply failed";
    console.error("[market-rate] apply-finalized failed:", url, msg);
    return { ok: false, detail: msg };
  }
}

export async function GET(req: NextRequest, context: RouteContext) {
  try {
    const { projectId } = await context.params;
    const auth = req.headers.get("authorization");

    if (!projectId || !auth) {
      return NextResponse.json(
        { success: false, message: "Missing project ID or authorization." },
        { status: 401 }
      );
    }

    const url = `${TATVA_VENDOR_API}/vendor/quotes/project/${encodeURIComponent(projectId)}?quotationShare=true`;
    const res = await fetch(url, {
      headers: {
        Authorization: auth,
        Accept: "application/json",
      },
      cache: "no-store",
    });

    const data = await res.json();
    const headers = new Headers();
    headers.set("Cache-Control", "no-store");

    if (res.ok) {
      syncMarketRateCatalog(data);
      // Full Mongo quote list (incl. workSummary + isFinalizeQuote) → MA update
      const apply = await applyFinalizedQuotesFromPayload(data);
      headers.set(
        "X-Market-Rate-Apply",
        apply.ok ? apply.detail || "ok" : `error:${apply.detail || "fail"}`
      );
      headers.set("X-Backend-Base", getBackendBase());
    }

    return NextResponse.json(data, { status: res.status, headers });
  } catch {
    return NextResponse.json(
      { success: false, message: "Unable to fetch project quotes." },
      { status: 500 }
    );
  }
}
