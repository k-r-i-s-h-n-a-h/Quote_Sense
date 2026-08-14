"use client";

import React, { useState, useEffect, useRef, useMemo, Suspense } from "react";
import dynamic from "next/dynamic";
import { useSearchParams, useRouter } from "next/navigation";
import CompareLoadingPanel, {
  type CompareProgressStage,
} from "../../components/CompareLoadingPanel";
import VendorInsights from "../../components/VendorInsights";
import RecommendationView from "../../components/RecommendationView";
import VendorSummary from "../../components/compare/VendorSummary";
import ComparisonMatrix from "../../components/compare/ComparisonMatrix";
import CompareChat from "../../components/compare/CompareChat";
import { buildVendorLabels } from "../../lib/format";
import { downloadComparisonPdf } from "../../lib/download-comparison-pdf";
import { getCompareLane, showPdfUpload } from "../../lib/compare-lane";
import { STANDALONE_PDF_UPLOAD_ENABLED } from "../../lib/feature-flags";
import { StandalonePdfCompareGuard } from "../../components/dashboard/PdfUploadGateButton";
import {
  resolveQuotesForCompare,
  startMongoCompareJob,
} from "../../lib/compare-sync";
import {
  MAX_COMPARE_QUOTES,
  MIN_COMPARE_QUOTES,
  clampQuoteIds,
  isValidCompareCount,
} from "../../lib/compare-limits";
import { useAuth } from "@/lib/auth";
import { getAuthUserId } from "@/lib/project-api";
import {
  ComparePageNav,
  CompareLoadingBanner,
  CompareSelectionBanner,
} from "../../components/project/CompareSelectionBanner";
import { pollCompareProgress } from "../../lib/compare-progress";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState } from "@/components/ui/EmptyState";

const VendorChart = dynamic(() => import("../../components/VendorChart"), {
  ssr: false,
  loading: () => (
    <div className="h-80 w-full flex items-center justify-center text-gray-400 text-sm">
      Loading chart…
    </div>
  ),
});

/** True when report text is an error payload, not an AI recommendation. */
function isErrorReport(report: string): boolean {
  const t = report.trim();
  return t.startsWith("❌") || t.startsWith("Error:");
}

/** Expired / unknown backend job — common after reload with a stale session_id in the URL. */
function isStaleSessionMessage(message: string): boolean {
  const m = message.toLowerCase();
  return (
    m.includes("no job found") ||
    m.includes("job not found") ||
    m.includes("may have expired")
  );
}


// Main export wrapped in Suspense to fix the Next.js/useSearchParams error
export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[60vh] gap-3">
          <div className="w-8 h-8 border-2 border-stone-200 border-t-[var(--accent)] rounded-full animate-spin" />
          <p className="text-sm text-stone-500">Loading QuoteSense…</p>
        </div>
      }
    >
      <QuoteSenseContent />
    </Suspense>
  );
}

function QuoteSenseContent() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuth();
  const searchParams = useSearchParams();
  const qp = searchParams ?? new URLSearchParams();
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("Starting analysis…");
  const [loadingProgress, setLoadingProgress] = useState<{ processed: number; total: number }>({
    processed: 0,
    total: 0,
  });
  const [progressStage, setProgressStage] = useState<CompareProgressStage>("");
  
  const [report, setReport] = useState("");
  const [chartData, setChartData] = useState<any[]>([]);
  
  // Matrix Table State
  const [tableData, setTableData] = useState<any[]>([]);
  const [vendors, setVendors] = useState<string[]>([]);
  const [vendorMeta, setVendorMeta] = useState<Record<string, any>>({});

  // Chat State Variables
  const [sessionId, setSessionId] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState<{role: string, content: string}[]>([]);
  const [isChatting, setIsChatting] = useState(false);
  const loadingRef = useRef(false);
  const pollingActiveRef = useRef(false);
  const partialAppliedRef = useRef(false);
  const projectCompareStartedRef = useRef(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const selectedQuoteIds = useMemo(() => {
    const raw = qp.get("quotes");
    if (!raw) return [];
    return clampQuoteIds(raw.split(",").filter(Boolean));
  }, [qp]);

  const selectedQuoteIdsKey = selectedQuoteIds.join(",");

  const projectIdParam = qp.get("projectId");
  const sessionIdFromUrl = qp.get("session_id");
  const sourceParam = qp.get("source");

  const compareRunKey = useMemo(() => {
    if (!projectIdParam || !isValidCompareCount(selectedQuoteIds.length)) return "";
    return `${projectIdParam}:${selectedQuoteIdsKey}`;
  }, [projectIdParam, selectedQuoteIdsKey, selectedQuoteIds.length]);

  const lane = useMemo(
    () =>
      getCompareLane({
        sessionIdFromUrl,
        sourceParam,
        projectId: projectIdParam,
        selectedQuoteIds,
      }),
    [sessionIdFromUrl, sourceParam, projectIdParam, selectedQuoteIds]
  );

  const isIntegratedLane = lane === "integrated";
  const canShowPdfUpload = showPdfUpload(lane);
  const standalonePdfLocked =
    lane === "standalone" &&
    !STANDALONE_PDF_UPLOAD_ENABLED &&
    !sessionId &&
    !tableData.length;

  const vendorLabels = useMemo(
    () => buildVendorLabels(vendors, vendorMeta),
    [vendors, vendorMeta]
  );

  const getBackendUrl = () =>
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8001";

  /** Drop session_id from the URL so a reload does not re-poll an expired job. */
  const clearCompareSessionFromUrl = () => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (!params.has("session_id")) return;
    params.delete("session_id");
    const qs = params.toString();
    window.history.replaceState(null, "", qs ? `/compare?${qs}` : "/compare");
  };

  const resetStaleCompareSession = () => {
    pollingActiveRef.current = false;
    partialAppliedRef.current = false;
    projectCompareStartedRef.current = false;
    setActiveJobId(null);
    setSessionId("");
    setReport("");
    setLoading(false);
    clearCompareSessionFromUrl();
  };

  const handleGoBack = () => {
    if (projectIdParam) {
      router.push(`/project/${encodeURIComponent(projectIdParam)}`);
      return;
    }
    router.push("/");
  };

  const handleNewComparison = () => {
    resetStaleCompareSession();
    resetSelection();
    router.replace("/compare");
  };

  const processComparisonData = (data: any) => {
    if (data.report) {
      setReport(data.report);
      setChartData(data.chartData || []);
      setTableData(data.tableData || []);
      setVendors(data.vendors || []);
      setVendorMeta(data.vendorMeta || {});
      setSessionId(data.session_id);
      setChatHistory([
        { role: "ai", content: "Hi! I'm your QuoteSense Assistant. I've analyzed the synced quotes. Ask me anything..." }
      ]);
    } else {
      setReport(`Error: Could not generate report. Backend sent: ${JSON.stringify(data)}`);
    }
  };

  // Render the chart + table from the partial matrix while the recommendation
  // is still being generated. Does NOT set the report or chat greeting yet.
  const applyPartialData = (data: any) => {
    if (!data) return;
    setChartData(data.chartData || []);
    setTableData(data.tableData || []);
    setVendors(data.vendors || []);
    setVendorMeta(data.vendorMeta || {});
    if (data.session_id) setSessionId(data.session_id);
  };

  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);

  useEffect(() => {
    const autoSessionId = qp.get("session_id");
    const isProjectCompare =
      Boolean(projectIdParam) && selectedQuoteIds.length >= 2;

    // Project lane owns session_id polling — do not call get-comparison here.
    if (isProjectCompare) return;

    if (!autoSessionId || sessionId || activeJobId) return;

    // Integrated MongoDB lane: one-shot fetch of stored comparison.
    if (sourceParam === "integrated") {
      const fetchAutoData = async () => {
        setLoading(true);
        setLoadingMessage("Loading your synced comparison…");
        try {
          const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8001";
          const res = await fetch(`${backendUrl}/api/get-comparison?session_id=${autoSessionId}`);
          const data = await res.json();
          processComparisonData(data);
        } catch (err) {
          console.error("Auto-sync failed:", err);
        } finally {
          setLoading(false);
        }
      };

      fetchAutoData();
      return;
    }

    // Standalone PDF / async job: resume progress polling (e.g. after refresh).
    setSessionId(autoSessionId);
    setActiveJobId(autoSessionId);
    setLoading(true);
    pollingActiveRef.current = true;
    partialAppliedRef.current = false;
  }, [
    sessionIdFromUrl,
    sessionId,
    activeJobId,
    projectIdParam,
    selectedQuoteIds.length,
    sourceParam,
  ]);

  // Resume an in-flight project job after refresh (session_id already in URL).
  useEffect(() => {
    if (lane !== "project" || !compareRunKey) return;
    if (!sessionIdFromUrl || activeJobId) return;

    setActiveJobId(sessionIdFromUrl);
    setSessionId(sessionIdFromUrl);
    projectCompareStartedRef.current = true;
  }, [lane, compareRunKey, sessionIdFromUrl, activeJobId]);

  // Project lane: resolve payloads → start async MongoDB compare job.
  useEffect(() => {
    if (lane !== "project" || !compareRunKey) return;

    const projectId = projectIdParam;
    if (!projectId) return;

    if (sessionIdFromUrl || activeJobId || projectCompareStartedRef.current) return;

    projectCompareStartedRef.current = true;

    (async () => {
      setLoading(true);
      setLoadingMessage("Building comparison matrix…");
      setReport("");
      setChartData([]);
      setTableData([]);
      setVendors([]);
      setVendorMeta({});
      partialAppliedRef.current = false;

      try {
        const quotesResult = await resolveQuotesForCompare(
          projectId,
          selectedQuoteIds,
          getAuthUserId(user)
        );

        if (!quotesResult.ok) {
          setReport(`❌ ${quotesResult.message}`);
          setLoading(false);
          return;
        }

        setLoadingMessage(
          `Sending ${quotesResult.quotes.length} quotes for analysis…`
        );
        setLoadingProgress({
          processed: 0,
          total: quotesResult.quotes.length,
        });

        const job = await startMongoCompareJob(
          quotesResult.quotes,
          undefined,
          quotesResult.mongoId
        );

        if (!job.ok) {
          setReport(`❌ ${job.message}`);
          setLoading(false);
          return;
        }

        setSessionId(job.session_id);
        setActiveJobId(job.session_id);

        // Update URL for refresh/share without re-running this effect.
        if (typeof window !== "undefined") {
          const params = new URLSearchParams(window.location.search);
          params.set("session_id", job.session_id);
          window.history.replaceState(null, "", `/compare?${params.toString()}`);
        }
      } catch (err) {
        setReport(`❌ ${err instanceof Error ? err.message : "Comparison failed."}`);
        setLoading(false);
      }
    })();
  }, [lane, compareRunKey, activeJobId, sessionIdFromUrl, projectIdParam, selectedQuoteIds, user]);

  // Poll progress for the active comparison job (separate effect — not cancelled on URL tweak).
  useEffect(() => {
    if (!activeJobId) return;

    let cancelled = false;
    const sid = activeJobId;

    (async () => {
      setLoading(true);
      pollingActiveRef.current = true;

      try {
        // Same-origin /api/progress proxy → Render (do not poll NEXT_PUBLIC host directly)
        await runPollForSession(sid);
      } catch (err) {
        if (!cancelled) {
          setReport(`❌ ${err instanceof Error ? err.message : "Comparison failed."}`);
        }
      } finally {
        pollingActiveRef.current = false;
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      pollingActiveRef.current = false;
    };
  }, [activeJobId]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);

      setFiles((prevFiles) => {
        const combinedFiles = [...prevFiles, ...newFiles];
        const uniqueFiles = combinedFiles.filter((file, index, self) =>
          index === self.findIndex((f) => f.name === file.name && f.size === file.size)
        );
        if (uniqueFiles.length > MAX_COMPARE_QUOTES) {
          alert(`You can compare at most ${MAX_COMPARE_QUOTES} PDF quotes at a time.`);
        }
        return uniqueFiles.slice(0, MAX_COMPARE_QUOTES);
      });

      e.target.value = "";
    }
  };

  const resetSelection = () => {
    setFiles([]);
    setReport("");
    setChartData([]);
    setTableData([]); 
    setVendors([]);   
    setVendorMeta({});
    setSessionId("");
    setActiveJobId(null);
    setChatHistory([]);
    projectCompareStartedRef.current = false;
    partialAppliedRef.current = false;
    pollingActiveRef.current = false;
  };

  const handleDownloadPdf = async () => {
    if (tableData.length === 0 || vendors.length === 0) return;
    await downloadComparisonPdf(tableData, vendors, vendorLabels, vendorMeta);
  };

  const handleProgressTick = (data: {
    message?: string;
    processed?: number;
    total?: number;
    stage?: string;
    partial?: Record<string, unknown>;
  }) => {
    if (data.stage) setProgressStage(data.stage as CompareProgressStage);
    if (data.message) setLoadingMessage(data.message);
    if (typeof data.processed === "number") {
      setLoadingProgress({ processed: data.processed, total: data.total || 0 });
    }
    if (data.partial && !partialAppliedRef.current) {
      applyPartialData(data.partial);
      partialAppliedRef.current = true;
      setLoadingMessage(
        data.message || "Matrix ready — finishing recommendation…"
      );
    }
  };

  const runPollForSession = async (sid: string) => {
    const result = await pollCompareProgress({
      sessionId: sid,
      shouldContinue: () => pollingActiveRef.current,
      hasPartialApplied: () => partialAppliedRef.current,
      onTick: handleProgressTick,
    });

    if (result.outcome === "done") {
      processComparisonData(result.result);
      setLoading(false);
      return;
    }
    if (result.outcome === "error" || result.outcome === "unknown") {
      // Stale session_id on reload (job expired on backend) — return to fresh upload UI.
      if (!partialAppliedRef.current && isStaleSessionMessage(result.message)) {
        resetStaleCompareSession();
        return;
      }
      setReport(`❌ ${result.message}`);
      setLoading(false);
      return;
    }
    if (result.outcome === "cancelled") {
      setLoading(false);
      return;
    }

    // Timeout — if matrix already visible, keep it and explain; don't wipe results.
    if (partialAppliedRef.current) {
      setReport(
        "⏳ Analysis is still running on the backend. Your comparison matrix is shown above — " +
          "refresh this page in a minute or click Compare again with the same files to fetch the final report."
      );
      setLoading(false);
      return;
    }

    setReport(
      "🕒 PDF extraction is taking longer than usual (large quotes can take 15+ minutes). " +
        "Keep the backend running and try Compare again — or use fewer/smaller PDFs."
    );
    setLoading(false);
  };

  const handleUpload = async () => {
    if (!isValidCompareCount(files.length)) {
      alert(
        `Please upload ${MIN_COMPARE_QUOTES}–${MAX_COMPARE_QUOTES} vendor PDFs to run a comparison.`
      );
      return;
    }

    setLoading(true);
    setReport("");
    setChartData([]);
    setTableData([]);
    setVendors([]);
    setVendorMeta({});
    setChatHistory([]);
    setLoadingMessage("Uploading quotes…");
    setLoadingProgress({ processed: 0, total: files.length });
    partialAppliedRef.current = false;
    setProgressStage("queued");
    pollingActiveRef.current = true;

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    const backendUrl = getBackendUrl();
    let jobStarted = false;

    try {
      try {
        // Quick reachability probe — 8s is enough locally; Render cold-starts may need longer.
        await fetch(`${backendUrl}/api/health`, {
          signal: AbortSignal.timeout(8000),
        });
      } catch {
        setReport(
          `❌ Cannot reach the backend at ${backendUrl}. Start it from the backend folder:\n\n` +
            `cd backend\nuvicorn main:app --port 8001 --host 127.0.0.1\n\n` +
            `(Do not use backend.main:app when you are already inside backend/.)`
        );
        return;
      }

      const response = await fetch(`${backendUrl}/api/compare-quotes`, {
        method: "POST",
        body: formData,
      });
      const startData = await response.json();

      if (!startData.session_id) {
        setReport(`❌ Backend did not start the job: ${JSON.stringify(startData)}`);
        return;
      }

      setSessionId(startData.session_id);
      setLoadingMessage(startData.message || "Processing started…");
      setActiveJobId(startData.session_id);
      jobStarted = true;

      if (typeof window !== "undefined") {
        const params = new URLSearchParams(window.location.search);
        params.set("session_id", startData.session_id);
        window.history.replaceState(null, "", `/compare?${params.toString()}`);
      }
    } catch (error: any) {
      if (error.message === "Failed to fetch") {
        setReport(
          `❌ Connection lost to ${backendUrl}. The backend may have crashed — check the terminal running uvicorn.`
        );
      } else {
        setReport(`❌ Browser Error: ${error.message}`);
      }
      console.error("Full Error Details:", error);
    } finally {
      if (!jobStarted) {
        pollingActiveRef.current = false;
        setLoading(false);
      }
    }
  };

  const sendChatMessage = async (userMsg: string) => {
    if (!userMsg.trim() || !sessionId || isChatting) return;
    setChatInput("");
    setChatHistory((prev) => [...prev, { role: "user", content: userMsg }]);
    setIsChatting(true);

    try {
      const res = await fetch(`${getBackendUrl()}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: userMsg }),
      });

      const data = await res.json();
      const aiMessage = data.reply
        ? data.reply
        : `Could not get a reply: ${JSON.stringify(data)}`;
      setChatHistory((prev) => [...prev, { role: "ai", content: aiMessage }]);
    } catch (error) {
      setChatHistory((prev) => [
        ...prev,
        { role: "ai", content: `Connection error: ${error}` },
      ]);
    } finally {
      setIsChatting(false);
    }
  };

  const handleChatSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    await sendChatMessage(chatInput);
  };

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-stone-200 border-t-[var(--accent)] rounded-full animate-spin" />
      </div>
    );
  }

  const hasResults = tableData.length > 0;
  const showErrorCard = Boolean(report && isErrorReport(report) && !hasResults);

  return (
    <main className="pb-14 text-stone-800">
      <div className="qs-container py-6 md:py-8 space-y-6">
        <ComparePageNav
          projectId={projectIdParam}
          hasResults={hasResults}
          onNewComparison={handleNewComparison}
        />

        {(lane === "project" || lane === "integrated") && (
          <PageHeader
            eyebrow="Comparison"
            title={
              projectIdParam
                ? `Project ${projectIdParam}`
                : "Vendor quote comparison"
            }
            description={
              selectedQuoteIds.length > 0
                ? `${selectedQuoteIds.length} quotes selected · ${
                    loading && !hasResults
                      ? "Building analysis…"
                      : hasResults
                        ? "Review totals, market estimates, and AI guidance."
                        : "Preparing comparison."
                  }`
                : "Analyze vendor pricing with market context and AI recommendation."
            }
            actions={
              hasResults ? (
                <>
                  <button
                    type="button"
                    onClick={handleDownloadPdf}
                    className="qs-btn qs-btn-secondary"
                  >
                    Export PDF
                  </button>
                  <button
                    type="button"
                    onClick={handleGoBack}
                    className="qs-btn qs-btn-ghost"
                  >
                    {projectIdParam ? "Back to project" : "All projects"}
                  </button>
                </>
              ) : null
            }
          />
        )}

        {lane === "project" && selectedQuoteIds.length > 0 && (
          <CompareSelectionBanner
            quoteIds={selectedQuoteIds}
            projectId={projectIdParam}
          />
        )}

        {lane === "project" && loading && !tableData.length && (
          <>
            <CompareLoadingBanner message={loadingMessage} />
            <CompareLoadingPanel
              message={loadingMessage}
              processed={loadingProgress.processed}
              total={loadingProgress.total}
              stage={progressStage}
            />
          </>
        )}

        {(lane === "project" || lane === "integrated") &&
          tableData.length > 0 &&
          loading && (
            <p className="text-xs text-stone-500 text-center">
              Almost done — preparing your summary…
            </p>
          )}

        {isIntegratedLane && loading && !tableData.length && (
          <>
            <CompareLoadingBanner message={loadingMessage} />
            <CompareLoadingPanel
              message={loadingMessage}
              processed={loadingProgress.processed}
              total={loadingProgress.total}
              stage={progressStage}
            />
          </>
        )}

        <StandalonePdfCompareGuard active={standalonePdfLocked} />

        {canShowPdfUpload && !sessionId && !tableData.length && (
          <PageHeader
            eyebrow="Standalone compare"
            title="Compare vendor quotes"
            description="Upload 2–3 vendor PDFs for a standalone comparison, or pick quotes from a project."
          />
        )}

        {canShowPdfUpload && (
          <div className="qs-card p-6 md:p-8">
            <div className="flex items-center justify-between mb-5 gap-3">
              <div>
                <h2 className="qs-section-title">Upload vendor quotes</h2>
                <p className="qs-section-sub">
                  PDF only · {MIN_COMPARE_QUOTES}–{MAX_COMPARE_QUOTES} files
                </p>
              </div>
              {files.length > 0 && !loading && (
                <button
                  type="button"
                  onClick={resetSelection}
                  className="qs-btn qs-btn-danger !py-2"
                >
                  Clear
                </button>
              )}
            </div>

            <label className="block">
              <span className="sr-only">Choose PDF files</span>
              <input
                type="file"
                multiple
                accept=".pdf"
                onChange={handleFileChange}
                disabled={loading}
                className="block w-full text-sm text-stone-500 file:mr-4 file:py-2.5 file:px-5 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-[var(--accent-soft)] file:text-[var(--accent)] hover:file:bg-orange-100 cursor-pointer disabled:cursor-not-allowed"
              />
            </label>

            {files.length > 0 && (
              <div className="mt-5 p-4 bg-stone-50 rounded-lg border border-stone-100">
                <p className="text-sm font-semibold text-stone-700 mb-2">
                  Selected quotes ({files.length})
                </p>
                <ul className="space-y-1.5 list-none">
                  {files.map((file, index) => (
                    <li
                      key={`${file.name}-${index}`}
                      className="text-sm text-stone-800 bg-white border border-stone-200 px-3 py-2 rounded-md"
                    >
                      {file.name}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <button
              type="button"
              onClick={handleUpload}
              disabled={loading || !isValidCompareCount(files.length)}
              className="qs-btn qs-btn-primary mt-6 w-full !py-3"
            >
              {loading
                ? "Analyzing quotes…"
                : `Compare ${files.length > 1 ? `${files.length} ` : ""}quotes`}
            </button>

            {loading && (
              <CompareLoadingPanel
                message={loadingMessage}
                processed={loadingProgress.processed}
                total={loadingProgress.total}
                stage={progressStage}
                isPdfLane
              />
            )}
          </div>
        )}

        {loading && tableData.length > 0 && canShowPdfUpload && (
          <p className="text-sm text-center text-emerald-800 bg-[var(--success-soft)] border border-[var(--success-border)] rounded-lg py-2.5 px-4">
            Comparison matrix is ready below — finishing the AI recommendation…
          </p>
        )}

        {showErrorCard && (
          <ErrorState
            title="Comparison failed"
            description={report.replace(/^❌\s*/, "").replace(/^Error:\s*/, "")}
            action={
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleNewComparison}
                  className="qs-btn qs-btn-primary"
                >
                  Try again
                </button>
                <button
                  type="button"
                  onClick={handleGoBack}
                  className="qs-btn qs-btn-secondary"
                >
                  {projectIdParam ? "Back to project" : "All projects"}
                </button>
              </div>
            }
          />
        )}

        {chartData.length > 0 && vendors.length > 0 && (
          <VendorSummary
            chartData={chartData}
            vendors={vendors}
            tableData={tableData}
            meta={vendorMeta}
          />
        )}

        {report && tableData.length > 0 && !isErrorReport(report) && (
          <RecommendationView text={report} />
        )}

        {chartData.length > 0 && (
          <section className="qs-card p-5 md:p-6">
            <h2 className="qs-section-title">Cost comparison</h2>
            <p className="qs-section-sub mb-4">
              Grand total across all quoted services per vendor.
            </p>
            <VendorChart data={chartData} meta={vendorMeta} />
          </section>
        )}

        {tableData.length > 0 && (
          <ComparisonMatrix
            tableData={tableData}
            vendors={vendors}
            vendorMeta={vendorMeta}
            onDownloadPdf={handleDownloadPdf}
          />
        )}

        {tableData.length > 0 && vendors.length > 0 && (
          <VendorInsights
            tableData={tableData}
            vendors={vendors}
            meta={vendorMeta}
          />
        )}

        {sessionId && tableData.length > 0 && (
          <CompareChat
            sessionId={sessionId}
            chatHistory={chatHistory}
            chatInput={chatInput}
            isChatting={isChatting}
            onInputChange={setChatInput}
            onSubmit={handleChatSubmit}
            onSuggestion={(text) => {
              void sendChatMessage(text);
            }}
          />
        )}

        {report && tableData.length > 0 && !isErrorReport(report) && (
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              type="button"
              onClick={handleGoBack}
              className="qs-btn qs-btn-primary flex-1 !py-3"
            >
              {projectIdParam ? "← Back to project" : "← All projects"}
            </button>
            <button
              type="button"
              onClick={handleNewComparison}
              className="qs-btn qs-btn-secondary !py-3"
            >
              New comparison
            </button>
          </div>
        )}
      </div>
    </main>
  );
}