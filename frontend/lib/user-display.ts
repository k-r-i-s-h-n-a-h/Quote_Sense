import type { TatvaUser } from "./tatva-api";

/** Prefer saved name; never fall back to phone number in UI. */
export function getUserDisplayName(
  user: TatvaUser | null | undefined,
  fallback = "there"
): string {
  const name = user?.name?.trim() || user?.fullName?.trim();
  return name || fallback;
}

export function userNeedsName(user: TatvaUser | null | undefined): boolean {
  if (!user) return false;
  return !user.name?.trim() && !user.fullName?.trim();
}

/** Single letter for avatar chip when name may be missing. */
export function getUserInitial(user: TatvaUser | null | undefined): string {
  const name = getUserDisplayName(user, "");
  if (name) return name.charAt(0).toUpperCase();
  return "?";
}
