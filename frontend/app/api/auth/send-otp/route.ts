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

    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const message =
      err instanceof Error && err.message.includes("ENOTFOUND")
        ? "Auth service unreachable. Check TATVA_API_BASE is set to https://devopsapi.withtatva.ai"
        : "Unable to send OTP. Please try again.";
    console.error("send-otp proxy failed:", err);
    return NextResponse.json({ success: false, message }, { status: 500 });
  }
}
