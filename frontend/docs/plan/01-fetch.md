# F1 — Fetch

Get a `MatrixV1` payload to the compare page.

**Modules**

- `lib/compare-sync.ts` — `resolveQuotesForCompare`, `startMongoCompareJob`
- `lib/compare-progress.ts` — `pollCompareProgress`
- `lib/compare-payload-cache.ts` — sessionStorage cache
- `lib/compare-lane.ts` — which entry path is active
- `app/api/compare/sync-mongodb/route.ts`, `app/api/progress/[sessionId]/route.ts`,
  `app/api/projects/[projectId]/quotes/route.ts` — BFF proxies
- `app/compare/page.tsx` — orchestration

---

## Lanes

| Lane | Trigger | Path |
| --- | --- | --- |
| `integrated` | existing `session_id` | `GET /api/get-comparison` |
| `project` | quotes picked from a Tatva project | `POST /api/compare/sync-mongodb` then poll |
| `standalone` | direct PDF upload | `POST /api/compare-quotes` then poll |

All three converge on the same `MatrixV1` payload, so nothing downstream of this
stage needs to know which lane ran.

A run accepts **exactly two quotes** (`MIN_COMPARE_QUOTES` =
`MAX_COMPARE_QUOTES` = 2 in `lib/compare-limits.ts` and `backend/main.py`).
The project hub and PDF upload must refuse a third file; the API returns an
error if more than two payloads arrive. Do not widen this in the UI without
the matching backend constant.

## Progress and the partial matrix

`GET /api/progress/{sessionId}` reports stages `queued` → `extracting` →
`comparing` → `recommending` → `done`. The backend publishes the matrix *before*
starting the recommendation, so `recommending` ticks carry a `partial` payload
with everything except `report`.

The page renders that partial immediately. This is why a slow recommendation
never blocks the table, and it is worth preserving: the recommendation has a 45s
ceiling and the table is the thing users actually need.

Poll ceiling is 25 minutes for large PDF batches. On timeout, any partial matrix
already received is kept and only the report is reported missing.

## What this stage must not do

No reshaping of the payload. Pass `MatrixV1` through as received. The temptation
is to flatten tiers here "so the components stay simple" — that would move
interpretation into the transport layer and break the contract boundary.

Two exceptions, both structural rather than semantic:

- attach `contract_version` if a legacy backend omitted it,
- strip nothing.

## Caching

`lib/compare-payload-cache.ts` stores the payload in sessionStorage so a reload
does not re-run the comparison. On a quota error it silently falls back to
re-fetching. Cache the whole `MatrixV1` including tiers — a partial cache entry
would render a bundle-less matrix that looks legitimate.

## Tests

- a payload with tiers survives the round trip unmodified,
- a legacy `tableData`-only payload passes through untouched,
- a poll timeout with a received partial keeps the matrix and flags the report.

---

## What to change if this stage breaks

**Symptom: the table renders but the bundle section is missing.**
Check whether the proxy or the cache dropped `bundleTier`. Log the raw response
before blaming the components.

**Symptom: comparison never completes.**
Backend job state, not this stage. `JOBS` in `main.py` is in-process memory, so a
backend restart or a second worker loses the job — the known cause of a
`"unknown"` progress status. Re-run the comparison.

**Symptom: stale data after a reload.**
The sessionStorage cache. Confirm the `session_id` key matches before adding
invalidation logic.

**Do not** add field defaults here. Missing-field tolerance belongs in
[00-contracts.md](00-contracts.md)'s accessors, in one place, not spread across
fetch paths.
