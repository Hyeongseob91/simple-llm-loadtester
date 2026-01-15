"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight, Check, X, Circle } from "lucide-react";
import type { RequestLogEntry } from "@/hooks/useBenchmarkProgress";

interface RequestLogPanelProps {
  logs: RequestLogEntry[];
  isRunning: boolean;
}

/**
 * 요청별 로그를 표시하는 토글 패널 컴포넌트
 * 브라우저 개발자 도구 스타일의 접힘/펼침 패널
 */
export function RequestLogPanel({ logs, isRunning }: RequestLogPanelProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  // 자동 스크롤: 새 로그 추가 시 하단으로
  useEffect(() => {
    if (containerRef.current && isExpanded && isRunning) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs.length, isExpanded, isRunning]);

  // 로컬 스토리지에서 패널 상태 복원
  useEffect(() => {
    const saved = localStorage.getItem("requestLogPanelExpanded");
    if (saved !== null) {
      setIsExpanded(saved === "true");
    }
  }, []);

  // 패널 상태 저장
  const handleToggle = () => {
    const newState = !isExpanded;
    setIsExpanded(newState);
    localStorage.setItem("requestLogPanelExpanded", String(newState));
  };

  // 상태에 따른 아이콘 색상
  const getStatusColor = (status: RequestLogEntry["status"]) => {
    switch (status) {
      case "pending":
        return "text-gray-400 dark:text-gray-500";
      case "running":
        return "text-blue-500 dark:text-blue-400";
      case "completed":
        return "text-green-500 dark:text-green-400";
      case "failed":
        return "text-red-500 dark:text-red-400";
      default:
        return "text-gray-400";
    }
  };

  // E2E 시간 포맷팅 (ms → s 또는 ms)
  const formatE2E = (ms: number | null) => {
    if (ms === null) return "-";
    if (ms >= 1000) {
      return `${(ms / 1000).toFixed(2)}s`;
    }
    return `${ms.toFixed(0)}ms`;
  };

  // TTFT 포맷팅
  const formatTTFT = (ms: number | null) => {
    if (ms === null) return "-";
    return `${ms.toFixed(0)}ms`;
  };

  if (!isRunning && logs.length === 0) {
    return null;
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* 헤더 - 클릭 시 토글 */}
      <div
        onClick={handleToggle}
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors border-b border-gray-200 dark:border-gray-700"
      >
        <div className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-gray-500" />
          ) : (
            <ChevronRight className="h-4 w-4 text-gray-500" />
          )}
          <span className="font-medium text-gray-900 dark:text-gray-100">
            Request Log
          </span>
          {isRunning && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
              Live
            </span>
          )}
        </div>
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {logs.length} requests
        </span>
      </div>

      {/* 테이블 - 펼침 상태에서만 표시 */}
      {isExpanded && (
        <div
          ref={containerRef}
          className="max-h-64 overflow-y-auto overflow-x-auto"
        >
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-50 dark:bg-gray-700/50">
              <tr className="text-left text-gray-500 dark:text-gray-400">
                <th className="px-4 py-2 font-medium w-16">#</th>
                <th className="px-4 py-2 font-medium w-20">Status</th>
                <th className="px-4 py-2 font-medium w-20 text-right">TTFT</th>
                <th className="px-4 py-2 font-medium w-20 text-right">E2E</th>
                <th className="px-4 py-2 font-medium w-20 text-right">Tokens</th>
                <th className="px-4 py-2 font-medium w-16 text-center">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {logs.map((log) => (
                <tr
                  key={`${log.requestId}-${log.timestamp}`}
                  className={`${
                    !log.success
                      ? "bg-red-50 dark:bg-red-900/20"
                      : "hover:bg-gray-50 dark:hover:bg-gray-700/30"
                  } transition-colors`}
                >
                  <td className="px-4 py-2 text-gray-600 dark:text-gray-300 font-mono">
                    {log.requestId}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-1.5">
                      <Circle
                        className={`h-2.5 w-2.5 fill-current ${getStatusColor(log.status)}`}
                      />
                      <span className="text-gray-600 dark:text-gray-300 capitalize text-xs">
                        {log.status}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-gray-600 dark:text-gray-300">
                    {formatTTFT(log.ttftMs)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-gray-600 dark:text-gray-300">
                    {formatE2E(log.e2eMs)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-gray-600 dark:text-gray-300">
                    {log.outputTokens ?? "-"}
                  </td>
                  <td className="px-4 py-2 text-center">
                    {log.success ? (
                      <Check className="h-4 w-4 text-green-500 dark:text-green-400 mx-auto" />
                    ) : (
                      <X className="h-4 w-4 text-red-500 dark:text-red-400 mx-auto" />
                    )}
                  </td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-gray-500 dark:text-gray-400"
                  >
                    요청 대기 중...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default RequestLogPanel;
