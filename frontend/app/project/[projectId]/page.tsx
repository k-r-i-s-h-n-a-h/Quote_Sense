"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { notFound, useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { fetchProjectWithQuotes, getAuthUserId } from "@/lib/project-api";
import type { ProjectData } from "@/lib/project-types";
import ProjectHub from "@/components/project/ProjectHub";

export default function ProjectDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
        </div>
      }
    >
      <ProjectDetailContent />
    </Suspense>
  );
}

function ProjectDetailContent() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const projectId = typeof params.projectId === "string" ? params.projectId : "";
  const userId = getAuthUserId(user);

  const [project, setProject] = useState<ProjectData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;

    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);
      const result = await fetchProjectWithQuotes(projectId, userId);
      if (cancelled) return;

      if (result.ok) {
        setProject(result.project);
      } else {
        setError(result.message);
        setProject(null);
      }
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [projectId, userId]);

  // Canonical URL uses public project code (0F44A3), not Mongo _id.
  useEffect(() => {
    if (!project?.projectCode || typeof window === "undefined") return;
    const canonical = project.projectCode;
    if (canonical.toUpperCase() === projectId.toUpperCase()) return;
    const qs = window.location.search;
    router.replace(`/project/${encodeURIComponent(canonical)}${qs}`, {
      scroll: false,
    });
  }, [project, projectId, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-lg mx-auto mt-16 px-4 text-center">
        <p className="text-red-600 text-sm font-medium">{error}</p>
        <Link href="/" className="inline-block mt-4 text-sm text-[#c04a00] hover:underline">
          ← Back to projects
        </Link>
      </div>
    );
  }

  if (!project) notFound();

  return <ProjectHub project={project} />;
}
