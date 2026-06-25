import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8001";

/** Same-origin proxy — avoids CORS and large cross-origin POST issues. */
export async function POST(req: NextRequest) {
  const sessionId = req.nextUrl.searchParams.get("session_id");
  if (!sessionId) {
    return NextResponse.json(
      { status: "error", message: "session_id is required." },
      { status: 400 }
    );
  }

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
    const res = await fetch(
      `${BACKEND}/api/sync-mongodb-quotes?session_id=${encodeURIComponent(sessionId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    );

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to reach comparison backend.";
    return NextResponse.json({ status: "error", message }, { status: 502 });
  }
}
