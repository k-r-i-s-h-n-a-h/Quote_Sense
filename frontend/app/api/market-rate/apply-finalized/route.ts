import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8001";

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

  try {
    const res = await fetch(`${BACKEND}/api/market-rate/apply-finalized`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message =
      err instanceof Error
        ? err.message
        : "Failed to reach market-rate backend.";
    return NextResponse.json({ status: "error", message }, { status: 502 });
  }
}
