"use client";

import React, { useState, useEffect, useRef, Suspense } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useSearchParams } from 'next/navigation';

const LOADING_MESSAGES = [
  "⚙️ Extracting data from vendor PDFs...",
  "🧮 Calculating market ground truth...",
  "⚖️ Comparing vendor deviations...",
  "🕵️ Analyzing tactical pricing and red flags...",
  "🧠 AI is drafting the final report...",
  "✨ Finalizing dashboard..."
];

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

  // Chat State Variables
  const [sessionId, setSessionId] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState<{role: string, content: string}[]>([]);
  const [isChatting, setIsChatting] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const processComparisonData = (data: any) => {
    if (data.report) {
      setReport(data.report);
      setChartData(data.chartData || []);
      setTableData(data.tableData || []);
      setVendors(data.vendors || []);
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
    let interval: NodeJS.Timeout;
    if (loading) {
      setLoadingMsgIdx(0);
      interval = setInterval(() => {
        setLoadingMsgIdx((prev) => 
          prev < LOADING_MESSAGES.length - 1 ? prev + 1 : prev
        );
      }, 2500);
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
    setSessionId("");
    setChatHistory([]);
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
    setChatHistory([]);

    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      if (loading) { 
        controller.abort();
      }
    }, 180000); 

    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8001";
      
      const response = await fetch(`${backendUrl}/api/compare-quotes`, {
          method: "POST",
          body: formData,
          signal: controller.signal, 
      });

      const data = await response.json();
      
      clearTimeout(timeoutId);
      processComparisonData(data);
    }
     catch (error: any) {
      if (error.name === 'AbortError') {
        setReport("🕒 Analysis is taking very long. The backend might be struggling with the Gemini API or large files. Check your terminal logs.");
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
            {loading ? LOADING_MESSAGES[loadingMsgIdx] : `Compare ${files.length > 1 ? files.length + ' ' : ''}Quotes Now`}
          </button>
        </div>

        {/* Visual Chart Section */}
        {chartData.length > 0 && (
          <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">Total Cost Comparison</h2>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="vendor" tick={{fontSize: 12}} interval={0} angle={-15} textAnchor="end" height={80} />
                  <YAxis tickFormatter={(value) => `₹${(value / 100000).toFixed(1)}L`} />
                  <Tooltip formatter={(value: any) => `₹${Number(value).toLocaleString()}`} />
                  <Bar dataKey="total" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

       {tableData.length > 0 && (
          <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 animate-in fade-in slide-in-from-bottom-4 duration-700 overflow-hidden">
            <h2 className="text-2xl font-bold text-gray-800 mb-6 px-2">Tatva Quotes Comparison Matrix</h2>
            
            <div className="overflow-x-auto border rounded-lg">
              <table className="w-full text-left border-collapse min-w-[800px]">
                <thead>
                  <tr className="bg-gray-50 text-gray-700 uppercase text-[10px] font-bold tracking-widest">
                    <th className="p-4 border-b border-gray-200 w-[250px]">Service Description</th>
                    <th className="p-4 border-b border-gray-200 text-right bg-blue-50/50 text-blue-700">Baseline Mean</th>
                    {vendors.map((vendor, i) => (
                      <th key={i} className="p-4 border-b border-gray-200 text-right max-w-[150px]">
                        <div className="truncate" title={vendor}>{vendor.split(' (')[0]}</div>
                      </th>
                    ))}
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
                        <td colSpan={vendors.length + 2} className="p-3 pl-4 text-sm font-black text-blue-900 uppercase tracking-wider border-y border-blue-100">
                          📁 {category}
                        </td>
                      </tr>

                      {(items as any[]).map((row, idx) => (
                        <tr key={idx} className="hover:bg-gray-50/80 transition-colors group">
                          <td className="p-4 pl-8">
                            <div className="text-sm font-bold text-gray-900 leading-tight">{row.sub_service}</div>
                            <div className="text-[10px] text-gray-400 mt-0.5 group-hover:text-gray-500 uppercase">Verified Service</div>
                          </td>
                          <td className="p-4 text-right font-bold text-blue-600 bg-blue-50/30 border-x border-blue-50">
                            ₹{Number(row.market_average).toLocaleString()}
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

        {report && (
          <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200 animate-in fade-in slide-in-from-bottom-4 duration-1000">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">Expert Recommendation</h2>
            <div className="prose max-w-none whitespace-pre-wrap text-gray-700 leading-relaxed">
              {report}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}