"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getUserDisplayName } from "@/lib/user-display";
import { fetchUserProjects, getAuthUserId } from "@/lib/project-api";
import type { ProjectSummary } from "@/lib/project-types";
import {
  filterProjects,
  serviceOptionsForFilter,
} from "@/lib/project-list-filter";
import { ProjectTile } from "./ProjectTile";
import StandalonePdfSection from "./StandalonePdfSection";
import { PdfUploadGateButton } from "./PdfUploadGateButton";

type DashboardError = {
  message: string;
  status: number;
};

function isAuthSessionError(error: DashboardError): boolean {
  const message = error.message.toLowerCase();
  return (
    error.status === 401 ||
    error.status === 403 ||
    message.includes("token") ||
    message.includes("unauthorized") ||
    message.includes("forbidden")
  );
}

export default function ProjectDashboard() {
  const { user, logout } = useAuth();
  const displayName = getUserDisplayName(user);
  const userId = getAuthUserId(user);

  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<DashboardError | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [serviceFilter, setServiceFilter] = useState("");

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
        setError({ message: result.message, status: result.status });
        setProjects([]);
      }
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [userId]);

  const showProminentPdf = !loading && !error && projects.length === 0;
  const sessionError = error ? isAuthSessionError(error) : false;

  const serviceOptions = useMemo(
    () => serviceOptionsForFilter(projects),
    [projects]
  );

  const filteredProjects = useMemo(
    () =>
      filterProjects(projects, {
        query: searchQuery,
        serviceId: serviceFilter,
      }),
    [projects, searchQuery, serviceFilter]
  );

  const isFiltering =
    searchQuery.trim().length > 0 || serviceFilter.trim().length > 0;

  return (
    <div className="bg-[#f8fafc] pb-12">
      <div className="bg-white border-b border-slate-100">
        <div className="max-w-5xl mx-auto px-4 md:px-6 py-8 flex flex-col md:flex-row md:items-center md:justify-between gap-5">
          <div>
            <p className="text-sm text-slate-500">Welcome back,</p>
            <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight mt-1">
              {displayName}
            </h1>
            <p className="text-sm text-slate-500 mt-2 max-w-xl">
              Your TatvaOps projects with vendor proposals. Open a project to compare quotes.
            </p>
          </div>

          <PdfUploadGateButton className="shrink-0 inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-sm font-semibold text-white bg-[#c04a00] hover:bg-[#a84000] transition-colors shadow-sm whitespace-nowrap">
            Upload & compare PDFs
          </PdfUploadGateButton>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 md:px-6 py-8">
        <div className="flex flex-col gap-3 mb-5 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-sm font-semibold text-slate-800">My projects</h2>
          {!loading && (
            <span className="text-xs text-slate-400">
              {isFiltering
                ? `${filteredProjects.length} of ${projects.length} active`
                : `${projects.length} active`}
            </span>
          )}
        </div>

        {!loading && projects.length > 0 && (
          <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-center">
            <label className="relative flex-1 min-w-0">
              <span className="sr-only">Search projects by quote ID or service</span>
              <svg
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
                aria-hidden
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z"
                />
              </svg>
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by quote ID or service…"
                className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-800 placeholder:text-slate-400 shadow-sm focus:border-[#c04a00]/40 focus:outline-none focus:ring-2 focus:ring-[#c04a00]/15"
              />
            </label>
            <label className="sm:w-56 shrink-0">
              <span className="sr-only">Filter by service type</span>
              <select
                value={serviceFilter}
                onChange={(e) => setServiceFilter(e.target.value)}
                className="w-full rounded-xl border border-slate-200 bg-white py-2.5 px-3 text-sm text-slate-800 shadow-sm focus:border-[#c04a00]/40 focus:outline-none focus:ring-2 focus:ring-[#c04a00]/15"
              >
                <option value="">All services</option>
                {serviceOptions.map((service) => (
                  <option key={service.id} value={service.id}>
                    {service.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
          </div>
        )}

        {!loading && error && sessionError && (
          <div className="rounded-2xl border border-orange-100 bg-white px-6 py-6 shadow-sm">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <p className="text-sm font-semibold text-slate-900">
                  Your session has expired
                </p>
                <p className="text-sm text-slate-500 mt-1 max-w-xl">
                  Please sign in again to securely load your TatvaOps projects.
                  Your quote comparison tools are still available below.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  logout();
                  window.location.href = "/login";
                }}
                className="inline-flex items-center justify-center rounded-xl bg-[#c04a00] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#a84000] transition-colors"
              >
                Sign in again
              </button>
            </div>
          </div>
        )}

        {!loading && error && !sessionError && (
          <div className="rounded-2xl border border-amber-100 bg-white px-6 py-5 text-sm text-slate-700 shadow-sm">
            We could not load your projects right now.
            <p className="text-xs text-slate-500 mt-1">
              Please try again in a moment. If this continues, contact support.
            </p>
          </div>
        )}

        {!loading && !error && projects.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-200 bg-white px-6 py-10 text-center text-sm text-slate-500">
            No projects found for your account yet.
            <p className="text-xs text-slate-400 mt-2">
              You can still compare vendor quote PDFs using the tool below.
            </p>
          </div>
        )}

        {!loading && projects.length > 0 && filteredProjects.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-200 bg-white px-6 py-10 text-center text-sm text-slate-500 mb-4">
            No projects match your search.
            <button
              type="button"
              onClick={() => {
                setSearchQuery("");
                setServiceFilter("");
              }}
              className="mt-2 block mx-auto text-xs font-medium text-[#c04a00] hover:underline"
            >
              Clear filters
            </button>
          </div>
        )}

        {!loading && filteredProjects.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
            {filteredProjects.map((project) => (
              <ProjectTile key={project.id} project={project} />
            ))}
          </div>
        )}

        {!loading && (
          <StandalonePdfSection prominent={showProminentPdf} />
        )}
      </div>
    </div>
  );
}
