/** TatvaOps APIs — proxied via Next.js routes to avoid CORS on localhost. */

export const TATVA_API_BASE =
  process.env.TATVA_API_BASE || "https://api.withtatva.ai";

export const TATVA_USERS_API =
  process.env.TATVA_USERS_API_BASE || `${TATVA_API_BASE}/users/api`;

export const TATVA_VENDOR_API =
  process.env.TATVA_VENDOR_API_BASE || `${TATVA_API_BASE}/vendor/api`;

export type TatvaUser = {
  _id?: string;
  id?: string;
  phoneNumber?: string;
  name?: string;
  fullName?: string;
  username?: string;
  email?: string;
  status?: string;
  profileImage?: string;
};

export type AuthTokens = {
  accessToken: string;
  refreshToken?: string;
};

export type SendOtpResponse = {
  success: boolean;
  message: string;
  data?: { phoneNumber: string; otpSent: boolean };
};

export type VerifyOtpResponse = {
  success: boolean;
  message: string;
  data?: {
    user: TatvaUser;
    tokens: AuthTokens;
    accountType?: string;
    vendor?: unknown;
  };
};

export type UserProfileResponse = {
  success?: boolean;
  data?: TatvaUser;
} & TatvaUser;
