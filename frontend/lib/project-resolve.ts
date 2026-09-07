/**
 * Resolve Tatva project public codes (e.g. 0F44A3) ↔ Mongo _id for APIs.
 */

import { unwrapApiList } from "./project-mappers";

type RawRecord = Record<string, unknown>;

const MONGO_ID_RE = /^[a-f0-9]{24}$/i;

export type ResolvedProjectRef = {
  mongoId: string;
  publicRef: string;
};

export function isMongoObjectId(ref: string): boolean {
  return MONGO_ID_RE.test(ref.trim());
}

function asRecord(value: unknown): RawRecord | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as RawRecord)
    : null;
}

function asString(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return fallback;
}

/** Public hex code shown in PM (projectId.projectId). */
export function extractProjectCode(raw: RawRecord): string {
  const projectCodeField = raw.projectId;
  return (
    (typeof projectCodeField === "string" && projectCodeField) ||
    asString(asRecord(projectCodeField)?.projectId) ||
    asString(raw.code) ||
    asString(raw._id || raw.id).slice(-6).toUpperCase()
  );
}

export function projectMatchesRef(raw: RawRecord, ref: string): boolean {
  const needle = ref.trim();
  if (!needle) return false;
  const mongoId = asString(raw._id || raw.id);
  if (mongoId === needle) return true;
  return extractProjectCode(raw).toUpperCase() === needle.toUpperCase();
}

export function findProjectRawByRef(
  projects: RawRecord[],
  ref: string
): RawRecord | null {
  return projects.find((p) => projectMatchesRef(p, ref)) ?? null;
}

export function resolveProjectFromRaw(
  raw: RawRecord,
  fallbackRef?: string
): ResolvedProjectRef {
  const mongoId = asString(raw._id || raw.id);
  const publicRef = extractProjectCode(raw) || fallbackRef || mongoId;
  return { mongoId, publicRef };
}

/** Client: resolve short code or mongo id using the user's project list. */
export async function resolveProjectRef(
  projectRef: string,
  userId: string | null | undefined,
  authHeaders: HeadersInit = {}
): Promise<ResolvedProjectRef | null> {
  const ref = projectRef.trim();
  if (!ref) return null;

  if (!userId) {
    if (isMongoObjectId(ref)) {
      return { mongoId: ref, publicRef: ref.slice(-6).toUpperCase() };
    }
    return null;
  }

  const listRes = await fetch(
    `/api/projects?userId=${encodeURIComponent(userId)}`,
    { headers: authHeaders }
  );
  if (!listRes.ok) {
    if (isMongoObjectId(ref)) {
      return { mongoId: ref, publicRef: ref.slice(-6).toUpperCase() };
    }
    return null;
  }

  let data: unknown;
  try {
    data = await listRes.json();
  } catch {
    return null;
  }

  const projects = unwrapApiList(data) as RawRecord[];
  const match = findProjectRawByRef(projects, ref);
  if (match) return resolveProjectFromRaw(match, ref);

  if (isMongoObjectId(ref)) {
    return { mongoId: ref, publicRef: ref.slice(-6).toUpperCase() };
  }

  return null;
}

const SHORT_PROJECT_CODE_RE = /^[0-9A-Fa-f]{5,8}$/;

/** Project ref on a PM Compare redirect (query or `/project/:code`). */
export function extractPmProjectRef(
  params: URLSearchParams,
  pathname = ""
): string {
  for (const key of [
    "projectId",
    "project_id",
    "project",
    "projectCode",
    "project_code",
  ] as const) {
    const value = (params.get(key) || "").trim();
    if (value) return value;
  }

  const id = (params.get("id") || "").trim();
  if (id && (isMongoObjectId(id) || SHORT_PROJECT_CODE_RE.test(id))) {
    return id;
  }

  const pathMatch = pathname.match(/^\/project\/([^/?#]+)/);
  if (pathMatch?.[1]) {
    try {
      return decodeURIComponent(pathMatch[1]).trim();
    } catch {
      return pathMatch[1].trim();
    }
  }

  return "";
}

/** Build PM SSO redirect — that project hub, a compare session, or the list. */
export function buildPmRedirectPath(
  params: URLSearchParams,
  pathname = ""
): string {
  const sessionId = params.get("session_id");

  if (sessionId) {
    return `/compare?session_id=${encodeURIComponent(sessionId)}`;
  }

  const projectRef = extractPmProjectRef(params, pathname);
  if (projectRef) {
    return `/project/${encodeURIComponent(projectRef)}`;
  }

  return "/";
}
