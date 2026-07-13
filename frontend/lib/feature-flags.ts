/**
 * Temporary feature flags for internal evaluation / recovery.
 *
 * Standalone PDF upload is OFF unless explicitly enabled.
 * Only NEXT_PUBLIC_STANDALONE_PDF_ENABLED=true turns it back on.
 */
export const STANDALONE_PDF_UPLOAD_ENABLED =
  process.env.NEXT_PUBLIC_STANDALONE_PDF_ENABLED === "true";

export const STANDALONE_PDF_RECOVERY_MESSAGE =
  "PDF upload is temporarily unavailable while we recover this feature. We'll bring it back in the next update. You can still compare quotes from your TatvaOps projects.";
