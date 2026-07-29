"use client";

import React, { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ProjectData, findQuoteById, QUOTE_TIER_LABELS } from "@/lib/project-types";
import {
  buildTatvaServiceUrl,
  getTatvaServicesForNav,
} from "@/lib/tatva-services";
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

  // Quote type (Essential / Mid-segment / Luxury) of the current selection — every
  // new pick must match this so comparisons stay apples-to-apples.
  const selectedTier = useMemo(() => {
    for (const id of selectedQuoteIds) {
      const found = findQuoteById(project, id);
      if (found?.quote.tier) return found.quote.tier;
    }
    return undefined;
  }, [project, selectedQuoteIds]);

  const toggleQuote = useCallback((quoteId: string) => {
    setSelectedQuoteIds((prev) => {
      const next = new Set(prev);
      if (next.has(quoteId)) {
        next.delete(quoteId);
        setLimitMessage(null);
        return next;
      }

      const found = findQuoteById(project, quoteId);
      const newTier = found?.quote.tier;
      let currentTier: typeof newTier;
      for (const id of prev) {
        const t = findQuoteById(project, id)?.quote.tier;
        if (t) {
          currentTier = t;
          break;
        }
      }

      if (currentTier && newTier && currentTier !== newTier) {
        setLimitMessage(
          `You've selected ${QUOTE_TIER_LABELS[currentTier]} quotes — pick another ${QUOTE_TIER_LABELS[currentTier]} quote to compare like-for-like.`
        );
        return prev;
      }

      if (next.size >= MAX_COMPARE_QUOTES) {
        setLimitMessage(MAX_COMPARE_MESSAGE);
        return prev;
      }
      next.add(quoteId);
      setLimitMessage(null);
      return next;
    });
  }, [project]);

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

      // A vendor can submit quotes of different types (Essential/Mid-segment/Luxury) —
      // only compare quotes that share the same type as the first one.
      const firstTier = vendor.quotes.find((q) => q.tier)?.tier;
      const sameTierQuotes = firstTier
        ? vendor.quotes.filter((q) => !q.tier || q.tier === firstTier)
        : vendor.quotes;

      if (!isValidCompareCount(sameTierQuotes.length)) {
        setLimitMessage(
          "This vendor's quotes are different types (Essential/Mid-segment/Luxury) — select at least 2 of the same type to compare."
        );
        return;
      }

      const ids = sameTierQuotes.slice(0, MAX_COMPARE_QUOTES).map((q) => q.id);
      setSelectedQuoteIds(new Set(ids));
      setLimitMessage(
        sameTierQuotes.length > MAX_COMPARE_QUOTES
          ? `Only ${MAX_COMPARE_QUOTES} quotes can be compared — the first ${MAX_COMPARE_QUOTES} of the same type are selected.`
          : sameTierQuotes.length < vendor.quotes.length
            ? "Some of this vendor's quotes were a different type and were skipped."
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

  const finalizedQuotes = useMemo(
    () =>
      project.vendors.reduce(
        (n, v) => n + v.quotes.filter((q) => q.status === "finalized").length,
        0
      ),
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
              {project.vendors.length} vendor{project.vendors.length === 1 ? "" : "s"}
              {totalQuotes > 0
                ? ` · ${totalQuotes} quote${totalQuotes === 1 ? "" : "s"}`
                : ""}
              {finalizedQuotes > 0
                ? ` · ${finalizedQuotes} finalized`
                : ""}
            </span>
            <span
              className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium capitalize ${
                project.status === "completed"
                  ? "bg-violet-50 text-violet-800"
                  : project.status === "comparing"
                    ? "bg-amber-50 text-amber-700"
                    : project.status === "quotes_received"
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-blue-50 text-blue-700"
              }`}
              title="Project lifecycle status — independent of quote finalize"
            >
              {project.status.replaceAll("_", " ")}
            </span>
          </div>
        </div>
      </div>

      {/* How it works — minimal hint */}
      <div className="max-w-4xl mx-auto px-4 md:px-6 pt-6 space-y-2">
        <div className="rounded-xl border border-dashed border-slate-200 bg-white/60 px-4 py-3 text-xs text-slate-500 leading-relaxed">
          <strong className="text-slate-700 font-medium">Compare quotes</strong> — pick{" "}
          {MIN_COMPARE_QUOTES}–{MAX_COMPARE_QUOTES} proposals of the{" "}
          <strong className="text-slate-700">same quote type</strong> (Essential / Mid-segment /
          Luxury), then click <strong className="text-slate-700">Compare quotes</strong>.
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
          {getTatvaServicesForNav().map((svc) => {
            const isActive = svc.id === project.service.id;
            const className = `text-[11px] px-2.5 py-1 rounded-md border transition-colors ${
              isActive
                ? "border-[#c04a00]/30 bg-orange-50 text-[#c04a00] font-medium"
                : svc.href
                  ? "border-slate-100 bg-white text-slate-500 hover:border-[#c04a00]/20 hover:text-[#c04a00]"
                  : "border-slate-100 bg-white text-slate-400"
            }`;
            const label = (
              <>
                {svc.icon} {svc.name}
              </>
            );
            if (svc.href) {
              return (
                <a
                  key={svc.id}
                  href={buildTatvaServiceUrl(svc.href)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={className}
                >
                  {label}
                </a>
              );
            }
            return (
              <span key={svc.id} className={className}>
                {label}
              </span>
            );
          })}
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
            selectedTier={selectedTier}
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
