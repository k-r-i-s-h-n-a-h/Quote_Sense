import {
  buildProjectWithQuotes,
  mapApiProjectsList,
  unwrapApiList,
} from "./project-mappers";
import type { ProjectData, ProjectSummary } from "./project-types";
import { getAuthToken, getAuthUserId } from "./auth";
import { cacheProjectQuotePayloads } from "./compare-payload-cache";

export { getAuthUserId };

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
  projectId: string,
  userId?: string | null
): Promise<FetchProjectDetailResult> {
  let projectRaw: Record<string, unknown> | null = null;

  if (userId) {
    const listRes = await fetch(
      `/api/projects?userId=${encodeURIComponent(userId)}`,
      { headers: authHeaders() }
    );
    if (listRes.ok) {
      const listData = await parseJson(listRes);
      projectRaw =
        unwrapApiList(listData).find(
          (p) => String(p._id || p.id) === projectId
        ) ?? null;
    }
  }

  const quotesRes = await fetch(
    `/api/projects/${encodeURIComponent(projectId)}/quotes`,
    { headers: authHeaders() }
  );
  const quotesData = await parseJson(quotesRes);

  if (!quotesRes.ok) {
    const msg =
      (quotesData as { message?: string })?.message ||
      `Failed to load quotes (${quotesRes.status})`;
    return { ok: false, message: msg, status: quotesRes.status };
  }

  const rawQuotes = unwrapApiList(quotesData);
  const project = buildProjectWithQuotes(projectRaw, projectId, quotesData);
  cacheProjectQuotePayloads(projectId, rawQuotes, {
    title: project.title,
    projectCode: project.projectCode,
  });
  return { ok: true, project };
}
