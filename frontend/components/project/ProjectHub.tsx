"use client";

import React, { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  type ProjectData,
  findQuoteById,
  QUOTE_TIER_LABELS,
} from "@/lib/project-types";
import {
  buildTatvaServiceUrl,
  getTatvaServicesForNav,
} from "@/lib/tatva-services";
import {
  cacheSelectedComparePayloads,
  readCachedProjectQuotePayloads,
} from "@/lib/compare-payload-cache";
import {
  MAX_COMPARE_QUOTES,
  MIN_COMPARE_QUOTES,
  MAX_COMPARE_MESSAGE,
  clampQuoteIds,
  compareCountPhrase,
  isValidCompareCount,
} from "@/lib/compare-limits";
import { VendorCard } from "./VendorCard";
import { CompareActionBar } from "./CompareActionBar";
import { PageHeader } from "@/components/ui/PageHeader";
import { ProjectStatusBadge, TierBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";

type ProjectHubProps = {
  project: ProjectData;
};

export default function ProjectHub({ project }: ProjectHubProps) {
  const router = useRouter();
  const [selectedQuoteIds, setSelectedQuoteIds] = useState<Set<string>>(
    new Set()
  );
  const [limitMessage, setLimitMessage] = useState<string | null>(null);

  const selectionFull = selectedQuoteIds.size >= MAX_COMPARE_QUOTES;

  const selectedTier = useMemo(() => {
    for (const id of selectedQuoteIds) {
      const found = findQuoteById(project, id);
      if (found?.quote.tier) return found.quote.tier;
    }
    return undefined;
  }, [project, selectedQuoteIds]);

  const toggleQuote = useCallback(
    (quoteId: string) => {
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
            `Compare quotes from the same tier. You've selected ${QUOTE_TIER_LABELS[currentTier]} — pick another ${QUOTE_TIER_LABELS[currentTier]} quote.`
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
    },
    [project]
  );

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
          cacheSelectedComparePayloads(
            project.projectCode,
            selected,
            cached.meta
          );
        }
      }

      const params = new URLSearchParams({
        quotes: limited.join(","),
        projectId: project.projectCode,
      });
      router.push(`/compare?${params.toString()}`);
    },
    [project.projectCode, router]
  );

  const handleCompare = useCallback(() => {
    if (!isValidCompareCount(selectedQuoteIds.size)) return;
    navigateToCompare(Array.from(selectedQuoteIds));
  }, [navigateToCompare, selectedQuoteIds]);

  const handleCompareVendorQuotes = useCallback(
    (vendorId: string) => {
      const vendor = project.vendors.find((v) => v.id === vendorId);
      if (!vendor || vendor.quotes.length < MIN_COMPARE_QUOTES) return;

      const firstTier = vendor.quotes.find((q) => q.tier)?.tier;
      const sameTierQuotes = firstTier
        ? vendor.quotes.filter((q) => !q.tier || q.tier === firstTier)
        : vendor.quotes;

      if (!isValidCompareCount(sameTierQuotes.length)) {
        setLimitMessage(
          "This vendor's quotes span different tiers (Essential / Mid / Luxury). Select at least 2 of the same tier to compare."
        );
        return;
      }

      const ids = sameTierQuotes.slice(0, MAX_COMPARE_QUOTES).map((q) => q.id);
      setSelectedQuoteIds(new Set(ids));
      setLimitMessage(
        sameTierQuotes.length > MAX_COMPARE_QUOTES
          ? `Only ${MAX_COMPARE_QUOTES} quotes can be compared — the first ${MAX_COMPARE_QUOTES} of the same tier are selected.`
          : sameTierQuotes.length < vendor.quotes.length
            ? "Some of this vendor's quotes were a different tier and were skipped."
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
        (n, v) => n + v.quotes.filter((q) => q.isFinalizeQuote === true).length,
        0
      ),
    [project.vendors]
  );

  return (
    <div className="pb-32">
      <div className="border-b border-stone-200/80 bg-white/70 backdrop-blur-sm">
        <div className="qs-container py-6 md:py-8">
          <Link
            href="/"
            className="inline-flex items-center gap-1 text-xs font-medium text-stone-500 hover:text-[var(--accent)] mb-4 transition-colors"
          >
            ← All projects
          </Link>
          <PageHeader
            eyebrow={project.projectCode}
            title={project.title}
            description={
              <>
                {project.brief}
                {project.clientName && project.clientName !== "—" ? (
                  <span className="block mt-1 text-stone-400">
                    Client · {project.clientName}
                  </span>
                ) : null}
              </>
            }
            meta={
              <>
                <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-stone-100 text-stone-700 text-xs font-medium">
                  {project.service.name}
                </span>
                <span className="inline-flex items-center px-2.5 py-1 rounded-md bg-stone-100 text-stone-600 text-xs font-medium">
                  {project.vendors.length} vendor
                  {project.vendors.length === 1 ? "" : "s"}
                  {totalQuotes > 0
                    ? ` · ${totalQuotes} quote${totalQuotes === 1 ? "" : "s"}`
                    : ""}
                </span>
                <ProjectStatusBadge status={project.status} />
                {finalizedQuotes > 0 ? (
                  <span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-violet-50 text-violet-800">
                    {finalizedQuotes} finalized
                  </span>
                ) : null}
                {selectedTier ? <TierBadge tier={selectedTier} /> : null}
              </>
            }
          />
        </div>
      </div>

      <div className="qs-container pt-6 space-y-3">
        <div className="qs-card px-4 py-3.5 border-dashed">
          <p className="text-sm text-stone-700 leading-relaxed">
            <strong className="font-semibold text-stone-900">
              Pick {compareCountPhrase()} quotes from the same
              tier
            </strong>{" "}
            (Essential, Mid-segment, or Luxury), then compare. Mixing tiers is
            blocked so comparisons stay like-for-like.
          </p>
        </div>
        {limitMessage && (
          <div
            role="alert"
            className="rounded-lg border border-[var(--warning-border)] bg-[var(--warning-soft)] px-4 py-3 text-sm text-amber-900 leading-relaxed"
          >
            {limitMessage}
          </div>
        )}
      </div>

      <div className="qs-container pt-5">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-stone-400 mb-2">
          TatvaOps services
        </p>
        <div className="flex flex-wrap gap-1.5">
          {getTatvaServicesForNav().map((svc) => {
            const isActive = svc.id === project.service.id;
            const className = `text-[11px] px-2.5 py-1 rounded-md border transition-colors duration-150 ${
              isActive
                ? "border-[color-mix(in_srgb,var(--accent)_35%,var(--border))] bg-[var(--accent-soft)] text-[var(--accent)] font-medium"
                : svc.href
                  ? "border-stone-200 bg-white text-stone-500 hover:border-[color-mix(in_srgb,var(--accent)_25%,var(--border))] hover:text-[var(--accent)]"
                  : "border-stone-100 bg-white text-stone-400"
            }`;
            const label = svc.name;
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

      <div className="qs-container py-6 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="qs-section-title">Vendors & proposals</h2>
            <p className="qs-section-sub">
              Select quotes to analyze side-by-side.
            </p>
          </div>
          {selectedQuoteIds.size > 0 && (
            <span className="text-xs text-stone-500 tabular-nums">
              {selectedQuoteIds.size}/{MAX_COMPARE_QUOTES} selected
            </span>
          )}
        </div>

        {project.vendors.length === 0 ? (
          <EmptyState
            title="No vendor quotes yet"
            description="When vendors submit proposals for this project, they’ll appear here for selection and comparison."
          />
        ) : (
          project.vendors.map((vendor) => (
            <VendorCard
              key={vendor.id}
              vendor={vendor}
              selectedQuoteIds={selectedQuoteIds}
              selectionFull={selectionFull}
              selectedTier={selectedTier}
              onToggleQuote={toggleQuote}
              onCompareVendorQuotes={handleCompareVendorQuotes}
            />
          ))
        )}
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
