"use client";

import React from "react";
import Link from "next/link";
import type { ProjectSummary } from "@/lib/dummy-project-data";

const STATUS_STYLE: Record<ProjectSummary["status"], string> = {
  in_progress: "bg-blue-50 text-blue-700",
  quotes_received: "bg-emerald-50 text-emerald-700",
  comparing: "bg-amber-50 text-amber-700",
};

type ProjectTileProps = {
  project: ProjectSummary;
};

export function ProjectTile({ project }: ProjectTileProps) {
  return (
    <Link
      href={`/project/${project.id}`}
      className="group qs-card p-5 flex flex-col min-h-[180px] hover:border-[#c04a00]/30 hover:shadow-md hover:shadow-orange-100/50 transition-all duration-200"
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <span className="text-2xl" aria-hidden>
          {project.service.icon}
        </span>
        <span
          className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full capitalize ${STATUS_STYLE[project.status]}`}
        >
          {project.status.replace("_", " ")}
        </span>
      </div>

      <p className="text-[10px] font-semibold text-[#c04a00] tracking-wide">
        {project.projectCode}
      </p>
      <h3 className="font-bold text-slate-900 text-base leading-snug mt-1 group-hover:text-[#c04a00] transition-colors line-clamp-2">
        {project.title}
      </h3>
      <p className="text-xs text-slate-500 mt-2 line-clamp-2 flex-1">{project.brief}</p>

      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
        <span>{project.service.name}</span>
        <span className="font-medium text-slate-700">
          {project.vendorCount} vendors · {project.quoteCount} quotes
        </span>
      </div>
    </Link>
  );
}
