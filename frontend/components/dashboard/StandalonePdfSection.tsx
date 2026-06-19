"use client";

import React from "react";
import Link from "next/link";

/** Standalone PDF compare — links to full comparator; kept below project tiles on home. */
export default function StandalonePdfSection() {
  return (
    <section id="pdf-compare" className="max-w-5xl mx-auto px-4 md:px-6 pb-16">
      <div className="border-t border-slate-200 pt-10">
        <div className="qs-card p-6 md:p-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1">
                Standalone tool
              </p>
              <h2 className="text-lg font-bold text-slate-900">Quick PDF compare</h2>
              <p className="text-sm text-slate-500 mt-1 max-w-lg">
                Upload vendor quote PDFs directly without selecting a project. AI extracts
                line items and builds a side-by-side comparison matrix.
              </p>
            </div>
            <Link
              href="/compare"
              className="shrink-0 inline-flex items-center justify-center px-6 py-3 rounded-xl text-sm font-semibold text-white bg-[#c04a00] hover:bg-[#a84000] transition-colors shadow-sm"
            >
              Upload & compare PDFs →
            </Link>
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
      </div>
    </section>
  );
}
