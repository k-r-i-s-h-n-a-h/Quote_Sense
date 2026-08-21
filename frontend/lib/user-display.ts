import type { TatvaUser } from "./tatva-api";

function asTrimmed(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

/**
 * Tatva / PM profiles store the display name under several keys.
 * Prefer explicit name fields; never fall back to phone number in UI.
 */
export function resolveProfileName(
  user: TatvaUser | Record<string, unknown> | null | undefined
): string {
  if (!user) return "";
  const u = user as Record<string, unknown>;
  const first =
    asTrimmed(u.firstName) || asTrimmed(u.first_name) || asTrimmed(u.given_name);
  const last =
    asTrimmed(u.lastName) || asTrimmed(u.last_name) || asTrimmed(u.family_name);
  const combined = [first, last].filter(Boolean).join(" ");
  return (
    asTrimmed(u.name) ||
    asTrimmed(u.fullName) ||
    asTrimmed(u.username) ||
    combined
  );
}

/** Copy resolved PM/Tatva name onto name + fullName for the rest of the app. */
export function withResolvedName(user: TatvaUser): TatvaUser {
  const resolved = resolveProfileName(user);
  if (!resolved) return user;
  return {
    ...user,
    name: asTrimmed(user.name) || resolved,
    fullName: asTrimmed(user.fullName) || resolved,
  };
}

export function getUserDisplayName(
  user: TatvaUser | null | undefined,
  fallback = "there"
): string {
  return resolveProfileName(user) || fallback;
}

export function userNeedsName(user: TatvaUser | null | undefined): boolean {
  if (!user) return false;
  return !resolveProfileName(user);
}

/** Single letter for avatar chip when name may be missing. */
export function getUserInitial(user: TatvaUser | null | undefined): string {
  const name = getUserDisplayName(user, "");
  if (name) return name.charAt(0).toUpperCase();
  return "?";
}
