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
  } catch {
    return NextResponse.json(
      { success: false, message: "Unable to fetch profile." },
      { status: 500 }
    );
  }
}

export async function PUT(req: NextRequest) {
  try {
    const userId = req.nextUrl.searchParams.get("userId");
    const token = req.headers.get("authorization");

    if (!userId || !token) {
      return NextResponse.json(
        { success: false, message: "Missing user ID or authorization." },
        { status: 401 }
      );
    }

    const body = await req.json();
    const res = await fetch(`${TATVA_USERS_API}/users/${userId}`, {
      method: "PUT",
      headers: {
        Authorization: token,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { success: false, message: "Unable to update profile." },
      { status: 500 }
    );
  }
}
