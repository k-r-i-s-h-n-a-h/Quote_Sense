"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getUserDisplayName } from "@/lib/user-display";
import { fetchUserProjects, getAuthUserId } from "@/lib/project-api";
import type { ProjectSummary } from "@/lib/project-types";
import { ProjectTile } from "./ProjectTile";
import StandalonePdfSection from "./StandalonePdfSection";
import { PdfUploadGateButton } from "./PdfUploadGateButton";

export default function ProjectDashboard() {
  const { user } = useAuth();
  const displayName = getUserDisplayName(user);
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
      // #region agent log
      fetch('http://127.0.0.1:7880/ingest/fae56c38-48bc-450d-a803-35ac016bc76b',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'b7c34a'},body:JSON.stringify({sessionId:'b7c34a',location:'ProjectDashboard.tsx:fetch',message:'projects fetch result',data:{ok:result.ok,status:result.ok?200:('status' in result?result.status:null),count:result.ok?result.projects.length:0,message:result.ok?null:result.message},timestamp:Date.now(),hypothesisId:'H4'})}).catch(()=>{});
      // #endregion
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [userId]);

  const showProminentPdf = !loading && !error && projects.length === 0;

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
            <span className="text-base leading-none">📄</span>
            Upload & compare PDFs
          </PdfUploadGateButton>
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
          <div className="rounded-xl border border-dashed border-slate-200 bg-white px-6 py-10 text-center text-sm text-slate-500">
            No projects found for your account yet.
            <p className="text-xs text-slate-400 mt-2">
              You can still compare vendor quote PDFs using the tool below.
            </p>
          </div>
        )}

        {!loading && projects.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
            {projects.map((project) => (
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
