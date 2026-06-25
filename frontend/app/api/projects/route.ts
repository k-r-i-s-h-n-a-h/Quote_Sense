import { NextRequest, NextResponse } from "next/server";
import { TATVA_USERS_API } from "@/lib/tatva-api";

export async function GET(req: NextRequest) {
  try {
    const userId = req.nextUrl.searchParams.get("userId");
    const auth = req.headers.get("authorization");

    if (!userId || !auth) {
      return NextResponse.json(
        { success: false, message: "Missing user ID or authorization." },
        { status: 401 }
      );
    }

    const url = `${TATVA_USERS_API}/users/projects/user/${encodeURIComponent(userId)}/`;
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
      { success: false, message: "Unable to fetch projects." },
      { status: 500 }
    );
  }
}
