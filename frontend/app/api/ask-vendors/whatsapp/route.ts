import { NextRequest, NextResponse } from "next/server";
import { getBackendBase } from "@/lib/backend-url";

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
    const res = await fetch(`${backend}/api/ask-vendors/whatsapp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Failed to reach the compare backend.";
    return NextResponse.json(
      { status: "error", message, backend },
      { status: 502 }
    );
  }
}
