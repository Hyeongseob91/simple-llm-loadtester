"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { ArrowLeft, Loader2, AlertCircle, RefreshCw, Sparkles } from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function AnalysisPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.id as string;

  const [analysis, setAnalysis] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasStarted, setHasStarted] = useState(false);
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

  const startAnalysis = async () => {
    setIsGenerating(true);
    setError(null);
    setAnalysis("");
    setHasStarted(true);

    try {
      const serverUrl = status?.server_url || "http://host.docker.internal:8000";
      const model = status?.model || "";

      const response = await fetch(
        `/api/v1/benchmark/result/${runId}/analysis?server_url=${encodeURIComponent(serverUrl)}&model=${encodeURIComponent(model)}`
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
      setError(err instanceof Error ? err.message : "분석 생성 중 오류가 발생했습니다");
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
            AI 분석 보고서
          </h1>
        </div>
        <div className="bg-yellow-50 dark:bg-yellow-900/20 rounded-xl p-6 text-center">
          <AlertCircle className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
          <p className="text-yellow-600 dark:text-yellow-400">
            벤치마크가 아직 진행 중입니다. 완료 후 분석을 실행할 수 있습니다.
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
              AI 분석 보고서
            </h1>
            <p className="mt-1 text-gray-600 dark:text-gray-400">
              {status?.model} @ {status?.server_url}
            </p>
          </div>
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
              분석 생성 중...
            </>
          ) : hasStarted ? (
            <>
              <RefreshCw className="h-4 w-4" />
              다시 분석
            </>
          ) : (
            <>
              <Sparkles className="h-4 w-4" />
              분석 시작
            </>
          )}
        </button>
      </div>

      {/* Result Summary Card */}
      {result?.summary && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            벤치마크 결과 요약
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400">최고 처리량</div>
              <div className="text-xl font-bold text-gray-900 dark:text-white">
                {result.summary.best_throughput?.toFixed(1)} <span className="text-sm font-normal">tok/s</span>
              </div>
            </div>
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400">최저 TTFT (p50)</div>
              <div className="text-xl font-bold text-gray-900 dark:text-white">
                {result.summary.best_ttft_p50?.toFixed(1)} <span className="text-sm font-normal">ms</span>
              </div>
            </div>
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400">최적 동시성</div>
              <div className="text-xl font-bold text-gray-900 dark:text-white">
                {result.summary.best_concurrency}
              </div>
            </div>
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="text-xs text-gray-500 dark:text-gray-400">평균 Goodput</div>
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
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-blue-600" />
            AI 분석 결과
          </h2>
          {isGenerating && (
            <span className="text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-2 py-1 rounded flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" />
              vLLM 생성 중
            </span>
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
                오류 발생
              </div>
              <p className="text-sm">{error}</p>
            </div>
          ) : !hasStarted ? (
            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
              <Sparkles className="h-12 w-12 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
              <p>상단의 "분석 시작" 버튼을 클릭하여</p>
              <p>AI 분석 보고서를 생성하세요.</p>
              <p className="mt-4 text-sm text-gray-400 dark:text-gray-500">
                벤치마크 서버의 vLLM 모델을 사용하여 분석합니다.
              </p>
            </div>
          ) : analysis ? (
            <div className="prose prose-gray dark:prose-invert max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // GFM 테이블 스타일링
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
              <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
              <p className="text-gray-600 dark:text-gray-400">
                vLLM에서 분석을 생성하고 있습니다...
              </p>
            </div>
          ) : null}
        </div>
      </div>

      {/* Info */}
      <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 text-sm text-gray-500 dark:text-gray-400">
        <p>
          이 분석은 벤치마크에 사용된 vLLM 서버 ({status?.server_url})의 {status?.model} 모델을 사용하여 생성됩니다.
          분석 결과는 AI가 생성한 것으로, 참고 자료로만 활용해주세요.
        </p>
      </div>
    </div>
  );
}
