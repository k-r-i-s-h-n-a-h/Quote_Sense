"use client";

import React, { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  TATVA_SERVICES,
  type ProjectData,
} from "@/lib/project-types";
import {
  cacheSelectedComparePayloads,
  readCachedProjectQuotePayloads,
} from "@/lib/compare-payload-cache";
import { projectHref } from "@/lib/project-api";
import {
  MAX_COMPARE_QUOTES,
  MIN_COMPARE_QUOTES,
  MAX_COMPARE_MESSAGE,
  clampQuoteIds,
  isValidCompareCount,
} from "@/lib/compare-limits";
import { VendorCard } from "./VendorCard";
import { CompareActionBar } from "./CompareActionBar";

type ProjectHubProps = {
  project: ProjectData;
};

export default function ProjectHub({ project }: ProjectHubProps) {
  const router = useRouter();
  const [selectedQuoteIds, setSelectedQuoteIds] = useState<Set<string>>(new Set());
  const [limitMessage, setLimitMessage] = useState<string | null>(null);

  const selectionFull = selectedQuoteIds.size >= MAX_COMPARE_QUOTES;

  const toggleQuote = useCallback((quoteId: string) => {
    setSelectedQuoteIds((prev) => {
      const next = new Set(prev);
      if (next.has(quoteId)) {
        next.delete(quoteId);
        setLimitMessage(null);
        return next;
      }
      if (next.size >= MAX_COMPARE_QUOTES) {
        setLimitMessage(MAX_COMPARE_MESSAGE);
        return prev;
      }
      next.add(quoteId);
      setLimitMessage(null);
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedQuoteIds(new Set());
    setLimitMessage(null);
  }, []);

  const navigateToCompare = useCallback(
    (quoteIds: string[]) => {
      const limited = clampQuoteIds(quoteIds);
      if (!isValidCompareCount(limited.length)) return;

      const cached = readCachedProjectQuotePayloads(project.projectCode);
      if (cached) {
        const wanted = new Set(limited.map(String));
        const selected = cached.quotes.filter((q) =>
          wanted.has(String(q._id || q.id))
        );
        if (isValidCompareCount(selected.length)) {
          cacheSelectedComparePayloads(project.projectCode, selected, cached.meta);
        }
      }

      const params = new URLSearchParams({
        quotes: limited.join(","),
        projectId: project.projectCode,
      });
      router.push(`/compare?${params.toString()}`);
    },
    [project.id, project.projectCode, router]
  );

  const handleCompare = useCallback(() => {
    if (!isValidCompareCount(selectedQuoteIds.size)) return;
    navigateToCompare(Array.from(selectedQuoteIds));
  }, [navigateToCompare, selectedQuoteIds]);

  const handleCompareVendorQuotes = useCallback(
    (vendorId: string) => {
      const vendor = project.vendors.find((v) => v.id === vendorId);
      if (!vendor || vendor.quotes.length < MIN_COMPARE_QUOTES) return;

      const ids = vendor.quotes.slice(0, MAX_COMPARE_QUOTES).map((q) => q.id);
      setSelectedQuoteIds(new Set(ids));
      setLimitMessage(
        vendor.quotes.length > MAX_COMPARE_QUOTES
          ? `Only ${MAX_COMPARE_QUOTES} quotes can be compared — the first ${MAX_COMPARE_QUOTES} are selected.`
          : null
      );
      navigateToCompare(ids);
    },
    [project.vendors, navigateToCompare]
  );

  const totalQuotes = useMemo(
    () => project.vendors.reduce((n, v) => n + v.quotes.length, 0),
    [project.vendors]
  );

  return (
    <div className="min-h-screen bg-[#f8fafc] pb-28">
      {/* Project header */}
      <div className="bg-white border-b border-slate-100">
        <div className="max-w-4xl mx-auto px-4 md:px-6 py-6">
          <Link
            href="/"
            className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-[#c04a00] mb-4 transition-colors"
          >
            ← All projects
          </Link>
          <div className="flex items-center gap-2 text-xs text-slate-500 mb-3">
            <span className="font-medium text-[#c04a00]">{project.projectCode}</span>
            <span>·</span>
            <span>{project.clientName}</span>
          </div>
          <h1 className="text-xl md:text-2xl font-bold text-slate-900 tracking-tight">
            {project.title}
          </h1>
          <p className="text-sm text-slate-500 mt-2 max-w-2xl leading-relaxed">{project.brief}</p>

          <div className="flex flex-wrap items-center gap-2 mt-4">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-xs font-medium">
              <span>{project.service.icon}</span>
              {project.service.name}
            </span>
            <span className="inline-flex items-center px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-medium">
              {project.vendors.length} vendors · {totalQuotes} quotes
            </span>
            <span className="inline-flex items-center px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium capitalize">
              {project.status.replace("_", " ")}
            </span>
          </div>
        </div>
      </div>

      {/* How it works — minimal hint */}
      <div className="max-w-4xl mx-auto px-4 md:px-6 pt-6 space-y-2">
        <div className="rounded-xl border border-dashed border-slate-200 bg-white/60 px-4 py-3 text-xs text-slate-500 leading-relaxed">
          <strong className="text-slate-700 font-medium">Compare quotes</strong> — pick{" "}
          {MIN_COMPARE_QUOTES}–{MAX_COMPARE_QUOTES} proposals (even if a vendor has more), then
          click <strong className="text-slate-700">Compare quotes</strong>.
        </div>
        {limitMessage && (
          <div
            role="alert"
            className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800 leading-relaxed"
          >
            {limitMessage}
          </div>
        )}
      </div>

      {/* Service pills — other Tatva services (context) */}
      <div className="max-w-4xl mx-auto px-4 md:px-6 pt-5">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
          TatvaOps services
        </p>
        <div className="flex flex-wrap gap-1.5">
          {TATVA_SERVICES.map((svc) => (
            <span
              key={svc.id}
              className={`text-[11px] px-2.5 py-1 rounded-md border ${
                svc.id === project.service.id
                  ? "border-[#c04a00]/30 bg-orange-50 text-[#c04a00] font-medium"
                  : "border-slate-100 bg-white text-slate-400"
              }`}
            >
              {svc.icon} {svc.name}
            </span>
          ))}
        </div>
      </div>

      {/* Vendor quote cards */}
      <div className="max-w-4xl mx-auto px-4 md:px-6 py-6 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-slate-800">
            Assigned vendors & proposals
          </h2>
          {selectedQuoteIds.size > 0 && (
            <span className="text-xs text-slate-500 tabular-nums">
              {selectedQuoteIds.size}/{MAX_COMPARE_QUOTES} selected
            </span>
          )}
        </div>
        {project.vendors.map((vendor) => (
          <VendorCard
            key={vendor.id}
            vendor={vendor}
            selectedQuoteIds={selectedQuoteIds}
            selectionFull={selectionFull}
            onToggleQuote={toggleQuote}
            onCompareVendorQuotes={handleCompareVendorQuotes}
          />
        ))}
      </div>

      <CompareActionBar
        project={project}
        selectedIds={Array.from(selectedQuoteIds)}
        limitMessage={limitMessage}
        onCompare={handleCompare}
        onClear={clearSelection}
      />
    </div>
  );
}
