"use client";

import React from "react";

/** Render inline **bold** segments within a line. */
function renderInline(text: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-gray-900">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

const BULLET_RE = /^\s*([-*•]|\d+\.)\s+/;

/**
 * Render the AI recommendation as a clean bullet list. Falls back gracefully to
 * paragraphs for any non-bullet lines.
 */
export default function RecommendationView({ text }: { text: string }) {
  const lines = (text || "")
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

  const bullets = lines.filter((l) => BULLET_RE.test(l));
  const useBullets = bullets.length >= 2;

  if (!useBullets) {
    return (
      <div className="prose max-w-none whitespace-pre-wrap text-gray-700 leading-relaxed">
        {text}
      </div>
    );
  }

  return (
    <ul className="space-y-3">
      {lines.map((line, i) => {
        const isBullet = BULLET_RE.test(line);
        const content = line.replace(BULLET_RE, "");
        if (!isBullet) {
          return (
            <li key={i} className="text-gray-700 leading-relaxed list-none">
              {renderInline(line)}
            </li>
          );
        }
        return (
          <li key={i} className="flex items-start gap-3">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-600" />
            <span className="text-gray-700 leading-relaxed">
              {renderInline(content)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
