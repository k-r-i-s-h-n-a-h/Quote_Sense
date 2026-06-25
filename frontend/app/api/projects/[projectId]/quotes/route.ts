import { NextRequest, NextResponse } from "next/server";
import { TATVA_VENDOR_API } from "@/lib/tatva-api";

type RouteContext = { params: Promise<{ projectId: string }> };

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
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { success: false, message: "Unable to fetch project quotes." },
      { status: 500 }
    );
  }
}
