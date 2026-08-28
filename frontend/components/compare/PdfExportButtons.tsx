"use client";

import type { PdfDetailLevel } from "@/lib/download-comparison-pdf";

export type { PdfDetailLevel };

type Props = {
  onExport: (detail: PdfDetailLevel) => void | Promise<void>;
  disabled?: boolean;
  className?: string;
};

export default function PdfExportButtons({
  onExport,
  disabled,
  className = "",
}: Props) {
  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onExport("spaces")}
        className="qs-btn qs-btn-secondary shrink-0"
        title="Portrait A4 with space totals only — packages and recaps still included"
      >
        <DownloadIcon />
        PDF: spaces
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onExport("full")}
        className="qs-btn qs-btn-secondary shrink-0"
        title="Portrait A4 with every work line under each space"
      >
        <DownloadIcon />
        PDF: detailed
      </button>
    </div>
  );
}

function DownloadIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className="w-4 h-4"
      aria-hidden
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}
