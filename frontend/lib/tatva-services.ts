/** TatvaOps service links — URLs from env, SSO appended at click time. */

import { getAuthToken, getAuthUserId } from "./auth";
import { TATVA_SERVICES, type TatvaService } from "./project-types";

export type TatvaServiceNav = TatvaService & { href: string };

/**
 * Next.js only inlines NEXT_PUBLIC_* when accessed statically (not process.env[key]).
 * Keep this map in sync with TATVA_SERVICES envKey fields.
 */
function serviceHrefById(id: string): string {
  switch (id) {
    case "interior":
      return process.env.NEXT_PUBLIC_SERVICE_INTERIORS?.trim() || "";
    case "construction":
      return process.env.NEXT_PUBLIC_SERVICE_CONSTRUCTION?.trim() || "";
    case "solar":
      return process.env.NEXT_PUBLIC_SERVICE_SOLAR?.trim() || "";
    case "painting":
      return process.env.NEXT_PUBLIC_SERVICE_PAINTING?.trim() || "";
    case "plumbing":
      return process.env.NEXT_PUBLIC_SERVICE_PLUMBING?.trim() || "";
    case "electrical":
      return process.env.NEXT_PUBLIC_SERVICE_ELECTRICAL?.trim() || "";
    case "event_management":
      return process.env.NEXT_PUBLIC_SERVICE_EVENT_MANAGEMENT?.trim() || "";
    case "property_development":
      return process.env.NEXT_PUBLIC_SERVICE_PROPERTY_DEVELOPMENT?.trim() || "";
    case "home_automation":
      return process.env.NEXT_PUBLIC_SERVICE_HOME_AUTOMATION?.trim() || "";
    case "farm_infrastructure":
      return process.env.NEXT_PUBLIC_SERVICE_FARM_INFRASTRUCTURE?.trim() || "";
    case "irrigation_automation":
      return process.env.NEXT_PUBLIC_SERVICE_IRRIGATION_AUTOMATION?.trim() || "";
    default:
      return "";
  }
}

/** All Tatva services for ProjectHub — href from env when configured. */
export function getTatvaServicesForNav(): TatvaServiceNav[] {
  return TATVA_SERVICES.map((svc) => ({
    id: svc.id,
    name: svc.name,
    icon: svc.icon,
    href: serviceHrefById(svc.id),
  }));
}

/** Outbound SSO link to withtatva.ai service pages. */
export function buildTatvaServiceUrl(baseHref: string): string {
  if (!baseHref) return "";
  try {
    const url = new URL(baseHref);
    const token = getAuthToken();
    const userId = getAuthUserId(null);
    if (token) url.searchParams.set("jwt_auth", token);
    if (userId) url.searchParams.set("user_id", userId);
    return url.toString();
  } catch {
    return baseHref;
  }
}
