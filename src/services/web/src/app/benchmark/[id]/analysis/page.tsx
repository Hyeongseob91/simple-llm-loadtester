"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { ArrowLeft, Loader2, AlertCircle, RefreshCw, Sparkles, Download, ChevronDown } from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const languageOptions = [
  { value: "ko", label: "한국어" },
  { value: "en", label: "English" },
];

export default function AnalysisPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.id as string;

  const [analysis, setAnalysis] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasStarted, setHasStarted] = useState(false);
  const [isThinkingModel, setIsThinkingModel] = useState(false);
  const [language, setLanguage] = useState("ko");
  const contentRef = useRef<HTMLDivElement>(null);

  // Fetch benchmark status and result
  const { data: status } = useQuery({
    queryKey: ["run-status", runId],
    queryFn: () => api.getRunStatus(runId),
  });

  const { data: result } = useQuery({
    queryKey: ["run-result", runId],
    queryFn: () => api.getResult(runId),
    enabled: status?.status === "completed",
  });

  // Auto-scroll to bottom when new content arrives
  useEffect(() => {
    if (contentRef.current && isGenerating) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [analysis, isGenerating]);

  // Download analysis result
  const downloadAnalysis = () => {
    const modelName = status?.model?.replace(/[/\\:*?"<>|]/g, "-") || "unknown";
    const dateStr = new Date().toISOString().split("T")[0];
    const filename = `analysis_${modelName}_${dateStr}.md`;

    const blob = new Blob([analysis], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();

    URL.revokeObjectURL(url);
  };

  const startAnalysis = async () => {
    setIsGenerating(true);
    setIsThinking(false);
    setError(null);
    setAnalysis("");
    setHasStarted(true);

    try {
      const serverUrl = status?.server_url || "";
      const model = status?.model || "";

      const response = await fetch(
        `/api/v1/benchmark/result/${runId}/analysis?server_url=${encodeURIComponent(serverUrl)}&model=${encodeURIComponent(model)}&is_thinking_model=${isThinkingModel}&language=${language}`
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response body");
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") {
              setIsGenerating(false);
              return;
            }
            try {
              const parsed = JSON.parse(data);
              // Thinking status handling
              if (parsed.thinking !== undefined) {
                setIsThinking(parsed.thinking);
              }
              if (parsed.content) {
                setAnalysis((prev) => prev + parsed.content);
              }
              if (parsed.error) {
                setError(parsed.error);
                setIsGenerating(false);
                return;
              }
            } catch {
              // Ignore JSON parse errors for incomplete chunks
            }
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred while generating analysis");
    } finally {
      setIsGenerating(false);
    }
  };

  // If benchmark is not completed, show error
  if (status?.status === "running") {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link
            href={`/benchmark/${runId}`}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            AI Analysis Report
          </h1>
        </div>
        <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded-xl p-6 text-center">
          <AlertCircle className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
          <p className="text-yellow-600 dark:text-yellow-400">
            Benchmark is still running. Analysis can be performed after completion.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href={`/benchmark/${runId}`}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              AI Analysis Report
            </h1>
            <p className="mt-1 text-gray-600 dark:text-gray-400">
              {status?.model} @ {status?.server_url}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Thinking Model Checkbox */}
          <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={isThinkingModel}
              onChange={(e) => setIsThinkingModel(e.target.checked)}
              disabled={isGenerating}
              className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
            />
            <span>Thinking Model</span>
          </label>
          {/* Language Selector */}
          <div className="relative">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              disabled={isGenerating}
              className="appearance-none bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 pr-8 text-sm text-gray-700 dark:text-gray-300 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {languageOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500 pointer-events-none" />
          </div>
          <button
            onClick={startAnalysis}
            disabled={isGenerating}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
              isGenerating
                ? "bg-gray-100 text-gray-400 cursor-not-allowed dark:bg-gray-700 dark:text-gray-500"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : hasStarted ? (
              <>
                <RefreshCw className="h-4 w-4" />
                Regenerate
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Start Analysis
              </>
            )}
          </button>
        </div>
      </div>

      {/* Result Summary Card */}
      {result?.summary && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Benchmark Summary
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400">Best Throughput</div>
              <div className="text-xl font-bold text-gray-900 dark:text-white">
                {result.summary.best_throughput?.toFixed(1)} <span className="text-sm font-normal">tok/s</span>
              </div>
            </div>
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400">Best TTFT (p50)</div>
              <div className="text-xl font-bold text-gray-900 dark:text-white">
                {result.summary.best_ttft_p50?.toFixed(1)} <span className="text-sm font-normal">ms</span>
              </div>
            </div>
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400">Best Concurrency</div>
              <div className="text-xl font-bold text-gray-900 dark:text-white">
                {result.summary.best_concurrency}
              </div>
            </div>
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400">Avg Goodput</div>
              <div className="text-xl font-bold text-gray-900 dark:text-white">
                {result.summary.avg_goodput_percent?.toFixed(1) ?? "N/A"} <span className="text-sm font-normal">%</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Analysis Content */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-blue-600" />
              Analysis Results
            </h2>
            {isGenerating && (
              <span className={`text-xs px-2 py-1 rounded flex items-center gap-1 ${
                isThinking
                  ? "text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30"
                  : "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30"
              }`}>
                <Loader2 className="h-3 w-3 animate-spin" />
                {isThinking ? "AI Thinking..." : "Writing Report"}
              </span>
            )}
          </div>
          {/* Download Button - shown after analysis is complete */}
          {!isGenerating && analysis && (
            <button
              onClick={downloadAnalysis}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              <Download className="h-4 w-4" />
              Download
            </button>
          )}
        </div>

        <div
          ref={contentRef}
          className="p-6 max-h-[600px] overflow-y-auto"
        >
          {error ? (
            <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4 text-red-600 dark:text-red-400">
              <div className="flex items-center gap-2 font-medium mb-2">
                <AlertCircle className="h-5 w-5" />
                Error
              </div>
              <p className="text-sm">{error}</p>
            </div>
          ) : !hasStarted ? (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
              <Sparkles className="h-12 w-12 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
              <p>Click the &quot;Start Analysis&quot; button above</p>
              <p>to generate an AI analysis report.</p>
              <p className="mt-4 text-sm text-gray-400 dark:text-gray-500">
                Uses the vLLM model from the benchmark server for analysis.
              </p>
            </div>
          ) : analysis ? (
            <div className="prose prose-gray dark:prose-invert max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // GFM table styling
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-4">
                      <table className="min-w-full border-collapse border border-gray-300 dark:border-gray-600 text-sm">
                        {children}
                      </table>
                    </div>
                  ),
                  thead: ({ children }) => (
                    <thead className="bg-gray-100 dark:bg-gray-700">{children}</thead>
                  ),
                  tbody: ({ children }) => (
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-600">{children}</tbody>
                  ),
                  tr: ({ children }) => (
                    <tr className="hover:bg-gray-50 dark:hover:bg-gray-700/50">{children}</tr>
                  ),
                  th: ({ children }) => (
                    <th className="border border-gray-300 dark:border-gray-600 px-3 py-2 text-left font-semibold text-gray-900 dark:text-gray-100">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="border border-gray-300 dark:border-gray-600 px-3 py-2 text-gray-700 dark:text-gray-300">
                      {children}
                    </td>
                  ),
                }}
              >
                {analysis}
              </ReactMarkdown>
              {isGenerating && (
                <span className="inline-block w-2 h-5 bg-blue-600 animate-pulse ml-1" />
              )}
            </div>
          ) : isGenerating ? (
            <div className="text-center py-12">
              {isThinking ? (
                <>
                  <div className="relative mx-auto mb-4 w-16 h-16">
                    <div className="absolute inset-0 rounded-full border-4 border-amber-200 dark:border-amber-800"></div>
                    <div className="absolute inset-0 rounded-full border-4 border-amber-500 border-t-transparent animate-spin"></div>
                    <span className="absolute inset-0 flex items-center justify-center text-2xl">
                      🤔
                    </span>
                  </div>
                  <p className="text-amber-600 dark:text-amber-400 font-medium">
                    AI is analyzing benchmark results...
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                    Thinking model is performing in-depth analysis
                  </p>
                </>
              ) : (
                <>
                  <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
                  <p className="text-gray-600 dark:text-gray-400">
                    Generating analysis from vLLM...
                  </p>
                </>
              )}
            </div>
          ) : null}
        </div>
      </div>

      {/* Info */}
      <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 text-sm text-gray-500 dark:text-gray-400">
        <p>
          This analysis is generated using the {status?.model} model from the vLLM server ({status?.server_url}).
          The analysis is AI-generated and should be used as reference only.
        </p>
      </div>
    </div>
  );
}
