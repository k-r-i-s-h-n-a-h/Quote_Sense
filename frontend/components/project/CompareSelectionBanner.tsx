"use client";

import React from "react";
import Link from "next/link";
import {
  formatInr,
  getQuoteSelectionSummary,
  type ProjectData,
} from "@/lib/project-types";
import { readCachedProjectQuotePayloads } from "@/lib/compare-payload-cache";

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
    {
      id: string;
      companyName: string;
      contactName: string;
      email: string;
      quotes: ProjectData["vendors"][0]["quotes"];
    }
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
        contactName: String(
          vendorDetail.fullName || vendorDetail.vendorName || ""
        ),
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

  const backRef = project?.projectCode || projectId;
  const backHref = backRef ? `/project/${encodeURIComponent(backRef)}` : "/";

  return (
    <div className="qs-card p-5 border-[color-mix(in_srgb,var(--accent)_22%,var(--border))] bg-[var(--accent-soft)]/40">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <p className="qs-eyebrow">Selected for comparison</p>
          <h2 className="text-lg font-semibold text-stone-900 mt-1 tracking-tight">
            {summary.length} quotes ·{" "}
            {new Set(summary.map((s) => s.vendor.id)).size} vendors
          </h2>
          {project && (
            <p className="text-xs text-stone-500 mt-1">
              {project.title} ({project.projectCode})
            </p>
          )}
        </div>
        <Link href={backHref} className="qs-btn qs-btn-secondary !py-2 shrink-0">
          ← Back to project
        </Link>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {summary.map(({ vendor, quote }) => (
          <div
            key={quote.id}
            className="bg-white rounded-lg border border-stone-200 px-3 py-2.5"
          >
            <p className="text-[11px] text-stone-400 truncate">
              {vendor.companyName}
            </p>
            <p className="text-sm font-semibold text-stone-900">
              #{quote.quoteNumber}
            </p>
            <p className="text-xs text-stone-500 truncate">{quote.label}</p>
            <p className="qs-money text-sm text-[var(--accent)] mt-1">
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
  hasResults = false,
  onNewComparison,
}: {
  projectId?: string | null;
  hasResults?: boolean;
  onNewComparison?: () => void;
}) {
  const backHref = projectId
    ? `/project/${encodeURIComponent(projectId)}`
    : "/";
  const backLabel = projectId ? "Back to project" : "All projects";

  return (
    <div className="flex items-center justify-between gap-4">
      <Link
        href={backHref}
        className="inline-flex items-center gap-1.5 text-sm font-medium text-stone-600 hover:text-[var(--accent)] transition-colors"
      >
        <span aria-hidden>←</span> {backLabel}
      </Link>
      {hasResults && onNewComparison && (
        <button
          type="button"
          onClick={onNewComparison}
          className="qs-btn qs-btn-secondary !py-2"
        >
          New comparison
        </button>
      )}
    </div>
  );
}

export function CompareLoadingBanner({ message }: { message: string }) {
  return (
    <div className="qs-card p-5">
      <h1 className="text-lg font-semibold text-stone-900 tracking-tight">
        Building your comparison
      </h1>
      <p className="text-sm text-stone-500 mt-1">{message}</p>
    </div>
  );
}

/** @deprecated Use CompareLoadingBanner */
export const IntegratedLoadingBanner = CompareLoadingBanner;
