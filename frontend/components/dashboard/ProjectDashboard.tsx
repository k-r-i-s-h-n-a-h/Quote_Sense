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
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorState } from "@/components/ui/EmptyState";
import SessionExpiredModal from "@/components/SessionExpiredModal";

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

function ProjectGridSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="qs-card p-5 min-h-[188px] space-y-3">
          <div className="flex justify-between">
            <div className="h-10 w-10 qs-skeleton" />
            <div className="h-5 w-20 qs-skeleton" />
          </div>
          <div className="h-3 w-16 qs-skeleton" />
          <div className="h-5 w-3/4 qs-skeleton" />
          <div className="h-3 w-full qs-skeleton" />
          <div className="h-3 w-2/3 qs-skeleton" />
        </div>
      ))}
    </div>
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
  const [dismissedSessionModal, setDismissedSessionModal] = useState(false);

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
    <div className="pb-14">
      <div className="border-b border-stone-200/80 bg-white/70 backdrop-blur-sm">
        <div className="qs-container py-8 md:py-10">
          <PageHeader
            eyebrow="QuoteSense"
            title={
              <>
                Vendor quote intelligence
                <span className="block text-base md:text-lg font-medium text-stone-500 mt-1">
                  Welcome back, {displayName}
                </span>
              </>
            }
            description="Open a project to select 2–3 same-tier vendor quotes, compare costs against market rates, and review an AI recommendation."
            actions={
              <PdfUploadGateButton className="qs-btn qs-btn-primary whitespace-nowrap">
                Upload & compare PDFs
              </PdfUploadGateButton>
            }
          />
        </div>
      </div>

      <div className="qs-container py-8">
        <div className="flex flex-col gap-3 mb-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="qs-section-title">My projects</h2>
            <p className="qs-section-sub">
              Active TatvaOps projects with vendor proposals.
            </p>
          </div>
          {!loading && (
            <span className="text-xs text-stone-400 tabular-nums">
              {isFiltering
                ? `${filteredProjects.length} of ${projects.length} projects`
                : `${projects.length} project${projects.length === 1 ? "" : "s"}`}
            </span>
          )}
        </div>

        {!loading && projects.length > 0 && (
          <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-center">
            <label className="relative flex-1 min-w-0">
              <span className="sr-only">Search projects by quote ID or service</span>
              <svg
                className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400"
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
                className="qs-input qs-input-icon"
              />
            </label>
            <label className="sm:w-56 shrink-0">
              <span className="sr-only">Filter by service type</span>
              <select
                value={serviceFilter}
                onChange={(e) => setServiceFilter(e.target.value)}
                className="qs-select"
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

        {loading && <ProjectGridSkeleton />}

        {sessionError && !dismissedSessionModal && (
          <SessionExpiredModal
            onSignIn={() => {
              logout();
              window.location.href = "/login";
            }}
            onContinue={() => setDismissedSessionModal(true)}
          />
        )}

        {!loading && error && sessionError && (
          <EmptyState
            title="Projects unavailable"
            description="Sign in to load your TatvaOps projects. You can still compare vendor quote PDFs using the standalone tool below."
          />
        )}

        {!loading && error && !sessionError && (
          <ErrorState
            title="We couldn’t load your projects"
            description="Please try again in a moment. If this continues, contact support."
          />
        )}

        {!loading && !error && projects.length === 0 && (
          <EmptyState
            title="No projects yet"
            description="Projects assigned to your TatvaOps account will appear here. You can still compare vendor quote PDFs using the standalone tool below."
          />
        )}

        {!loading && projects.length > 0 && filteredProjects.length === 0 && (
          <EmptyState
            title="No matching projects"
            description="Try a different quote ID, service name, or clear your filters."
            action={
              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setServiceFilter("");
                }}
                className="qs-btn qs-btn-secondary"
              >
                Clear filters
              </button>
            }
          />
        )}

        {!loading && filteredProjects.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {filteredProjects.map((project) => (
              <ProjectTile key={project.id} project={project} />
            ))}
          </div>
        )}

        {!loading && <StandalonePdfSection prominent={showProminentPdf} />}
      </div>
    </div>
  );
}
