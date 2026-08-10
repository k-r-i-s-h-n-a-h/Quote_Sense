import {
  buildProjectWithQuotes,
  mapApiProjectsList,
  unwrapApiList,
} from "./project-mappers";
import type { ProjectData, ProjectSummary } from "./project-types";
import { getAuthToken, getAuthUserId } from "./auth";
import { cacheProjectQuotePayloads } from "./compare-payload-cache";
import { applyFinalizedQuotesInBackground } from "./market-rate-apply";
import { annotateQuotesPayloadForUi } from "./quote-ui-status";
import {
  findProjectRawByRef,
  isMongoObjectId,
  resolveProjectFromRaw,
  resolveProjectRef,
  type ResolvedProjectRef,
} from "./project-resolve";

export { getAuthUserId, resolveProjectRef };
export type { ResolvedProjectRef };

function authHeaders(): HeadersInit {
  const token = getAuthToken();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

async function parseJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return { success: false, message: "Invalid JSON from API." };
  }
}

export type FetchProjectsResult =
  | { ok: true; projects: ProjectSummary[] }
  | { ok: false; message: string; status: number };

export async function fetchUserProjects(
  userId: string
): Promise<FetchProjectsResult> {
  const res = await fetch(`/api/projects?userId=${encodeURIComponent(userId)}`, {
    headers: authHeaders(),
  });
  const data = await parseJson(res);

  if (!res.ok) {
    const msg =
      (data as { message?: string })?.message ||
      `Failed to load projects (${res.status})`;
    return { ok: false, message: msg, status: res.status };
  }

  const projects = mapApiProjectsList(data);
  return { ok: true, projects };
}

export type FetchProjectDetailResult =
  | { ok: true; project: ProjectData }
  | { ok: false; message: string; status: number };

export async function fetchProjectWithQuotes(
  projectRef: string,
  userId?: string | null
): Promise<FetchProjectDetailResult> {
  const headers = authHeaders();
  const resolved = await resolveProjectRef(projectRef, userId, headers);
  if (!resolved) {
    return {
      ok: false,
      message: "Project not found. Check the project code or sign in again.",
      status: 404,
    };
  }

  const { mongoId, publicRef } = resolved;
  let projectRaw: Record<string, unknown> | null = null;

  if (userId) {
    const listRes = await fetch(
      `/api/projects?userId=${encodeURIComponent(userId)}`,
      { headers }
    );
    if (listRes.ok) {
      const listData = await parseJson(listRes);
      projectRaw =
        findProjectRawByRef(unwrapApiList(listData) as Record<string, unknown>[], projectRef) ??
        null;
    }
  }

  const quotesRes = await fetch(
    `/api/projects/${encodeURIComponent(mongoId)}/quotes`,
    { headers }
  );
  const quotesData = await parseJson(quotesRes);

  if (!quotesRes.ok) {
    const msg =
      (quotesData as { message?: string })?.message ||
      `Failed to load quotes (${quotesRes.status})`;
    return { ok: false, message: msg, status: quotesRes.status };
  }

  // Raw Tatva shape (keep isFinalizeQuote for MA apply).
  const rawQuotes = unwrapApiList(quotesData);
  // UI path: normalize finalize flag; keep Tatva status for dual badges.
  const uiQuotesPayload = annotateQuotesPayloadForUi(quotesData);
  const project = buildProjectWithQuotes(projectRaw, mongoId, uiQuotesPayload);
  project.id = mongoId;
  project.projectCode = publicRef;

  cacheProjectQuotePayloads(publicRef, rawQuotes, {
    title: project.title,
    projectCode: publicRef,
    mongoId,
  });

  // User-selected finalized quote(s) only → market_moving_averages (not compare).
  applyFinalizedQuotesInBackground(rawQuotes);

  return { ok: true, project };
}

/** Resolve public code in compare URLs to mongo id for Tatva API calls. */
export async function resolveProjectRefForCompare(
  projectRef: string,
  userId?: string | null
): Promise<ResolvedProjectRef | null> {
  return resolveProjectRef(projectRef, userId, authHeaders());
}

export function projectHref(project: { projectCode: string; id: string }): string {
  return `/project/${encodeURIComponent(project.projectCode || project.id)}`;
}

export function isPublicProjectRef(ref: string): boolean {
  return !isMongoObjectId(ref);
}
