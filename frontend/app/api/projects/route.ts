import { NextRequest, NextResponse } from "next/server";
import { TATVA_USERS_API } from "@/lib/tatva-api";

type JsonRecord = Record<string, unknown>;

// Keys the Tatva API might nest the projects array under (covers both plain
// arrays and common paginator shapes like { data: { docs: [...] } }).
const LIST_KEYS = ["data", "projects", "projectRequests", "items", "results", "quotes", "docs"];

/** Fetch page size — large enough that most users fit on page 1. */
const PAGE_SIZE = 100;
/** Hard ceiling so a misbehaving API can never make this loop run away. */
const MAX_PAGES = 20;

type ListLocation = { items: JsonRecord[]; path: string[] };

/** Find the array of projects inside the payload, and remember where it lives
 *  so we can splice the fully-merged array back into the same shape. */
function findList(payload: unknown): ListLocation | null {
  if (Array.isArray(payload)) {
    return { items: payload as JsonRecord[], path: [] };
  }
  if (!payload || typeof payload !== "object") return null;
  const root = payload as JsonRecord;

  for (const key of LIST_KEYS) {
    const val = root[key];
    if (Array.isArray(val)) return { items: val as JsonRecord[], path: [key] };
  }
  // One level deeper, e.g. { data: { docs: [...] } }
  for (const key of LIST_KEYS) {
    const nested = root[key];
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      const nestedRecord = nested as JsonRecord;
      for (const nestedKey of LIST_KEYS) {
        const val = nestedRecord[nestedKey];
        if (Array.isArray(val)) return { items: val as JsonRecord[], path: [key, nestedKey] };
      }
    }
  }
  return null;
}

/** Return a copy of payload with the array at `path` replaced by `items`. */
function withMergedList(payload: unknown, path: string[], items: JsonRecord[]): unknown {
  if (path.length === 0) return items;
  const root: JsonRecord = { ...(payload as JsonRecord) };
  if (path.length === 1) {
    root[path[0]] = items;
    return root;
  }
  const nested: JsonRecord = { ...(root[path[0]] as JsonRecord) };
  nested[path[1]] = items;
  root[path[0]] = nested;
  return root;
}

function idsOf(items: JsonRecord[]): string[] {
  return items.map((it) => String(it._id ?? it.id ?? ""));
}

function sameIds(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((id, i) => id === b[i]);
}

/** Build a page URL that hedges across the most common pagination param names,
 *  since the exact convention the Tatva API uses isn't documented on our side. */
function pageUrl(baseUrl: string, page: number): string {
  const params = new URLSearchParams({
    page: String(page),
    pageNumber: String(page),
    limit: String(PAGE_SIZE),
    pageSize: String(PAGE_SIZE),
    per_page: String(PAGE_SIZE),
  });
  return `${baseUrl}?${params.toString()}`;
}

export async function GET(req: NextRequest) {
  try {
    const userId = req.nextUrl.searchParams.get("userId");
    const auth = req.headers.get("authorization");

    if (!userId || !auth) {
      return NextResponse.json(
        { success: false, message: "Missing user ID or authorization." },
        { status: 401 }
      );
    }

    const baseUrl = `${TATVA_USERS_API}/users/projects/user/${encodeURIComponent(userId)}/`;
    const headers = { Authorization: auth, Accept: "application/json" };

    const firstRes = await fetch(pageUrl(baseUrl, 1), { headers, cache: "no-store" });
    const firstData = await firstRes.json();

    if (!firstRes.ok) {
      return NextResponse.json(firstData, { status: firstRes.status });
    }

    const firstList = findList(firstData);
    if (!firstList) {
      // Nothing we recognize as a list — return exactly what we got before.
      return NextResponse.json(firstData, { status: firstRes.status });
    }

    let allItems = firstList.items;
    let lastIds = idsOf(allItems);
    let page = 1;

    // Keep fetching while every page so far came back completely full — that's
    // the signal there may be more. Stop as soon as a page is short (or empty,
    // or a duplicate of the previous page, which means the API isn't actually
    // honoring our pagination params and we should quit rather than loop).
    while (allItems.length === page * PAGE_SIZE && page < MAX_PAGES) {
      page += 1;
      let nextData: unknown;
      try {
        const nextRes = await fetch(pageUrl(baseUrl, page), { headers, cache: "no-store" });
        if (!nextRes.ok) break;
        nextData = await nextRes.json();
      } catch {
        break;
      }

      const nextList = findList(nextData);
      if (!nextList || nextList.items.length === 0) break;

      const nextIds = idsOf(nextList.items);
      if (sameIds(nextIds, lastIds)) break; // API ignored our page param — bail out.

      allItems = allItems.concat(nextList.items);
      lastIds = nextIds;
    }

    const merged = withMergedList(firstData, firstList.path, allItems);
    return NextResponse.json(merged, { status: firstRes.status });
  } catch (err) {
    console.error("GET /api/projects failed:", err);
    return NextResponse.json(
      { success: false, message: "Unable to fetch projects." },
      { status: 500 }
    );
  }
}
