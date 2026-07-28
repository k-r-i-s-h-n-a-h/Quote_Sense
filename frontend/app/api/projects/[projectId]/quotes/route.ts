import { NextRequest, NextResponse } from "next/server";
import { TATVA_VENDOR_API } from "@/lib/tatva-api";

type RouteContext = { params: Promise<{ projectId: string }> };

function backendBase(): string {
  return (
    process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/$/, "") ||
    "http://127.0.0.1:8001"
  );
}

/** Fire-and-forget: teach QuoteSense ObjectIds from Tatva quote payloads. */
function syncMarketRateCatalog(quotesPayload: unknown): void {
  const url = `${backendBase()}/api/market-rate/sync-catalog`;
  void fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(quotesPayload ?? {}),
  }).catch(() => {
    /* catalog sync is best-effort — never block project quotes */
  });
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
    if (res.ok) {
      syncMarketRateCatalog(data);
    }
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { success: false, message: "Unable to fetch project quotes." },
      { status: 500 }
    );
  }
}
