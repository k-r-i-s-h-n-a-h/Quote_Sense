"use client";

import React from "react";
import Link from "next/link";
import {
  formatInr,
  getQuoteSelectionSummary,
  type ProjectData,
} from "@/lib/project-types";
import { readCachedProjectQuotePayloads } from "@/lib/compare-payload-cache";
import type { CompareLane } from "@/lib/compare-lane";

type CompareSelectionBannerProps = {
  quoteIds: string[];
  projectId?: string | null;
};

function projectFromCache(
  projectId: string,
  quoteIds: string[]
): ProjectData | null {
  const entry = readCachedProjectQuotePayloads(projectId);
  if (!entry?.meta) return null;

  const vendorsMap = new Map<
    string,
    { id: string; companyName: string; contactName: string; email: string; quotes: ProjectData["vendors"][0]["quotes"] }
  >();

  for (const raw of entry.quotes) {
    const id = String(raw._id || raw.id || "");
    if (!quoteIds.includes(id)) continue;

    const vendorDetail = (raw.vendorDetail || {}) as Record<string, unknown>;
    const vendorId = String(raw.vendorId || vendorDetail._id || "vendor");
    const pricing = Array.isArray(raw.pricingSummary) ? raw.pricingSummary : [];
    let amount = 0;
    for (const row of pricing) {
      const rec = row as Record<string, unknown>;
      if (String(rec.label || "").toLowerCase().includes("grand total")) {
        amount = Number(rec.value) || 0;
      }
    }

    const quote = {
      id,
      quoteNumber: String(raw.quoteNumber || "—"),
      label: String(raw.draftName || raw.quoteNumber || "Quote"),
      amount,
      date: "—",
      status: "submitted" as const,
      lineItems: 0,
    };

    const existing = vendorsMap.get(vendorId);
    if (existing) {
      existing.quotes.push(quote);
    } else {
      vendorsMap.set(vendorId, {
        id: vendorId,
        companyName: String(vendorDetail.companyName || "Vendor"),
        contactName: String(vendorDetail.fullName || vendorDetail.vendorName || ""),
        email: String(vendorDetail.email || vendorDetail.companyEmail || ""),
        quotes: [quote],
      });
    }
  }

  const vendors = Array.from(vendorsMap.values());
  if (vendors.length === 0) return null;

  return {
    id: projectId,
    title: entry.meta.title,
    projectCode: entry.meta.projectCode,
    clientName: "—",
    status: "quotes_received",
    brief: "",
    service: { id: "general", name: "Project", icon: "📋" },
    vendors,
  };
}

export function CompareSelectionBanner({
  quoteIds,
  projectId,
}: CompareSelectionBannerProps) {
  const project =
    projectId && quoteIds.length > 0
      ? projectFromCache(projectId, quoteIds)
      : null;

  const summary = project ? getQuoteSelectionSummary(project, quoteIds) : [];

  if (summary.length === 0) return null;

  return (
    <div className="qs-card p-5 border-[#c04a00]/20 bg-orange-50/30">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#c04a00]">
            Selected for comparison
          </p>
          <h2 className="text-lg font-bold text-slate-900 mt-1">
            {summary.length} quotes · {new Set(summary.map((s) => s.vendor.id)).size} vendors
          </h2>
          {project && (
            <p className="text-xs text-slate-500 mt-1">
              Project: {project.title} ({project.projectCode})
            </p>
          )}
        </div>
        <Link
          href={projectId ? `/project/${projectId}` : "/"}
          className="shrink-0 text-xs font-medium text-slate-600 hover:text-[#c04a00] px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:border-[#c04a00]/30 transition-colors"
        >
          ← Back to project
        </Link>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {summary.map(({ vendor, quote }) => (
          <div
            key={quote.id}
            className="bg-white rounded-lg border border-slate-100 px-3 py-2.5"
          >
            <p className="text-[11px] text-slate-400 truncate">{vendor.companyName}</p>
            <p className="text-sm font-semibold text-slate-900">#{quote.quoteNumber}</p>
            <p className="text-xs text-slate-500">{quote.label}</p>
            <p className="text-sm font-bold text-[#c04a00] mt-1 tabular-nums">
              {formatInr(quote.amount)}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ComparePageNav({
  projectId,
  lane = "standalone",
}: {
  projectId?: string | null;
  lane?: CompareLane;
}) {
  if (lane === "integrated") {
    return (
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm text-slate-600">
          Synced comparison from <span className="font-medium text-slate-800">TatvaOps</span>
        </p>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-[#c04a00]">
          Integrated lane
        </span>
      </div>
    );
  }

  const backHref = projectId ? `/project/${projectId}` : "/";
  const backLabel = projectId ? "Back to project" : "All projects";

  return (
    <div className="flex items-center justify-between mb-6">
      <Link
        href={backHref}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-[#c04a00] transition-colors"
      >
        <span aria-hidden>←</span> {backLabel}
      </Link>
      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        Quote comparison
      </span>
    </div>
  );
}

export function IntegratedLoadingBanner({ message }: { message: string }) {
  return (
    <div className="qs-card p-6 border-[#c04a00]/15 bg-orange-50/40">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-[#c04a00] mb-1">
        TatvaOps · QuoteSense
      </p>
      <h1 className="text-lg font-bold text-slate-900">Building your comparison</h1>
      <p className="text-sm text-slate-500 mt-1">{message}</p>
    </div>
  );
}
