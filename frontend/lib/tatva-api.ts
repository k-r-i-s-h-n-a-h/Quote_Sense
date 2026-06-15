/** TatvaOps user API — proxied via Next.js routes to avoid CORS on localhost. */

export const TATVA_USERS_API =
  process.env.TATVA_USERS_API_BASE || "https://api.tatvaops.com/users/api";

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
