"use client";

import React from "react";
import Link from "next/link";
import type { ProjectSummary } from "@/lib/project-types";
import { projectHref } from "@/lib/project-api";
import { ProjectStatusBadge } from "@/components/ui/Badge";

function formatUpdated(value: string): string {
  if (!value || value === "—") return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

type ProjectTileProps = {
  project: ProjectSummary;
};

export function ProjectTile({ project }: ProjectTileProps) {
  const updated = formatUpdated(project.updatedAt);
  const initial = (project.service.name || "P").charAt(0).toUpperCase();

  return (
    <Link
      href={projectHref(project)}
      className="group qs-card qs-card-hover p-5 flex flex-col min-h-[188px] focus-visible:outline-offset-4"
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-stone-100 text-sm font-semibold text-stone-700">
          {initial}
        </div>
        <ProjectStatusBadge status={project.status} />
      </div>

      <p className="text-[11px] font-semibold text-[var(--accent)] tracking-wide">
        {project.projectCode}
      </p>
      <h3 className="font-semibold text-stone-900 text-[15px] leading-snug mt-1 group-hover:text-[var(--accent)] transition-colors duration-150 line-clamp-2">
        {project.title}
      </h3>

      {(project.clientName || project.brief) && (
        <p className="text-xs text-stone-500 mt-2 line-clamp-2 flex-1">
          {project.clientName && project.clientName !== "—"
            ? project.clientName
            : project.brief}
        </p>
      )}

      <div className="mt-4 pt-3 border-t border-stone-100 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-stone-700 truncate">
            {project.service.name}
          </p>
          <p className="text-[11px] text-stone-500 mt-0.5">
            {project.vendorCount} vendor{project.vendorCount === 1 ? "" : "s"}
            {project.quoteCount > 0
              ? ` · ${project.quoteCount} quote${project.quoteCount === 1 ? "" : "s"}`
              : ""}
            {project.finalizedQuoteCount > 0
              ? ` · ${project.finalizedQuoteCount} finalized`
              : ""}
          </p>
          {updated ? (
            <p className="text-[11px] text-stone-400 mt-1">Updated {updated}</p>
          ) : null}
        </div>
        <span className="shrink-0 text-xs font-semibold text-[var(--accent)] opacity-80 group-hover:opacity-100 transition-opacity">
          View →
        </span>
      </div>
    </Link>
  );
}
