import { NextRequest, NextResponse } from "next/server";
import { getBackendBase } from "@/lib/backend-url";

/**
 * Proxy for finalized-quote → market_moving_averages.
 * Only payloads with isFinalizeQuote (etc.) are applied server-side.
 */
export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { status: "error", message: "Invalid JSON body." },
      { status: 400 }
    );
  }

  const backend = getBackendBase();
  try {
    const res = await fetch(`${backend}/api/market-rate/apply-finalized`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(
      { ...data, backend },
      {
        status: res.status,
        headers: { "X-Backend-Base": backend },
      }
    );
  } catch (err) {
    const message =
      err instanceof Error
        ? err.message
        : "Failed to reach market-rate backend.";
    return NextResponse.json(
      { status: "error", message, backend },
      { status: 502 }
    );
  }
}
