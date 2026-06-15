import { NextRequest, NextResponse } from "next/server";
import { TATVA_USERS_API } from "@/lib/tatva-api";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const phoneNumber = String(body.phoneNumber || "").trim();
    const otp = String(body.otp || "").trim();

    if (!phoneNumber || !otp) {
      return NextResponse.json(
        { success: false, message: "Phone number and OTP are required." },
        { status: 400 }
      );
    }

    const res = await fetch(`${TATVA_USERS_API}/auth/verify-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ phoneNumber, otp }),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { success: false, message: "Unable to verify OTP. Please try again." },
      { status: 500 }
    );
  }
}
