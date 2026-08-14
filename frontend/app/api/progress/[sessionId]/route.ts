import { NextRequest, NextResponse } from "next/server";
import { getBackendBase } from "@/lib/backend-url";

/**
 * Same-origin proxy for compare job progress.
 * Browser polls /api/progress/{sessionId}; Next forwards to FastAPI (Render).
 * Avoids CORS and broken NEXT_PUBLIC_BACKEND_URL pointing at the Vercel host.
 */
export async function GET(
  req: NextRequest,
  context: { params: Promise<{ sessionId: string }> }
) {
  const { sessionId } = await context.params;
  const sid = (sessionId || "").trim();
  if (!sid) {
    return NextResponse.json(
      { status: "error", message: "session_id is required." },
      { status: 400 }
    );
  }

  const hasPartial = req.nextUrl.searchParams.get("has_partial");
  const qs = new URLSearchParams();
  if (hasPartial) qs.set("has_partial", hasPartial);

  const BACKEND = getBackendBase();
  const url = `${BACKEND}/api/progress/${encodeURIComponent(sid)}${
    qs.toString() ? `?${qs.toString()}` : ""
  }`;

  try {
    const res = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    const data = await res.json().catch(() => ({
      status: "error",
      message: "Invalid progress response from backend.",
    }));
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to reach comparison backend.";
    return NextResponse.json({ status: "error", message }, { status: 502 });
  }
}
