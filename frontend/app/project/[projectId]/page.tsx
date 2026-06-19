"use client";

import React, { Suspense } from "react";
import { notFound, useParams } from "next/navigation";
import { getProjectById } from "@/lib/dummy-project-data";
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
  const projectId = typeof params.projectId === "string" ? params.projectId : "";
  const project = getProjectById(projectId);

  if (!project) notFound();

  return <ProjectHub project={project} />;
}
