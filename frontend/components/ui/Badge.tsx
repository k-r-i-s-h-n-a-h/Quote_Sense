import React from "react";
import type { QuoteStatus, QuoteTier } from "@/lib/project-types";
import { QUOTE_TIER_LABELS } from "@/lib/project-types";

type BadgeTone =
  | "neutral"
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "ai";

const TONE_CLASS: Record<BadgeTone, string> = {
  neutral: "bg-stone-100 text-stone-700",
  accent: "bg-[var(--accent-soft)] text-[var(--accent)]",
  success: "bg-[var(--success-soft)] text-[var(--success)]",
  warning: "bg-[var(--warning-soft)] text-[var(--warning)]",
  danger: "bg-[var(--danger-soft)] text-[var(--danger)]",
  info: "bg-[var(--info-soft)] text-[var(--info)]",
  ai: "bg-[var(--ai-soft)] text-[var(--ai)]",
};

export function Badge({
  children,
  tone = "neutral",
  className = "",
  title,
}: {
  children: React.ReactNode;
  tone?: BadgeTone;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${TONE_CLASS[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

const TIER_TONE: Record<QuoteTier, BadgeTone> = {
  ESSENTIAL: "success",
  MID_SEGMENT: "info",
  LUXURY: "ai",
};

export function TierBadge({
  tier,
  className = "",
}: {
  tier: QuoteTier;
  className?: string;
}) {
  return (
    <Badge tone={TIER_TONE[tier]} className={className} title="Quote type">
      {QUOTE_TIER_LABELS[tier]}
    </Badge>
  );
}

const STATUS_TONE: Record<QuoteStatus, BadgeTone> = {
  draft: "neutral",
  submitted: "success",
  revised: "warning",
  finalized: "ai",
};

export function QuoteStatusBadge({
  status,
  className = "",
}: {
  status: QuoteStatus;
  className?: string;
}) {
  // FINALIZED is a separate badge from isFinalizeQuote — never show lifecycle as finalized.
  const display = status === "finalized" ? "submitted" : status;
  return (
    <Badge
      tone={STATUS_TONE[display]}
      className={className}
      title="Tatva quote lifecycle (status field)"
    >
      {display}
    </Badge>
  );
}

const PROJECT_STATUS_TONE: Record<string, BadgeTone> = {
  in_progress: "info",
  quotes_received: "success",
  comparing: "warning",
  completed: "ai",
};

export function ProjectStatusBadge({
  status,
  className = "",
}: {
  status: string;
  className?: string;
}) {
  return (
    <Badge
      tone={PROJECT_STATUS_TONE[status] || "neutral"}
      className={className}
      title="Project status"
    >
      {status.replaceAll("_", " ")}
    </Badge>
  );
}
