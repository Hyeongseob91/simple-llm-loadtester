"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight, CheckCircle, AlertTriangle, Loader2, XCircle } from "lucide-react";
import type { ValidationLogEntry } from "@/hooks/useBenchmarkProgress";

interface ValidationLogPanelProps {
  logs: ValidationLogEntry[];
  isRunning: boolean;
}

/**
 * Validation 진행 로그를 표시하는 토글 패널 컴포넌트
 * 브라우저 개발자 도구 스타일의 접힘/펼침 패널
 */
export function ValidationLogPanel({ logs, isRunning }: ValidationLogPanelProps) {
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
    const saved = localStorage.getItem("validationLogPanelExpanded");
    if (saved !== null) {
      setIsExpanded(saved === "true");
    }
  }, []);

  // 패널 상태 저장
  const handleToggle = () => {
    const newState = !isExpanded;
    setIsExpanded(newState);
    localStorage.setItem("validationLogPanelExpanded", String(newState));
  };

  // 상태에 따른 아이콘
  const getStatusIcon = (status: ValidationLogEntry["status"]) => {
    switch (status) {
      case "running":
        return <Loader2 className="h-4 w-4 text-blue-500 dark:text-blue-400 animate-spin" />;
      case "warning":
        return <AlertTriangle className="h-4 w-4 text-yellow-500 dark:text-yellow-400" />;
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500 dark:text-green-400" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500 dark:text-red-400" />;
      default:
        return <Loader2 className="h-4 w-4 text-gray-400 animate-spin" />;
    }
  };

  // Step에 따른 배경색
  const getStepBadgeColor = (step: string) => {
    switch (step) {
      case "init":
        return "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400";
      case "before":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400";
      case "after":
        return "bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400";
      case "validate":
        return "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400";
      case "complete":
        return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-400";
    }
  };

  // 전체 상태 계산
  const getOverallStatus = () => {
    if (logs.length === 0) return null;
    const lastLog = logs[logs.length - 1];
    if (lastLog.status === "completed") return "passed";
    if (lastLog.status === "failed") return "failed";
    return "running";
  };

  const overallStatus = getOverallStatus();

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
            Validation Log
          </span>
          {isRunning && !overallStatus && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Live
            </span>
          )}
          {overallStatus === "passed" && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
              <CheckCircle className="h-3 w-3 mr-1" />
              PASSED
            </span>
          )}
          {overallStatus === "failed" && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
              <XCircle className="h-3 w-3 mr-1" />
              FAILED
            </span>
          )}
        </div>
        <span className="text-sm text-gray-500 dark:text-gray-400">
          {logs.length} logs
        </span>
      </div>

      {/* 로그 목록 - 펼침 상태에서만 표시 */}
      {isExpanded && (
        <div
          ref={containerRef}
          className="max-h-48 overflow-y-auto"
        >
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {logs.map((log, index) => (
              <div
                key={`${log.step}-${log.timestamp}-${index}`}
                className={`flex items-center gap-3 px-4 py-2 ${
                  log.status === "failed"
                    ? "bg-red-50 dark:bg-red-900/20"
                    : log.status === "warning"
                    ? "bg-yellow-50 dark:bg-yellow-900/10"
                    : "hover:bg-gray-50 dark:hover:bg-gray-700/30"
                } transition-colors`}
              >
                {/* 상태 아이콘 */}
                <div className="flex-shrink-0">
                  {getStatusIcon(log.status)}
                </div>

                {/* Step 배지 */}
                <span className={`flex-shrink-0 px-2 py-0.5 rounded text-xs font-medium uppercase ${getStepBadgeColor(log.step)}`}>
                  {log.step}
                </span>

                {/* 메시지 */}
                <span className="flex-1 text-sm text-gray-700 dark:text-gray-300 truncate">
                  {log.message}
                </span>

                {/* 타임스탬프 */}
                <span className="flex-shrink-0 text-xs text-gray-400 dark:text-gray-500 font-mono">
                  {new Date(log.timestamp * 1000).toLocaleTimeString()}
                </span>
              </div>
            ))}
            {logs.length === 0 && (
              <div className="px-4 py-8 text-center text-gray-500 dark:text-gray-400">
                Validation 대기 중...
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ValidationLogPanel;
