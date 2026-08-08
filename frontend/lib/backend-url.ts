/**
 * QuoteSense FastAPI base URL for Next.js server routes and client code.
 * Prefer BACKEND_URL on the server (Vercel) so apply/catalog still work if
 * NEXT_PUBLIC_* is missing; never rely only on localhost in hosted deploys.
 */
export function getBackendBase(): string {
  const raw =
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    "http://127.0.0.1:8001";
  return raw.endsWith("/") ? raw.slice(0, -1) : raw;
}
