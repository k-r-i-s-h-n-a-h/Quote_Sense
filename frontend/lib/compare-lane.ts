/** Detect how the user entered the compare experience. */

import { STANDALONE_PDF_UPLOAD_ENABLED } from "./feature-flags";

export type CompareLane = "integrated" | "project" | "standalone";

export function getCompareLane(params: {
  sessionIdFromUrl?: string | null;
  sourceParam?: string | null;
  projectId?: string | null;
  selectedQuoteIds?: string[];
}): CompareLane {
  const {
    sessionIdFromUrl,
    sourceParam,
    projectId,
    selectedQuoteIds = [],
  } = params;

  // Project compare keeps this lane even after session_id is added to the URL.
  if (projectId && selectedQuoteIds.length >= 2) {
    return "project";
  }

  if (sessionIdFromUrl || sourceParam === "integrated") {
    return "integrated";
  }
  if (selectedQuoteIds.length >= 2) {
    return "project";
  }
  return "standalone";
}

export function showPdfUpload(lane: CompareLane): boolean {
  // Temporary recovery lock: close the independent PDF door without
  // changing project / integrated compare flows.
  return lane === "standalone" && STANDALONE_PDF_UPLOAD_ENABLED;
}

export function showProjectNav(lane: CompareLane): boolean {
  return lane === "project" || lane === "standalone";
}
