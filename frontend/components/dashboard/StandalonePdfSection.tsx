"use client";

import React from "react";
import { PdfUploadGateButton } from "./PdfUploadGateButton";

type StandalonePdfSectionProps = {
  /** When true, show inline after empty projects (not as a distant footer block). */
  prominent?: boolean;
};

/** Standalone PDF compare — upload quotes without a TatvaOps project. */
export default function StandalonePdfSection({ prominent = false }: StandalonePdfSectionProps) {
  return (
    <section
      id="pdf-compare"
      className={prominent ? "mt-6" : "mt-10 pt-8 border-t border-slate-200"}
    >
      <div
        className={`qs-card p-6 md:p-8 ${
          prominent ? "border-[#c04a00]/25 bg-gradient-to-br from-orange-50/80 to-white" : ""
        }`}
      >
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <p
              className={`text-[10px] font-semibold uppercase tracking-wider mb-1 ${
                prominent ? "text-[#c04a00]" : "text-slate-400"
              }`}
            >
              {prominent ? "Get started" : "Standalone tool"}
            </p>
            <h2 className="text-lg font-bold text-slate-900">
              {prominent ? "Compare vendor PDFs now" : "Quick PDF compare"}
            </h2>
            <p className="text-sm text-slate-500 mt-1 max-w-lg">
              Upload vendor quote PDFs directly without selecting a project. AI extracts
              line items and builds a side-by-side comparison matrix.
            </p>
          </div>
          <PdfUploadGateButton className="shrink-0 inline-flex items-center justify-center px-6 py-3 rounded-xl text-sm font-semibold text-white bg-[#c04a00] hover:bg-[#a84000] transition-colors shadow-sm">
            Upload & compare PDFs →
          </PdfUploadGateButton>
        </div>

        <ul className="mt-5 grid sm:grid-cols-3 gap-3 text-xs text-slate-500">
          <li className="flex items-center gap-2 bg-slate-50 rounded-lg px-3 py-2">
            <span className="text-base">📄</span> Select 2+ vendor PDFs
          </li>
          <li className="flex items-center gap-2 bg-slate-50 rounded-lg px-3 py-2">
            <span className="text-base">🤖</span> AI extraction & matrix
          </li>
          <li className="flex items-center gap-2 bg-slate-50 rounded-lg px-3 py-2">
            <span className="text-base">📊</span> Chart, report & chat
          </li>
        </ul>
      </div>
    </section>
  );
}
