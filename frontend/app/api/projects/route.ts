import { NextRequest, NextResponse } from "next/server";
import { TATVA_USERS_API } from "@/lib/tatva-api";
import {
  dedupeById,
  findList,
  idsOf,
  readTotalHint,
  sameIds,
  shouldFetchNextPage,
  type JsonRecord,
} from "@/lib/projects-pagination";

/** Preferred page size when the API honors limit/pageSize. */
const PAGE_SIZE = 100;
/** Hard ceiling so a misbehaving API can never make this loop run away. */
const MAX_PAGES = 20;

/** Return a copy of payload with the array at `path` replaced by `items`. */
function withMergedList(
  payload: unknown,
  path: string[],
  items: JsonRecord[]
): unknown {
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

    const firstRes = await fetch(pageUrl(baseUrl, 1), {
      headers,
      cache: "no-store",
    });
    const firstData = await firstRes.json();

    if (!firstRes.ok) {
      return NextResponse.json(firstData, { status: firstRes.status });
    }

    const firstList = findList(firstData);
    if (!firstList) {
      return NextResponse.json(firstData, { status: firstRes.status });
    }

    const totalHint = readTotalHint(firstData);
    let allItems = dedupeById(firstList.items);
    let lastIds = idsOf(firstList.items);
    let lastPageCount = firstList.items.length;
    let page = 1;
    let stoppedReason = "first-page-only";

    // Keep requesting the next page until the API says we're done.
    // Do NOT require page1.length === PAGE_SIZE — a short first page (e.g. 81)
    // can still have more pages (→ 121). That bug caused local vs test gaps.
    while (
      shouldFetchNextPage({
        page,
        maxPages: MAX_PAGES,
        lastPageCount,
        mergedCount: allItems.length,
        totalHint,
      })
    ) {
      page += 1;
      let nextData: unknown;
      try {
        const nextRes = await fetch(pageUrl(baseUrl, page), {
          headers,
          cache: "no-store",
        });
        if (!nextRes.ok) {
          stoppedReason = `page-${page}-http-${nextRes.status}`;
          break;
        }
        nextData = await nextRes.json();
      } catch {
        stoppedReason = `page-${page}-fetch-error`;
        break;
      }

      const nextList = findList(nextData);
      if (!nextList || nextList.items.length === 0) {
        stoppedReason = "empty-next-page";
        break;
      }

      const nextIds = idsOf(nextList.items);
      if (sameIds(nextIds, lastIds)) {
        stoppedReason = "duplicate-page";
        break;
      }

      allItems = dedupeById(allItems.concat(nextList.items));
      lastIds = nextIds;
      lastPageCount = nextList.items.length;
      stoppedReason = `merged-through-page-${page}`;
    }

    if (
      totalHint != null &&
      allItems.length >= totalHint &&
      stoppedReason === "first-page-only"
    ) {
      stoppedReason = "reached-total-hint";
    }

    const merged = withMergedList(firstData, firstList.path, allItems);
    const resHeaders = new Headers();
    resHeaders.set("Cache-Control", "no-store");
    resHeaders.set("X-Projects-Count", String(allItems.length));
    resHeaders.set("X-Projects-Pages-Fetched", String(page));
    resHeaders.set("X-Projects-Stop", stoppedReason);
    if (totalHint != null) {
      resHeaders.set("X-Projects-Total-Hint", String(totalHint));
    }

    return NextResponse.json(merged, {
      status: firstRes.status,
      headers: resHeaders,
    });
  } catch (err) {
    console.error("GET /api/projects failed:", err);
    return NextResponse.json(
      { success: false, message: "Unable to fetch projects." },
      { status: 500 }
    );
  }
}
