import { NextRequest, NextResponse } from "next/server";
import { TATVA_USERS_API } from "@/lib/tatva-api";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const phoneNumber = String(body.phoneNumber || "").trim();

    if (!phoneNumber || phoneNumber.length < 10) {
      return NextResponse.json(
        { success: false, message: "Please enter a valid phone number." },
        { status: 400 }
      );
    }

    const res = await fetch(`${TATVA_USERS_API}/auth/send-otp`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ phoneNumber }),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { success: false, message: "Unable to send OTP. Please try again." },
      { status: 500 }
    );
  }
}
