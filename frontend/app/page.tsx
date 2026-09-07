"use client";

import React, { Suspense, useEffect } from "react";
import dynamic from "next/dynamic";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { extractPmProjectRef } from "@/lib/project-resolve";

const ProjectDashboard = dynamic(
  () => import("@/components/dashboard/ProjectDashboard"),
  {
    loading: () => (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
      </div>
    ),
  }
);

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen">
          Loading QuoteSense…
        </div>
      }
    >
      <HomeContent />
    </Suspense>
  );
}

function HomeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading } = useAuth();

  useEffect(() => {
    const sessionId = searchParams?.get("session_id");
    if (sessionId) {
      router.replace(`/compare?session_id=${encodeURIComponent(sessionId)}`);
      return;
    }
    const projectRef = extractPmProjectRef(
      new URLSearchParams(searchParams?.toString() ?? "")
    );
    if (projectRef) {
      router.replace(`/project/${encodeURIComponent(projectRef)}`);
    }
  }, [searchParams, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-stone-200 border-t-[var(--accent)] rounded-full animate-spin" />
      </div>
    );
  }

  const sessionId = searchParams?.get("session_id");
  const inboundProject = extractPmProjectRef(
    new URLSearchParams(searchParams?.toString() ?? "")
  );
  if (sessionId || inboundProject) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
      </div>
    );
  }

  return <ProjectDashboard />;
}
