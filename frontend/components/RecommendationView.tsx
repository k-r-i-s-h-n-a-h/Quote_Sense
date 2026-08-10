"use client";

import React from "react";

/** Render inline **bold** segments within a line. */
function renderInline(text: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-stone-900">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

const BULLET_RE = /^\s*([-*•]|\d+\.)\s+/;

/**
 * Procurement-style AI recommendation card. Does not invent confidence or
 * structured fields — renders the backend report text faithfully.
 */
export default function RecommendationView({ text }: { text: string }) {
  const lines = (text || "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

  const bullets = lines.filter((l) => BULLET_RE.test(l));
  const useBullets = bullets.length >= 2;
  const lead = useBullets
    ? lines.find((l) => !BULLET_RE.test(l))
    : lines[0];

  return (
    <div className="rounded-xl border border-[var(--ai-border)] bg-[linear-gradient(180deg,var(--ai-soft),#fff)] p-5 md:p-6">
      <p className="qs-eyebrow !text-[var(--ai)]">AI recommendation</p>
      {lead ? (
        <p className="mt-2 text-base font-semibold text-stone-900 tracking-tight leading-snug">
          {renderInline(lead)}
        </p>
      ) : null}

      {!useBullets ? (
        <div className="mt-4 whitespace-pre-wrap text-sm text-stone-700 leading-relaxed">
          {text}
        </div>
      ) : (
        <ul className="mt-4 space-y-2.5">
          {lines.map((line, i) => {
            const isBullet = BULLET_RE.test(line);
            const content = line.replace(BULLET_RE, "");
            if (!isBullet) {
              if (line === lead) return null;
              return (
                <li
                  key={i}
                  className="text-sm text-stone-700 leading-relaxed list-none"
                >
                  {renderInline(line)}
                </li>
              );
            }
            return (
              <li key={i} className="flex items-start gap-3">
                <span
                  className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--ai)]"
                  aria-hidden
                />
                <span className="text-sm text-stone-700 leading-relaxed">
                  {renderInline(content)}
                </span>
              </li>
            );
          })}
        </ul>
      )}

      <p className="mt-5 text-[11px] text-stone-400 leading-relaxed">
        Based on totals, scope coverage, and market moving-average baselines in
        this comparison. Inspect the matrix below before making a final decision.
      </p>
    </div>
  );
}
