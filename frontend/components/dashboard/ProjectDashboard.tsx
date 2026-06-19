"use client";

import React from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { getProjectsForUser } from "@/lib/dummy-project-data";
import { ProjectTile } from "./ProjectTile";

export default function ProjectDashboard() {
  const { user } = useAuth();
  const displayName = user?.name || user?.fullName || user?.phoneNumber || "there";
  const projects = getProjectsForUser(displayName);

  return (
    <div className="min-h-screen bg-[#f8fafc]">
      <div className="bg-white border-b border-slate-100">
        <div className="max-w-5xl mx-auto px-4 md:px-6 py-8">
          <p className="text-sm text-slate-500">Welcome back,</p>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight mt-1">
            {displayName}
          </h1>
          <p className="text-sm text-slate-500 mt-2 max-w-xl">
            Your TatvaOps projects with vendor proposals. Open a project to compare quotes.
          </p>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 md:px-6 py-8">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-sm font-semibold text-slate-800">My projects</h2>
          <span className="text-xs text-slate-400">{projects.length} active</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
          {projects.map((project) => (
            <ProjectTile key={project.id} project={project} />
          ))}
        </div>
      </div>
    </div>
  );
}
