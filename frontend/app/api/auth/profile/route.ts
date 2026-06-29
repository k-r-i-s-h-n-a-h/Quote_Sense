import { NextRequest, NextResponse } from "next/server";
import { TATVA_USERS_API } from "@/lib/tatva-api";

export async function GET(req: NextRequest) {
  try {
    const userId = req.nextUrl.searchParams.get("userId");
    const token = req.headers.get("authorization");

    if (!userId || !token) {
      return NextResponse.json(
        { success: false, message: "Missing user ID or authorization." },
        { status: 401 }
      );
    }

    const res = await fetch(`${TATVA_USERS_API}/users/${userId}`, {
      headers: {
        Authorization: token,
        Accept: "application/json",
      },
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("GET /api/auth/profile failed:", err);
    return NextResponse.json(
      { success: false, message: "Unable to fetch profile." },
      { status: 500 }
    );
  }
}

export async function PUT(req: NextRequest) {
  try {
    const userId = req.nextUrl.searchParams.get("userId");
    const authHeader = req.headers.get("authorization");

    if (!userId || !authHeader) {
      return NextResponse.json(
        { success: false, message: "Missing user ID or authorization." },
        { status: 401 }
      );
    }

    const body = await req.json();
    const payload = {
      ...body,
      ...(body.name && !body.fullName ? { fullName: body.name } : {}),
      ...(body.fullName && !body.name ? { name: body.fullName } : {}),
    };

    const res = await fetch(`${TATVA_USERS_API}/users/${encodeURIComponent(userId)}`, {
      method: "PUT",
      headers: {
        Authorization: authHeader.startsWith("Bearer ")
          ? authHeader
          : `Bearer ${authHeader}`,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    let data: Record<string, unknown>;
    try {
      data = await res.json();
    } catch {
      data = { success: false, message: `Profile update failed (${res.status}).` };
    }

    if (!res.ok && !data.message) {
      data.message =
        typeof data.error === "string"
          ? data.error
          : `Profile update failed (${res.status}).`;
      data.success = false;
    }

    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    console.error("Profile PUT error:", err);
    return NextResponse.json(
      { success: false, message: "Unable to update profile." },
      { status: 500 }
    );
  }
}
