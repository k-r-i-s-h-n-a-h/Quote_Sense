"use client";

import React from "react";
import { PdfUploadGateButton } from "./PdfUploadGateButton";
import { compareCountPhrase } from "@/lib/compare-limits";

type StandalonePdfSectionProps = {
  /** When true, show inline after empty projects (not as a distant footer block). */
  prominent?: boolean;
};

/** Standalone PDF compare — upload quotes without a TatvaOps project. */
export default function StandalonePdfSection({
  prominent = false,
}: StandalonePdfSectionProps) {
  return (
    <section
      id="pdf-compare"
      className={prominent ? "mt-6" : "mt-10 pt-8 border-t border-stone-200"}
    >
      <div
        className={`qs-card p-6 md:p-8 ${
          prominent
            ? "border-[color-mix(in_srgb,var(--accent)_30%,var(--border))] bg-[linear-gradient(180deg,var(--accent-soft),#fff)]"
            : ""
        }`}
      >
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <p className="qs-eyebrow mb-1">
              {prominent ? "Get started" : "Standalone tool"}
            </p>
            <h2 className="text-lg font-semibold text-stone-900 tracking-tight">
              {prominent ? "Compare vendor PDFs now" : "Quick PDF compare"}
            </h2>
            <p className="text-sm text-stone-500 mt-1 max-w-lg leading-relaxed">
              Upload {compareCountPhrase()} vendor quote PDFs. QuoteSense extracts line items, builds a
              comparison matrix, and generates an AI recommendation.
            </p>
          </div>
          <PdfUploadGateButton className="qs-btn qs-btn-primary shrink-0">
            Upload & compare PDFs →
          </PdfUploadGateButton>
        </div>

        <ul className="mt-5 grid sm:grid-cols-3 gap-3 text-xs text-stone-600">
          <li className="rounded-lg bg-stone-50 border border-stone-100 px-3 py-2.5">
            Select {compareCountPhrase()} vendor PDFs
          </li>
          <li className="rounded-lg bg-stone-50 border border-stone-100 px-3 py-2.5">
            AI extraction & cost matrix
          </li>
          <li className="rounded-lg bg-stone-50 border border-stone-100 px-3 py-2.5">
            Chart, market context & report
          </li>
        </ul>
      </div>
    </section>
  );
}
