"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { fetchUserProjects, getAuthUserId } from "@/lib/project-api";
import type { ProjectSummary } from "@/lib/project-types";
import { ProjectTile } from "./ProjectTile";

export default function ProjectDashboard() {
  const { user } = useAuth();
  const displayName = user?.name || user?.fullName || user?.phoneNumber || "there";
  const userId = getAuthUserId(user);

  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);
      const result = await fetchUserProjects(userId);
      if (cancelled) return;

      if (result.ok) {
        setProjects(result.projects);
      } else {
        setError(result.message);
        setProjects([]);
      }
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [userId]);

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
          {!loading && (
            <span className="text-xs text-slate-400">{projects.length} active</span>
          )}
        </div>

        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
          </div>
        )}

        {!loading && error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
            <p className="text-xs text-red-600/80 mt-1">
              Ensure you are logged in and TatvaOps APIs are reachable.
            </p>
          </div>
        )}

        {!loading && !error && projects.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-500">
            No projects found for your account yet.
          </div>
        )}

        {!loading && projects.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
            {projects.map((project) => (
              <ProjectTile key={project.id} project={project} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
