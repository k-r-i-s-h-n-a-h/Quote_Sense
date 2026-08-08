import { NextRequest, NextResponse } from "next/server";
import { getBackendBase } from "@/lib/backend-url";

/** Same-origin proxy — avoids CORS and large cross-origin POST issues. */
export async function POST(req: NextRequest) {
  const sessionId = req.nextUrl.searchParams.get("session_id");
  if (!sessionId) {
    return NextResponse.json(
      { status: "error", message: "session_id is required." },
      { status: 400 }
    );
  }

  const projectId = req.nextUrl.searchParams.get("project_id");
  const authHeader = req.headers.get("authorization");

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { status: "error", message: "Invalid JSON body." },
      { status: 400 }
    );
  }

  const backendParams = new URLSearchParams({ session_id: sessionId });
  if (projectId) {
    backendParams.set("project_id", projectId);
  }

  const BACKEND = getBackendBase();

  try {
    const res = await fetch(
      `${BACKEND}/api/sync-mongodb-quotes?${backendParams.toString()}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(authHeader ? { Authorization: authHeader } : {}),
        },
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
