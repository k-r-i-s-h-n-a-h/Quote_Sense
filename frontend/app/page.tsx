"use client";

import React, { useState, useEffect, useRef, useMemo, Suspense } from "react";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import CompareLoadingPanel from "../components/CompareLoadingPanel";
import VendorInsights from "../components/VendorInsights";
import RecommendationView from "../components/RecommendationView";
import { buildVendorLabels } from "../lib/format";

const VendorChart = dynamic(() => import("../components/VendorChart"), {
  ssr: false,
  loading: () => (
    <div className="h-80 w-full flex items-center justify-center text-gray-400 text-sm">
      Loading chart…
    </div>
  ),
});

// Main export wrapped in Suspense to fix the Next.js/useSearchParams error
export default function Home() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen">Loading QuoteSense...</div>}>
      <QuoteSenseContent />
    </Suspense>
  );
}

function QuoteSenseContent() {
  const searchParams = useSearchParams();
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMsgIdx, setLoadingMsgIdx] = useState(0); 
  
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

  const vendorLabels = useMemo(
    () => buildVendorLabels(vendors, vendorMeta),
    [vendors, vendorMeta]
  );

  const getBackendUrl = () =>
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8001";

  // --- REDIRECT LOGIC ---
  const handleGoBack = () => {
    // This sends the user back to the main dev dashboard
    window.location.href = "https://tatvaops.com/my-projects";
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

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (loading) {
      setLoadingMsgIdx(0);
      interval = setInterval(() => {
        setLoadingMsgIdx((prev) => prev + 1);
      }, 2800);
    }
    return () => clearInterval(interval);
  }, [loading]);

  useEffect(() => {
    const autoSessionId = searchParams.get('session_id');
    
    if (autoSessionId && !sessionId) { 
      const fetchAutoData = async () => {
        setLoading(true);
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

    const esc = (v: any) =>
      String(v ?? "").replace(/[&<>"']/g, (c) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] as string)
      );

    // Vendor column headers (company + variant + quote no/date)
    const vendorHeadCells = vendors
      .map((vendor) => {
        const info = vendorLabels[vendor] || ({} as any);
        const meta = vendorMeta[vendor] || ({} as any);
        const company = info.company ?? vendor.split(" (")[0];
        const variant = info.variant ? `<div class="v-variant">${esc(info.variant)}</div>` : "";
        const qno = info.quoteNumber ? `#${esc(info.quoteNumber)}` : "";
        const qdate = info.quoteDate || meta.quote_date || "";
        const sep = qno && qdate ? " · " : "";
        const sub =
          qno || qdate ? `<div class="v-sub">${qno}${esc(sep)}${esc(qdate)}</div>` : "";
        return `<th class="num"><div class="v-company">${esc(company)}</div>${variant}${sub}</th>`;
      })
      .join("");

    // Group rows by category, preserving order
    const grouped: Record<string, any[]> = {};
    const order: string[] = [];
    tableData.forEach((item) => {
      if (!grouped[item.category]) {
        grouped[item.category] = [];
        order.push(item.category);
      }
      grouped[item.category].push(item);
    });

    const bodyRows = order
      .map((category) => {
        const catRow = `<tr class="cat"><td colspan="${vendors.length + 1}">${esc(
          category
        )}</td></tr>`;
        const itemRows = grouped[category]
          .map((row) => {
            const cells = vendors
              .map((vendor) => {
                const value = row[vendor];
                if (value === 0 || value === undefined || value === null) {
                  return `<td class="num na">N/A</td>`;
                }
                return `<td class="num">₹${Number(value).toLocaleString("en-IN")}</td>`;
              })
              .join("");
            return `<tr><td class="desc"><span class="svc">${esc(
              row.sub_service
            )}</span><span class="tax">${esc(
              row.taxonomy || "Verified Service"
            )}</span></td>${cells}</tr>`;
          })
          .join("");
        return catRow + itemRows;
      })
      .join("");

    const today = new Date().toLocaleDateString("en-IN", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });

    const html = `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>Tatva Quotes Comparison Matrix</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1f2937; margin: 28px; }
  .head { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 18px; }
  .head h1 { font-size: 20px; margin: 0; color: #0f172a; }
  .head .meta { font-size: 11px; color: #6b7280; text-align: right; }
  table { width: 100%; border-collapse: collapse; font-size: 11px; }
  thead th { background: #f8fafc; border-bottom: 2px solid #e2e8f0; padding: 8px 10px; vertical-align: top; }
  thead th:first-child { text-align: left; width: 240px; text-transform: uppercase; letter-spacing: .06em; font-size: 9px; color: #64748b; }
  th.num { text-align: right; }
  .v-company { font-size: 11px; font-weight: 700; color: #111827; }
  .v-variant { font-size: 10px; font-weight: 600; color: #1d4ed8; margin-top: 2px; }
  .v-sub { font-size: 9px; font-weight: 400; color: #9ca3af; margin-top: 2px; }
  tbody td { padding: 7px 10px; border-bottom: 1px solid #f1f5f9; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  td.num.na { color: #f87171; font-style: italic; }
  td.desc .svc { display: block; font-weight: 700; color: #111827; }
  td.desc .tax { display: block; font-size: 9px; text-transform: uppercase; color: #9ca3af; margin-top: 2px; }
  tr.cat td { background: #eef2ff; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; color: #1e3a8a; font-size: 10px; border-top: 1px solid #c7d2fe; border-bottom: 1px solid #c7d2fe; }
  tr { page-break-inside: avoid; }
  thead { display: table-header-group; }
  @page { size: A4 landscape; margin: 14mm; }
</style>
</head>
<body>
  <div class="head">
    <h1>Tatva Quotes Comparison Matrix</h1>
    <div class="meta">Generated by QuoteSense · ${esc(today)}</div>
  </div>
  <table>
    <thead>
      <tr><th>Service Description</th>${vendorHeadCells}</tr>
    </thead>
    <tbody>${bodyRows}</tbody>
  </table>
  <script>
    window.onload = function () { window.focus(); window.print(); };
  </script>
</body>
</html>`;

    const win = window.open("", "_blank");
    if (!win) {
      alert("Please allow pop-ups for this site to download the PDF.");
      return;
    }
    win.document.open();
    win.document.write(html);
    win.document.close();
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

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    const backendUrl = getBackendUrl();
    const controller = new AbortController();
    // Comparison runs Gemini on every PDF, so allow plenty of time before giving up.
    const TIMEOUT_MS = 600000; // 10 minutes
    const timeoutId = setTimeout(() => {
      if (loadingRef.current) {
        controller.abort(new DOMException("Comparison timed out", "TimeoutError"));
      }
    }, TIMEOUT_MS);

    try {
      try {
        const health = await fetch(`${backendUrl}/api/health`, {
          signal: AbortSignal.timeout(5000),
        });
        if (!health.ok) {
          throw new Error(`Backend health check failed (${health.status})`);
        }
      } catch {
        clearTimeout(timeoutId);
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
        signal: controller.signal,
      });

      const data = await response.json();

      clearTimeout(timeoutId);
      processComparisonData(data);
    } catch (error: any) {
      if (error.name === "AbortError" || error.name === "TimeoutError") {
        setReport(
          "🕒 The comparison is still running on the backend but the page stopped waiting after 10 minutes. " +
            "Check the uvicorn terminal — if you see '📊 Built comparison matrix...', just run the compare again to load the result."
        );
      } else if (error.message === "Failed to fetch") {
        setReport(
          `❌ Connection lost to ${backendUrl}. The backend may have crashed mid-request — check the terminal running uvicorn.`
        );
      } else {
        setReport(`❌ Browser Error: ${error.message}`);
      }
      console.error("Full Error Details:", error);
    } finally {
      setLoading(false);
      clearTimeout(timeoutId); 
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
    <main className="min-h-screen bg-gray-50 p-6 md:p-10 font-sans text-gray-800 pb-20">
      <div className="max-w-5xl mx-auto space-y-8">
        
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-bold text-blue-900">QuoteSense 📊</h1>
          <p className="text-gray-600 text-lg">TatvaOps Intelligent Quote Comparator</p>
        </div>

        {/* Upload Section */}
        <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-xl font-semibold">1. Select Vendor Quotes (PDF)</h2>
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

          {loading && <CompareLoadingPanel messageIndex={loadingMsgIdx} />}
        </div>

        {/* Visual Chart Section */}
        {chartData.length > 0 && (
          <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">Total Cost Comparison</h2>
            <VendorChart data={chartData} meta={vendorMeta} />
          </div>
        )}

       {tableData.length > 0 && (
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 animate-in fade-in slide-in-from-bottom-4 duration-700 overflow-hidden">
            <div className="flex items-center justify-between mb-6 px-2">
              <h2 className="text-2xl font-bold text-gray-800">Tatva Quotes Comparison Matrix</h2>
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
            
            <div className="overflow-x-auto border rounded-lg">
              <table className="w-full text-left border-collapse min-w-[800px]">
                <thead>
                  <tr className="bg-gray-50 text-gray-700 uppercase text-[10px] font-bold tracking-widest">
                    <th className="p-4 border-b border-gray-200 w-[250px]">Service Description</th>
                    {vendors.map((vendor, i) => {
                      const info = vendorLabels[vendor];
                      const meta = vendorMeta[vendor] || {};
                      return (
                        <th key={i} className="p-4 border-b border-gray-200 text-right align-top max-w-[170px]">
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
                
                <tbody className="divide-y divide-gray-100">
                  {Object.entries(
                    tableData.reduce((acc, item) => {
                      if (!acc[item.category]) acc[item.category] = [];
                      acc[item.category].push(item);
                      return acc;
                    }, {} as Record<string, any[]>)
                  ).map(([category, items], groupIdx) => (
                    <React.Fragment key={groupIdx}>
                      <tr className="bg-blue-900/5">
                        <td colSpan={vendors.length + 1} className="p-3 pl-4 text-sm font-black text-blue-900 uppercase tracking-wider border-y border-blue-100">
                          📁 {category}
                        </td>
                      </tr>

                      {(items as any[]).map((row, idx) => (
                        <tr key={idx} className="hover:bg-gray-50/80 transition-colors group">
                          <td className="p-4 pl-8 max-w-[320px]">
                            <div className="text-sm font-bold text-gray-900 leading-tight">{row.sub_service}</div>
                            <div className="text-[10px] text-gray-400 mt-0.5 group-hover:text-gray-500 uppercase">{row.taxonomy || "Verified Service"}</div>
                          </td>
                          {vendors.map((vendor, vIdx) => {
                            const value = row[vendor];
                            return (
                              <td key={vIdx} className={`p-4 text-right ${value === 0 ? "opacity-60" : ""}`}>
                                {value === 0 ? (
                                  <span className="text-[14px] font-bold text-red-400 italic">N/A</span>
                                ) : (
                                  <span className="text-sm font-medium text-gray-700">₹{Number(value).toLocaleString()}</span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Interactive Insights (between the matrix and the AI recommendation) */}
        {tableData.length > 0 && vendors.length > 0 && (
          <VendorInsights tableData={tableData} vendors={vendors} meta={vendorMeta} />
        )}

        {/* AI Recommendation Section */}
        {report && (
          <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">Expert Recommendation</h2>
            <div className="mb-8">
              <RecommendationView text={report} />
            </div>
            
            {/* THE REDIRECT BUTTON BLOCK */}
            <div className="pt-6 border-t border-gray-100 flex flex-col sm:flex-row gap-4">
              <button 
                onClick={handleGoBack}
                className="flex-1 bg-blue-900 text-white py-3 rounded-lg font-bold hover:bg-black transition-all flex items-center justify-center gap-2 shadow-md"
              >
                ⬅️ Return to Dashboard
              </button>
              
              <button 
                onClick={resetSelection}
                className="px-8 py-3 text-gray-500 hover:text-red-600 font-semibold transition-colors border border-transparent hover:border-gray-200 rounded-lg"
              >
                Compare New Quotes
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}