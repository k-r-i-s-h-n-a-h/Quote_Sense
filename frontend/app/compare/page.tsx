"use client";

import React, { useState, useEffect, useRef, useMemo, Suspense } from "react";
import dynamic from "next/dynamic";
import { useSearchParams, useRouter } from "next/navigation";
import CompareLoadingPanel, {
  type CompareProgressStage,
} from "../../components/CompareLoadingPanel";
import VendorInsights from "../../components/VendorInsights";
import RecommendationView from "../../components/RecommendationView";
import { buildVendorLabels, formatInrFull, formatQuoteCountLabel, priceVsBaseline } from "../../lib/format";
import {
  groupTableData,
  sumSubServiceRow,
  lineItemDescription,
} from "../../lib/compare-matrix";
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
} from "../../components/project/CompareSelectionBanner";
import { pollCompareProgress } from "../../lib/compare-progress";

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
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen">Loading QuoteSense...</div>}>
      <QuoteSenseContent />
    </Suspense>
  );
}

function QuoteSenseContent() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuth();
  const searchParams = useSearchParams();
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
  const chatEndRef = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const pollingActiveRef = useRef(false);
  const partialAppliedRef = useRef(false);
  const projectCompareStartedRef = useRef(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  const selectedQuoteIds = useMemo(() => {
    const raw = searchParams.get("quotes");
    if (!raw) return [];
    return clampQuoteIds(raw.split(",").filter(Boolean));
  }, [searchParams]);

  const selectedQuoteIdsKey = selectedQuoteIds.join(",");

  const projectIdParam = searchParams.get("projectId");
  const sessionIdFromUrl = searchParams.get("session_id");
  const sourceParam = searchParams.get("source");

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
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);

  useEffect(() => {
    const autoSessionId = searchParams.get("session_id");
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
    searchParams,
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
    const backendUrl = getBackendUrl();

    (async () => {
      setLoading(true);
      pollingActiveRef.current = true;

      try {
        await runPollForSession(sid, backendUrl);
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

  const runPollForSession = async (sid: string, backendUrl: string) => {
    const result = await pollCompareProgress({
      sessionId: sid,
      backendUrl,
      shouldContinue: () => pollingActiveRef.current,
      hasPartialApplied: () => partialAppliedRef.current,
      onTick: handleProgressTick,
    });

    // #region agent log
    fetch('http://127.0.0.1:7880/ingest/fae56c38-48bc-450d-a803-35ac016bc76b',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'b7c34a'},body:JSON.stringify({sessionId:'b7c34a',location:'compare/page.tsx:poll',message:'poll finished',data:{outcome:result.outcome,sessionId:sid,hasPartial:partialAppliedRef.current},timestamp:Date.now(),hypothesisId:'H3'})}).catch(()=>{});
    // #endregion

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

  const handleChatSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!chatInput.trim() || !sessionId) return;

    const userMsg = chatInput;
    setChatInput("");
    setChatHistory(prev => [...prev, { role: "user", content: userMsg }]);
    setIsChatting(true);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: userMsg }), 
      });
      
      const data = await res.json();
      const aiMessage = data.reply ? data.reply : `⚠️ Backend error: ${JSON.stringify(data)}`;
      setChatHistory(prev => [...prev, { role: "ai", content: aiMessage }]);
    } catch (error) {
      setChatHistory(prev => [...prev, { role: "ai", content: `❌ Connection error: ${error}` }]);
    } finally {
      setIsChatting(false);
    }
  };

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <main className="bg-[#f8fafc] p-6 md:p-10 font-sans text-slate-800">
      <div className="max-w-5xl mx-auto space-y-8">

        <ComparePageNav
          projectId={projectIdParam}
          hasResults={tableData.length > 0}
          onNewComparison={handleNewComparison}
        />

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
            <p className="text-xs text-slate-500 text-center -mt-4">
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
          <div className="text-center space-y-3 pt-2">
            <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
              Compare vendor quotes
            </h1>
            <p className="text-slate-500 text-sm md:text-base max-w-xl mx-auto">
              Upload vendor PDFs for a standalone comparison, or pick quotes from a project.
            </p>
          </div>
        )}

        {canShowPdfUpload && (
        <div className="qs-card p-8">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-xl font-semibold">Upload vendor quotes (PDF)</h2>
            {files.length > 0 && !loading && (
                <button onClick={resetSelection} className="text-sm text-red-600 hover:underline">Clear</button>
            )}
          </div>
          
          <input 
            type="file" 
            multiple 
            accept=".pdf"
            onChange={handleFileChange}
            disabled={loading}
            className="block w-full text-sm text-gray-500 file:mr-4 file:py-2.5 file:px-5 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer disabled:cursor-not-allowed"
          />
          
          {files.length > 0 && (
            <div className="mt-5 p-4 bg-gray-50 rounded-lg border border-gray-100">
              <p className="text-sm font-semibold text-gray-700 mb-2">Selected Quotes ({files.length}):</p>
              <ul className="space-y-1.5 list-none">
                {files.map((file, index) => (
                  <li key={index} className="text-sm text-blue-800 bg-blue-50 px-3 py-1.5 rounded flex items-center gap-2">
                    📄 {file.name}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={loading || !isValidCompareCount(files.length)}
            className={`mt-6 w-full py-3 rounded-lg font-bold text-white transition-colors flex items-center justify-center gap-2 ${
              loading || !isValidCompareCount(files.length)
                ? "bg-gray-400 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-700"
            }`}
          >
            {loading ? "Analyzing quotes…" : `Compare ${files.length > 1 ? files.length + " " : ""}Quotes Now`}
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
          <p className="text-sm text-center text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg py-2.5 px-4">
            ✓ Comparison matrix is ready below — finishing the AI recommendation…
          </p>
        )}

        {/* Visual Chart Section */}
        {chartData.length > 0 && (
          <div className="qs-card p-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <h2 className="text-xl font-semibold text-slate-900 mb-1">Total Cost Comparison</h2>
            <p className="text-sm text-slate-500 mb-6">Grand total across all quoted services per vendor.</p>
            <VendorChart data={chartData} meta={vendorMeta} />
          </div>
        )}

       {tableData.length > 0 && (
          <div className="qs-card p-6 md:p-8 animate-in fade-in slide-in-from-bottom-4 duration-700 overflow-hidden">
            <div className="flex items-center justify-between mb-6 px-1">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">Comparison Matrix</h2>
                <p className="text-sm text-slate-500 mt-1">
                  Line items with sub-service totals per vendor.
                </p>
              </div>
              <button
                onClick={handleDownloadPdf}
                title="Download comparison as PDF"
                className="inline-flex items-center gap-2 bg-blue-900 text-white text-sm font-semibold px-4 py-2 rounded-lg hover:bg-black transition-all shadow-sm"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Download PDF
              </button>
            </div>
            
            <div className="overflow-x-auto border border-slate-200 rounded-lg qs-table-scroll max-h-[70vh]">
              <table className="w-full text-left border-collapse min-w-[900px]">
                <thead>
                  <tr className="text-slate-500 uppercase text-[10px] font-bold tracking-widest">
                    <th className="p-4 border-b border-slate-200 w-[250px] bg-slate-50">Service Description</th>
                    <th className="p-4 border-b border-slate-200 text-right w-[140px] bg-indigo-50/60 text-indigo-700">
                      <div>Market Est.</div>
                      <div className="text-[9px] font-normal normal-case tracking-normal text-indigo-400 mt-0.5 leading-tight">
                        Historical avg × item qty
                      </div>
                      <div className="text-[9px] font-normal normal-case tracking-normal text-indigo-300 mt-0.5 leading-tight">
                        (all past sessions)
                      </div>
                    </th>
                    {vendors.map((vendor, i) => {
                      const info = vendorLabels[vendor];
                      const meta = vendorMeta[vendor] || {};
                      return (
                        <th key={i} className="p-4 border-b border-slate-200 text-right align-top max-w-[170px] bg-slate-50">
                          <div className="ml-auto max-w-[170px]" title={info?.full ?? vendor}>
                            <div className="text-[11px] font-bold leading-snug normal-case tracking-normal text-gray-800 line-clamp-2 break-words">
                              {info?.company ?? vendor.split(" (")[0]}
                            </div>
                            {info?.variant && (
                              <div className="text-[10px] font-semibold text-blue-700 normal-case tracking-normal mt-0.5 line-clamp-1">
                                {info.variant}
                              </div>
                            )}
                            {(info?.quoteNumber || info?.quoteDate || meta.quote_date) && (
                              <div className="text-[9px] font-normal text-gray-400 normal-case tracking-normal mt-0.5">
                                {info?.quoteNumber ? `#${info.quoteNumber}` : ""}
                                {info?.quoteNumber && (info?.quoteDate || meta.quote_date) ? " · " : ""}
                                {info?.quoteDate || meta.quote_date || ""}
                              </div>
                            )}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                
                <tbody className="divide-y divide-slate-100">
                  {groupTableData(tableData).map((cat, ci) => (
                    <React.Fragment key={ci}>
                      <tr className="bg-slate-900/[0.03]">
                        <td colSpan={vendors.length + 2} className="p-3 pl-4 text-sm font-bold text-slate-800 uppercase tracking-wider border-y border-slate-200">
                          {cat.category}
                        </td>
                      </tr>

                      {cat.subs.map((sub, si) => {
                        const subTotals = sumSubServiceRow(sub.rows, vendors);
                        const subBaseline = subTotals.moving_average;
                        const isLastInCategory = si === cat.subs.length - 1;

                        return (
                          <React.Fragment key={si}>
                            {si > 0 && (
                              <tr aria-hidden="true">
                                <td
                                  colSpan={vendors.length + 2}
                                  className="h-3 p-0 bg-[#f8fafc] border-0"
                                />
                              </tr>
                            )}

                            <tr className="bg-slate-200/70 border-y-2 border-slate-300">
                              <td className="py-3 pl-5 pr-4 border-l-4 border-[#c04a00]">
                                <div className="text-xs font-extrabold text-slate-800 uppercase tracking-wide">
                                  {sub.sub}
                                </div>
                              </td>
                              <td
                                className="px-3 py-3 text-right align-middle bg-indigo-100/50 border-r border-slate-300"
                                title="Sum of all line-item market estimates for this service (historical avg rate × avg qty per item, from all past sessions)"
                              >
                                {subBaseline > 0 ? (
                                  <div className="text-base font-extrabold text-indigo-900 tabular-nums">
                                    {formatInrFull(subBaseline)}
                                  </div>
                                ) : (
                                  <span className="text-sm text-slate-400">—</span>
                                )}
                              </td>
                              {vendors.map((vendor, vIdx) => {
                                const value = Number(subTotals[vendor]) || 0;
                                const vs = priceVsBaseline(value, subBaseline);
                                return (
                                  <td
                                    key={vIdx}
                                    className={`px-3 py-3 text-right tabular-nums align-middle ${
                                      value === 0 ? "opacity-50" : ""
                                    }`}
                                  >
                                    {value === 0 ? (
                                      <span className="text-sm font-semibold text-rose-400 italic">N/A</span>
                                    ) : (
                                      <span
                                        className={`text-base font-extrabold ${
                                          vs === "below"
                                            ? "text-emerald-800"
                                            : vs === "above"
                                              ? "text-amber-800"
                                              : "text-slate-900"
                                        }`}
                                      >
                                        {formatInrFull(value)}
                                      </span>
                                    )}
                                  </td>
                                );
                              })}
                            </tr>

                            {sub.rows.map((row, idx) => {
                              const baseline = Number(row.moving_average ?? row.market_average) || 0;
                              const weight = Number(row.moving_weight) || 0;
                              const { title, room } = lineItemDescription(row);
                              const isLastLineItem = idx === sub.rows.length - 1;
                              return (
                                <tr
                                  key={idx}
                                  className={`hover:bg-slate-50/70 transition-colors group bg-white ${
                                    isLastLineItem && !isLastInCategory
                                      ? "border-b-2 border-slate-200"
                                      : ""
                                  }`}
                                >
                                  <td className="py-2.5 pl-12 pr-4 max-w-[320px] border-l-4 border-transparent">
                                    <div className="text-sm font-medium text-slate-800 leading-tight">
                                      {title}
                                    </div>
                                    {room && (
                                      <div className="text-[10px] text-slate-400 mt-0.5 uppercase tracking-wide">
                                        {room}
                                      </div>
                                    )}
                                  </td>
                                  <td
                                    className="px-4 py-2.5 text-right align-top bg-indigo-50/15 border-r border-indigo-100/40"
                                    title="Market Est. = historical avg rate × avg quantity for this item, built from all past uploaded quotes — not just the vendors in this comparison"
                                  >
                                    {baseline > 0 ? (
                                      <>
                                        <div className="text-sm font-medium text-indigo-700 tabular-nums">
                                          {formatInrFull(baseline)}
                                        </div>
                                        {weight > 0 && (
                                          <div
                                            className="text-[10px] text-slate-400 mt-0.5"
                                            title={`Built from ${weight} quote${weight === 1 ? "" : "s"} across all past sessions`}
                                          >
                                            {formatQuoteCountLabel(weight)}
                                          </div>
                                        )}
                                        {(() => {
                                          const ratePerUnit = Number((row as any).market_rate_per_unit) || 0;
                                          const pm = String((row as any).pricing_method || "");
                                          if (ratePerUnit > 0 && pm) {
                                            return (
                                              <div className="text-[9px] text-indigo-300 mt-0.5 tabular-nums" title="Historical avg market rate per unit">
                                                ₹{ratePerUnit.toLocaleString("en-IN")}/{pm}
                                              </div>
                                            );
                                          }
                                          return null;
                                        })()}
                                      </>
                                    ) : (
                                      <span className="text-sm text-slate-300">—</span>
                                    )}
                                  </td>
                                  {vendors.map((vendor, vIdx) => {
                                    const value = row[vendor];
                                    const vs = priceVsBaseline(Number(value), baseline);
                                    return (
                                      <td
                                        key={vIdx}
                                        className={`px-4 py-2.5 text-right tabular-nums ${
                                          value === 0 ? "opacity-50" : ""
                                        }`}
                                      >
                                        {value === 0 ? (
                                          <span className="text-sm font-medium text-rose-300 italic">N/A</span>
                                        ) : (
                                          <span
                                            className={`text-sm font-medium ${
                                              vs === "below"
                                                ? "text-emerald-700"
                                                : vs === "above"
                                                  ? "text-amber-700"
                                                  : "text-slate-700"
                                            }`}
                                          >
                                            {formatInrFull(Number(value))}
                                          </span>
                                        )}
                                      </td>
                                    );
                                  })}
                                </tr>
                              );
                            })}
                          </React.Fragment>
                        );
                      })}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-slate-400 mt-3 px-1">
              <span className="text-emerald-700 font-medium">Green</span> = below market est. ·{" "}
              <span className="text-amber-700 font-medium">Amber</span> = above market est. ·{" "}
              <span className="text-indigo-500 font-medium">Market Est.</span> = historical avg rate × item qty, built from all past quote sessions — not just the vendors in this comparison. Hover the column for details.
            </p>
          </div>
        )}

        {/* Interactive Insights (between the matrix and the AI recommendation) */}
        {tableData.length > 0 && vendors.length > 0 && (
          <VendorInsights tableData={tableData} vendors={vendors} meta={vendorMeta} />
        )}

        {/* AI Recommendation — only after a successful comparison with matrix data */}
        {report && tableData.length > 0 && !isErrorReport(report) && (
          <div className="qs-card p-8">
            <h2 className="text-xl font-semibold text-slate-900 mb-1">Expert Recommendation</h2>
            <p className="text-sm text-slate-500 mb-6">AI analysis based on totals, scope, and moving-average baselines.</p>
            <div className="mb-8">
              <RecommendationView text={report} />
            </div>
            
            <div className="pt-6 border-t border-gray-100 flex flex-col sm:flex-row gap-4">
              <button
                onClick={handleGoBack}
                className="flex-1 bg-blue-900 text-white py-3 rounded-lg font-bold hover:bg-black transition-all flex items-center justify-center gap-2 shadow-md"
              >
                {projectIdParam ? "← Back to project" : "← All projects"}
              </button>

              <button
                onClick={handleNewComparison}
                className="px-8 py-3 text-gray-600 hover:text-[#c04a00] font-semibold transition-colors border border-slate-200 hover:border-[#c04a00]/30 rounded-lg bg-white"
              >
                New comparison
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}