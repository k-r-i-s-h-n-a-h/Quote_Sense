import type jsPDF from "jspdf";

/** Custom family registered with jsPDF when Noto Sans loads. */
export const PDF_FONT_FAMILY = "NotoSans";

const LOCAL_REGULAR = "/fonts/NotoSans-Regular.ttf";
const LOCAL_BOLD = "/fonts/NotoSans-Bold.ttf";
/** OFL Noto Sans — includes U+20B9 so amounts can print as ₹, not "Rs." */
const CDN_REGULAR =
  "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-Regular.ttf";
const CDN_BOLD =
  "https://cdn.jsdelivr.net/gh/googlefonts/noto-fonts@main/hinted/ttf/NotoSans/NotoSans-Bold.ttf";

let cache: { regular: string; bold: string } | null = null;

function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const chunk = 0x8000;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function isTtf(buf: ArrayBuffer): boolean {
  const u = new Uint8Array(buf);
  if (u.length < 4) return false;
  if (u[0] === 0 && u[1] === 1 && u[2] === 0 && u[3] === 0) return true;
  const tag = String.fromCharCode(u[0], u[1], u[2], u[3]);
  return tag === "true" || tag === "OTTO";
}

async function fetchFont(urls: string[]): Promise<string> {
  let lastError: unknown;
  for (const url of urls) {
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      const buf = await res.arrayBuffer();
      if (!isTtf(buf)) continue;
      return toBase64(buf);
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError || new Error("font fetch failed");
}

/**
 * Embed Noto Sans so the export can draw ₹ and full vendor names.
 * Returns false when both the local files and the CDN are unavailable;
 * the caller then falls back to Helvetica (ASCII "INR").
 */
export async function registerPdfUnicodeFont(doc: jsPDF): Promise<boolean> {
  if (typeof window === "undefined") return false;
  try {
    if (!cache) {
      const [regular, bold] = await Promise.all([
        fetchFont([LOCAL_REGULAR, CDN_REGULAR]),
        fetchFont([LOCAL_BOLD, CDN_BOLD]),
      ]);
      cache = { regular, bold };
    }
    doc.addFileToVFS("NotoSans-Regular.ttf", cache.regular);
    doc.addFont("NotoSans-Regular.ttf", PDF_FONT_FAMILY, "normal");
    doc.addFileToVFS("NotoSans-Bold.ttf", cache.bold);
    doc.addFont("NotoSans-Bold.ttf", PDF_FONT_FAMILY, "bold");
    return true;
  } catch {
    return false;
  }
}
