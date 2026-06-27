/**
 * Poll /api/progress/{session_id} with adaptive intervals (not hundreds of rapid fetches).
 */

export type CompareProgressPayload = {
  status?: string;
  stage?: string;
  message?: string;
  processed?: number;
  total?: number;
  partial?: Record<string, unknown>;
  result?: Record<string, unknown>;
  error?: string;
};

export type PollCompareProgressOptions = {
  sessionId: string;
  backendUrl: string;
  /** Return false to stop polling (e.g. component unmounted). */
  shouldContinue: () => boolean;
  /** Client already rendered the partial matrix. */
  hasPartialApplied: () => boolean;
  onTick: (data: CompareProgressPayload) => void;
};

export type PollCompareProgressResult =
  | { outcome: "done"; result: Record<string, unknown> }
  | { outcome: "error"; message: string }
  | { outcome: "timeout"; last?: CompareProgressPayload }
  | { outcome: "cancelled" }
  | { outcome: "unknown"; message: string };

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** PDF + Gemini extraction can exceed 10 min for 2–3 large quotes. */
const MAX_MS = 25 * 60 * 1000;

function pollDelayMs(
  polls: number,
  hasPartial: boolean,
  unchangedStreak: number
): number {
  if (hasPartial) return 3500;
  // Extracting: start at 2s, back off to 5s if status unchanged
  const base = polls < 3 ? 2000 : 3000;
  const backoff = Math.min(unchangedStreak * 500, 2000);
  return Math.min(base + backoff, 5000);
}

export async function pollCompareProgress(
  options: PollCompareProgressOptions
): Promise<PollCompareProgressResult> {
  const { sessionId, backendUrl, shouldContinue, hasPartialApplied, onTick } =
    options;

  const startedAt = Date.now();
  let polls = 0;
  let unchangedStreak = 0;
  let lastSignature = "";
  let lastPayload: CompareProgressPayload | undefined;

  while (Date.now() - startedAt < MAX_MS) {
    if (!shouldContinue()) return { outcome: "cancelled" };

    let data: CompareProgressPayload;
    try {
      const hasPartialParam = hasPartialApplied() ? "?has_partial=true" : "";
      const res = await fetch(
        `${backendUrl}/api/progress/${encodeURIComponent(sessionId)}${hasPartialParam}`
      );
      data = (await res.json()) as CompareProgressPayload;
    } catch {
      await sleep(2000);
      polls += 1;
      continue;
    }

    lastPayload = data;
    onTick(data);

    const signature = `${data.status}|${data.stage}|${data.processed}|${data.message}`;
    if (signature === lastSignature) {
      unchangedStreak += 1;
    } else {
      unchangedStreak = 0;
      lastSignature = signature;
    }

    if (data.status === "done" && data.result) {
      return { outcome: "done", result: data.result };
    }
    if (data.status === "error") {
      return {
        outcome: "error",
        message: data.error || data.message || "Comparison failed on the backend.",
      };
    }
    if (data.status === "unknown") {
      return {
        outcome: "unknown",
        message:
          data.message ||
          "Job not found on the backend. It may have expired — start a new comparison.",
      };
    }

    polls += 1;
    await sleep(pollDelayMs(polls, hasPartialApplied(), unchangedStreak));
  }

  // One last check before giving up (backend may have finished between polls).
  try {
    const hasPartialParam = hasPartialApplied() ? "?has_partial=true" : "";
    const res = await fetch(
      `${backendUrl}/api/progress/${encodeURIComponent(sessionId)}${hasPartialParam}`
    );
    const data = (await res.json()) as CompareProgressPayload;
    if (data.status === "done" && data.result) {
      return { outcome: "done", result: data.result };
    }
    if (data.status === "error") {
      return {
        outcome: "error",
        message: data.error || data.message || "Comparison failed.",
      };
    }
    lastPayload = data;
  } catch {
    /* use lastPayload */
  }

  return { outcome: "timeout", last: lastPayload };
}
