"use client";

import React, { useState, useEffect, useRef, useMemo, Suspense } from "react";
import dynamic from "next/dynamic";
import { useSearchParams, useRouter } from "next/navigation";
import CompareLoadingPanel from "../../components/CompareLoadingPanel";
import VendorInsights from "../../components/VendorInsights";
import RecommendationView from "../../components/RecommendationView";
import { buildVendorLabels, formatInrFull, priceVsBaseline } from "../../lib/format";
import { downloadComparisonPdf } from "../../lib/download-comparison-pdf";
import { getCompareLane, showPdfUpload } from "../../lib/compare-lane";
import { useAuth } from "@/lib/auth";
import {
  ComparePageNav,
  CompareSelectionBanner,
  IntegratedLoadingBanner,
} from "../../components/project/CompareSelectionBanner";

const VendorChart = dynamic(() => import("../../components/VendorChart"), {
  ssr: false,
  loading: () => (
    <div className="h-80 w-full flex items-center justify-center text-gray-400 text-sm">
      Loading chart…
    </div>
  ),
});

type SubGroup = { sub: string; rows: any[] };
type CatGroup = { category: string; subs: SubGroup[] };

/**
 * Group flat tableData rows into the quote-flow hierarchy:
 *   category -> sub_service -> work-item rows.
 * Backend already pre-sorts rows in quote order, so we just preserve
 * the first-seen order of each category and sub-service.
 */
function groupTableData(rows: any[]): CatGroup[] {
  const cats: CatGroup[] = [];
  const catIdx = new Map<string, number>();
  const subIdx = new Map<string, number>();

  for (const item of rows) {
    const category = item.category || "Other";
    const sub = item.sub_service || "General";

    if (!catIdx.has(category)) {
      catIdx.set(category, cats.length);
      cats.push({ category, subs: [] });
    }
    const cat = cats[catIdx.get(category)!];

    const subKey = `${category}||${sub}`;
    if (!subIdx.has(subKey)) {
      subIdx.set(subKey, cat.subs.length);
      cat.subs.push({ sub, rows: [] });
    }
    cat.subs[subIdx.get(subKey)!].rows.push(item);
  }
  return cats;
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
  const { isAuthenticated, isLoading } = useAuth();
  const searchParams = useSearchParams();
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("Starting analysis…");
  const [loadingProgress, setLoadingProgress] = useState<{ processed: number; total: number }>({
    processed: 0,
    total: 0,
  });
  
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
  const partialAppliedRef = useRef(false);

  const selectedQuoteIds = useMemo(() => {
    const raw = searchParams.get("quotes");
    if (!raw) return [];
    return raw.split(",").filter(Boolean);
  }, [searchParams]);

  const projectIdParam = searchParams.get("projectId");
  const sessionIdFromUrl = searchParams.get("session_id");
  const sourceParam = searchParams.get("source");

  const lane = useMemo(
    () =>
      getCompareLane({
        sessionIdFromUrl,
        sourceParam,
        selectedQuoteIds,
      }),
    [sessionIdFromUrl, sourceParam, selectedQuoteIds]
  );

  const isIntegratedLane = lane === "integrated";
  const canShowPdfUpload = showPdfUpload(lane);

  const vendorLabels = useMemo(
    () => buildVendorLabels(vendors, vendorMeta),
    [vendors, vendorMeta]
  );

  const getBackendUrl = () =>
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8001";

  if (isLoading || !isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-slate-200 border-t-[#c04a00] rounded-full animate-spin" />
      </div>
    );
  }

  const handleGoBack = () => {
    router.push("/");
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
    const autoSessionId = searchParams.get('session_id');
    
    if (autoSessionId && !sessionId) { 
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
    }
  }, [searchParams, sessionId]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      
      setFiles((prevFiles) => {
        const combinedFiles = [...prevFiles, ...newFiles];
        const uniqueFiles = combinedFiles.filter((file, index, self) =>
          index === self.findIndex((f) => f.name === file.name && f.size === file.size)
        );
        return uniqueFiles;
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
    setChatHistory([]);
  };

  const handleDownloadPdf = () => {
    if (tableData.length === 0 || vendors.length === 0) return;
    downloadComparisonPdf(tableData, vendors, vendorLabels, vendorMeta);
  };

  const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  // Poll the backend for live progress until the job finishes, errors, or times out.
  const pollProgress = async (sid: string, backendUrl: string) => {
    const POLL_MS = 1500;
    const MAX_MS = 600000; // 10 minutes safety cap
    const startedAt = Date.now();

    while (Date.now() - startedAt < MAX_MS) {
      if (!loadingRef.current) return; // user reset/navigated away

      let data: any;
      try {
        // Once we've applied the matrix, tell the backend so it stops re-sending
        // the (large) partial payload on every poll.
        const hasPartialParam = partialAppliedRef.current ? "?has_partial=true" : "";
        const res = await fetch(`${backendUrl}/api/progress/${sid}${hasPartialParam}`);
        data = await res.json();
      } catch {
        await sleep(POLL_MS); // transient network blip — keep trying
        continue;
      }

      if (data.message) setLoadingMessage(data.message);
      if (typeof data.processed === "number") {
        setLoadingProgress({ processed: data.processed, total: data.total || 0 });
      }

      // Show chart + table the moment the matrix is ready (recommendation still cooking).
      if (data.partial && !partialAppliedRef.current) {
        applyPartialData(data.partial);
        partialAppliedRef.current = true;
      }

      if (data.status === "done") {
        processComparisonData(data.result);
        return;
      }
      if (data.status === "error") {
        setReport(`❌ ${data.error || data.message || "Comparison failed on the backend."}`);
        return;
      }

      await sleep(POLL_MS);
    }

    setReport(
      "🕒 The comparison is taking unusually long. It may still be running on the backend — " +
        "please try again in a moment."
    );
  };

  const handleUpload = async () => {
    if (files.length < 2) {
      alert("Please upload at least 2 vendor quotes to run a comparison.");
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

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    const backendUrl = getBackendUrl();

    try {
      try {
        // A reachability probe only: any HTTP response (even 404) proves the
        // server is up. We only treat network errors / timeouts as "down" so an
        // older deploy missing /api/health doesn't block the whole UI.
        // Render's free tier cold-starts can take 30-60s, so allow a generous
        // timeout instead of aborting after a few seconds.
        await fetch(`${backendUrl}/api/health`, {
          signal: AbortSignal.timeout(60000),
        });
      } catch {
        setReport(
          `❌ Cannot reach the backend at ${backendUrl}. Start it from the backend folder:\n\n` +
            `cd backend\nuvicorn main:app --port 8001 --host 127.0.0.1\n\n` +
            `(Do not use backend.main:app when you are already inside backend/.)`
        );
        return;
      }

      // 1. Kick off the background job — returns a session_id almost instantly.
      const response = await fetch(`${backendUrl}/api/compare-quotes`, {
        method: "POST",
        body: formData,
      });
      const startData = await response.json();

      if (!startData.session_id) {
        setReport(`❌ Backend did not start the job: ${JSON.stringify(startData)}`);
        return;
      }

      setLoadingMessage(startData.message || "Processing started…");

      // 2. Poll for live progress until the result is ready.
      await pollProgress(startData.session_id, backendUrl);
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
      setLoading(false);
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

  return (
    <main className="bg-[#f8fafc] p-6 md:p-10 font-sans text-slate-800">
      <div className="max-w-5xl mx-auto space-y-8">

        <ComparePageNav projectId={projectIdParam} lane={lane} />

        {selectedQuoteIds.length >= 2 && lane === "project" && (
          <CompareSelectionBanner
            quoteIds={selectedQuoteIds}
            projectId={projectIdParam}
          />
        )}

        {isIntegratedLane && loading && !tableData.length && (
          <>
            <IntegratedLoadingBanner message={loadingMessage} />
            <CompareLoadingPanel
              message={loadingMessage}
              processed={loadingProgress.processed}
              total={loadingProgress.total}
            />
          </>
        )}

        {canShowPdfUpload && !sessionId && !tableData.length && (
          <div className="text-center space-y-3 pt-2">
            <div className="inline-flex items-center gap-2 rounded-full bg-orange-50 border border-orange-100 px-3 py-1 text-xs font-semibold text-[#c04a00] tracking-wide uppercase">
              TatvaOps · QuoteSense
            </div>
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
            disabled={loading || files.length < 2}
            className={`mt-6 w-full py-3 rounded-lg font-bold text-white transition-colors flex items-center justify-center gap-2 ${
              loading || files.length < 2
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
            />
          )}
        </div>
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
                  Line-by-line pricing with a historical moving average baseline.
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
                    <th className="p-4 border-b border-slate-200 text-right w-[120px] bg-indigo-50/60 text-indigo-700">
                      <div>Moving Avg</div>
                      <div className="text-[9px] font-normal normal-case tracking-normal text-indigo-400 mt-0.5">
                        Historical baseline
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
                      {/* Level 1 — Service category */}
                      <tr className="bg-slate-900/[0.03]">
                        <td colSpan={vendors.length + 2} className="p-3 pl-4 text-sm font-bold text-slate-800 uppercase tracking-wider border-y border-slate-200">
                          {cat.category}
                        </td>
                      </tr>

                      {cat.subs.map((sub, si) => (
                        <React.Fragment key={si}>
                          {/* Level 2 — Sub-service */}
                          <tr className="bg-slate-50/90">
                            <td colSpan={vendors.length + 2} className="py-2 pl-7 pr-4 text-[11px] font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-100">
                              {sub.sub}
                            </td>
                          </tr>

                          {/* Level 3 — Work items */}
                          {sub.rows.map((row, idx) => {
                            const baseline = Number(row.moving_average ?? row.market_average) || 0;
                            const weight = Number(row.moving_weight) || 0;
                            return (
                            <tr key={idx} className="hover:bg-slate-50/70 transition-colors group">
                              <td className="py-3 pl-11 pr-4 max-w-[320px]">
                                <div className="text-sm font-medium text-slate-900 leading-tight">
                                  {row.item_name || row.work_item || row.sub_service}
                                </div>
                                {row.room && (
                                  <div className="text-[10px] text-slate-400 mt-0.5 uppercase tracking-wide">
                                    {row.room}
                                  </div>
                                )}
                              </td>
                              <td className="p-4 text-right align-top bg-indigo-50/20 border-r border-indigo-100/50">
                                {baseline > 0 ? (
                                  <>
                                    <div className="text-sm font-semibold text-indigo-700 tabular-nums">
                                      {formatInrFull(baseline)}
                                    </div>
                                    {weight > 0 && (
                                      <div className="text-[10px] text-slate-400 mt-0.5" title="Quotes used to build this baseline">
                                        n={weight}
                                      </div>
                                    )}
                                  </>
                                ) : (
                                  <span className="text-sm text-slate-300">—</span>
                                )}
                              </td>
                              {vendors.map((vendor, vIdx) => {
                                const value = row[vendor];
                                const vs = priceVsBaseline(Number(value), baseline);
                                return (
                                  <td key={vIdx} className={`p-4 text-right tabular-nums ${value === 0 ? "opacity-50" : ""}`}>
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
                                        title={
                                          baseline > 0
                                            ? vs === "below"
                                              ? "Below moving average"
                                              : vs === "above"
                                                ? "Above moving average"
                                                : "Near moving average"
                                            : undefined
                                        }
                                      >
                                        {formatInrFull(Number(value))}
                                      </span>
                                    )}
                                  </td>
                                );
                              })}
                            </tr>
                          );})}
                        </React.Fragment>
                      ))}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-slate-400 mt-3 px-1">
              <span className="text-emerald-700 font-medium">Green</span> = below baseline ·{" "}
              <span className="text-amber-700 font-medium">Amber</span> = above baseline · Moving avg
              updates as more quotes are processed.
            </p>
          </div>
        )}

        {/* Interactive Insights (between the matrix and the AI recommendation) */}
        {tableData.length > 0 && vendors.length > 0 && (
          <VendorInsights tableData={tableData} vendors={vendors} meta={vendorMeta} />
        )}

        {/* AI Recommendation Section */}
        {report && (
          <div className="qs-card p-8">
            <h2 className="text-xl font-semibold text-slate-900 mb-1">Expert Recommendation</h2>
            <p className="text-sm text-slate-500 mb-6">AI analysis based on totals, scope, and moving-average baselines.</p>
            <div className="mb-8">
              <RecommendationView text={report} />
            </div>
            
            {!isIntegratedLane && (
            <div className="pt-6 border-t border-gray-100 flex flex-col sm:flex-row gap-4">
              <button 
                onClick={handleGoBack}
                className="flex-1 bg-blue-900 text-white py-3 rounded-lg font-bold hover:bg-black transition-all flex items-center justify-center gap-2 shadow-md"
              >
                ⬅️ All projects
              </button>
              
              <button 
                onClick={resetSelection}
                className="px-8 py-3 text-gray-500 hover:text-red-600 font-semibold transition-colors border border-transparent hover:border-gray-200 rounded-lg"
              >
                Compare New Quotes
              </button>
            </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}