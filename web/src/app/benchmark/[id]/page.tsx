"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useState, useEffect, useMemo, useRef } from "react";
import { api, ConcurrencyResult } from "@/lib/api";
import { MetricCard } from "@/components/metric-card";
import { useBenchmarkProgress } from "@/hooks/useBenchmarkProgress";
import { Gauge, Clock, Activity, AlertCircle, CheckCircle, Loader2, FileText, Zap, Timer } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

// Time-series data point type
interface TimeSeriesPoint {
  time: string;
  timestamp: number;
  ttft: number;
  throughput: number;
}

export default function BenchmarkResultPage() {
  const params = useParams();
  const runId = params.id as string;

  const { data: status } = useQuery({
    queryKey: ["run-status", runId],
    queryFn: () => api.getRunStatus(runId),
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 2000 : false,
  });

  // 결과를 running/completed 모두에서 가져옴 (running에서는 부분 결과)
  const { data: result, isLoading } = useQuery({
    queryKey: ["run-result", runId],
    queryFn: () => api.getResult(runId),
    refetchInterval: status?.status === "running" ? 3000 : false,
  });

  // WebSocket progress for real-time updates
  const { progress, isConnected } = useBenchmarkProgress(
    runId,
    status?.status === "running"
  );

  const isRunning = status?.status === "running";
  const startedAt = status?.started_at ? new Date(status.started_at) : null;

  // 경과시간을 매초 업데이트
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!isRunning || !startedAt) {
      setElapsed(0);
      return;
    }

    // 초기값 설정
    setElapsed(Math.floor((Date.now() - startedAt.getTime()) / 1000));

    // 매초 업데이트
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt.getTime()) / 1000));
    }, 1000);

    return () => clearInterval(interval);
  }, [isRunning, startedAt]);

  // Real-time time-series data for running state
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesPoint[]>([]);
  const lastMetricsRef = useRef<{ ttft: number; throughput: number } | null>(null);

  // Accumulate time-series data from progress updates
  useEffect(() => {
    if (!isRunning) {
      setTimeSeriesData([]);
      lastMetricsRef.current = null;
      return;
    }

    if (progress?.metrics) {
      const m = progress.metrics;
      // Skip if metrics haven't changed
      if (
        lastMetricsRef.current &&
        lastMetricsRef.current.ttft === m.ttft_avg &&
        lastMetricsRef.current.throughput === m.throughput_current
      ) {
        return;
      }

      lastMetricsRef.current = { ttft: m.ttft_avg, throughput: m.throughput_current };

      const now = new Date();
      const newPoint: TimeSeriesPoint = {
        time: now.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
        timestamp: now.getTime(),
        ttft: m.ttft_avg,
        throughput: m.throughput_current,
      };

      setTimeSeriesData((prev) => {
        const updated = [...prev, newPoint];
        // Keep only last 60 points (rolling window)
        return updated.slice(-60);
      });
    }
  }, [isRunning, progress]);

  // 완료된 레벨 데이터 (API 결과)
  const completedChartData = useMemo(() => {
    return result?.results?.map((r: ConcurrencyResult) => ({
      concurrency: r.concurrency,
      throughput: r.throughput_tokens_per_sec,
      ttft_p50: r.ttft.p50,
      ttft_p99: r.ttft.p99,
      error_rate: r.error_rate_percent,
      goodput: r.goodput?.goodput_percent ?? null,
      isLive: false,
    })) ?? [];
  }, [result]);

  // 진행 중인 레벨의 실시간 메트릭
  const liveChartData = useMemo(() => {
    if (!isRunning || !progress?.metrics) return null;
    const m = progress.metrics;
    // 이미 완료된 레벨과 중복 방지
    const alreadyCompleted = completedChartData.some(
      (d) => d.concurrency === m.concurrency
    );
    if (alreadyCompleted) return null;

    return {
      concurrency: m.concurrency,
      throughput: m.throughput_current,
      ttft_p50: m.ttft_p50,
      ttft_p99: m.ttft_p50 * 1.5, // 진행 중이므로 p99는 추정값
      error_rate: m.error_count > 0 ? (m.error_count / m.completed) * 100 : 0,
      goodput: null,
      isLive: true, // 진행 중 표시
    };
  }, [isRunning, progress, completedChartData]);

  // 완료된 레벨 + 진행 중 레벨 병합
  const chartData = useMemo(() => {
    if (liveChartData) {
      return [...completedChartData, liveChartData];
    }
    return completedChartData;
  }, [completedChartData, liveChartData]);

  // Error state
  if (status?.status === "failed") {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Benchmark Result
        </h1>
        <div className="bg-red-50 dark:bg-red-900/20 rounded-xl p-6 text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600 dark:text-red-400">Benchmark failed</p>
        </div>
      </div>
    );
  }

  // Loading state (initial)
  if (isLoading && !result && !isRunning) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Benchmark Result
        </h1>
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-12 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading results...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {isRunning ? "Benchmark Running" : "Benchmark Result"}
          </h1>
          <p className="mt-1 text-gray-600 dark:text-gray-400">
            {status?.model} @ {status?.server_url}
          </p>
        </div>
        <div className={`flex items-center gap-2 ${isRunning ? "text-blue-600 dark:text-blue-400" : "text-green-600 dark:text-green-400"}`}>
          {isRunning ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              <span className="font-medium">진행 중</span>
            </>
          ) : (
            <>
              <CheckCircle className="h-5 w-5" />
              <span className="font-medium">완료</span>
            </>
          )}
        </div>
      </div>

      {/* Running Progress Panel */}
      {isRunning && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          {/* Dual Progress Bars */}
          <div className="space-y-4 mb-6">
            {/* Overall Progress */}
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-600 dark:text-gray-400">전체 진행률</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {(progress?.overall_percent ?? 0).toFixed(0)}%
                </span>
              </div>
              <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 transition-all duration-300"
                  style={{ width: `${progress?.overall_percent ?? 0}%` }}
                />
              </div>
            </div>

            {/* Level Progress */}
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-600 dark:text-gray-400">
                  레벨 진행률 (Level {(progress?.concurrency?.index ?? 0) + 1}/{progress?.concurrency?.total ?? "-"} - Concurrency {progress?.concurrency?.level ?? "-"})
                </span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {(progress?.progress?.percent ?? 0).toFixed(0)}%
                </span>
              </div>
              <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-500 transition-all duration-300"
                  style={{ width: `${progress?.progress?.percent ?? 0}%` }}
                />
              </div>
            </div>
          </div>

          {/* Current Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mb-1">
                <Activity className="h-3.5 w-3.5" />
                Concurrency
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {progress?.concurrency?.level ?? "-"}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {progress?.progress?.current ?? 0} / {progress?.progress?.total ?? "-"} 요청
              </div>
            </div>

            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mb-1">
                <Zap className="h-3.5 w-3.5" />
                현재 Throughput
              </div>
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {progress?.metrics?.throughput_current?.toFixed(1) ?? "-"}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                tok/s
              </div>
            </div>

            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mb-1">
                <Timer className="h-3.5 w-3.5" />
                평균 TTFT
              </div>
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {progress?.metrics?.ttft_avg?.toFixed(0) ?? "-"}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                ms (진행 중)
              </div>
            </div>

            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
              <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mb-1">
                <Clock className="h-3.5 w-3.5" />
                경과 시간
              </div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {Math.floor(elapsed / 60).toString().padStart(2, '0')}:{(elapsed % 60).toString().padStart(2, '0')}
              </div>
              <div className={`text-xs ${isConnected ? 'text-green-500' : 'text-yellow-500'}`}>
                {isConnected ? "● 실시간 연결" : "○ 폴링 모드"}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Real-time Time-Series Chart - Running 상태에서만 표시 */}
      {isRunning && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              실시간 성능 추이
            </h2>
            <span className="text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-2 py-1 rounded flex items-center gap-1">
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              실시간 모니터링
            </span>
          </div>
          <div className="h-64">
            {timeSeriesData.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={timeSeriesData}
                  margin={{ top: 10, right: 80, left: 20, bottom: 10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 11 }}
                    tickMargin={8}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 11 }}
                    tickMargin={8}
                    label={{
                      value: "Throughput (tok/s)",
                      angle: -90,
                      position: "insideLeft",
                      style: { textAnchor: 'middle', fontSize: 11 }
                    }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tick={{ fontSize: 11 }}
                    tickMargin={8}
                    label={{
                      value: "TTFT (ms)",
                      angle: 90,
                      position: "insideRight",
                      style: { textAnchor: 'middle', fontSize: 11 }
                    }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "rgb(31, 41, 55)",
                      border: "1px solid rgb(55, 65, 81)",
                      borderRadius: "0.5rem",
                      color: "white",
                      fontSize: 12,
                    }}
                    formatter={(value: number, name: string) => {
                      if (name === "Throughput") return [`${value.toFixed(1)} tok/s`, name];
                      return [`${value.toFixed(1)} ms`, name];
                    }}
                  />
                  <Legend
                    wrapperStyle={{ paddingTop: 10 }}
                    iconType="line"
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="throughput"
                    stroke="#2563eb"
                    name="Throughput"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="ttft"
                    stroke="#10b981"
                    name="TTFT"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-gray-500 dark:text-gray-400">
                <Loader2 className="h-8 w-8 animate-spin mb-3" />
                <p className="text-sm">메트릭 수집 대기 중...</p>
                <p className="text-xs mt-1">첫 번째 메트릭이 수신되면 차트가 표시됩니다</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Summary Cards - 완료 후에만 표시 (Running 중에는 숨김) */}
      {!isRunning && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            title="Best Throughput"
            value={result?.summary?.best_throughput?.toFixed(1) ?? "N/A"}
            unit="tok/s"
            icon={Gauge}
            trend="up"
          />
          <MetricCard
            title="Best TTFT (p50)"
            value={result?.summary?.best_ttft_p50?.toFixed(1) ?? "N/A"}
            unit="ms"
            icon={Clock}
            trend="up"
          />
          <MetricCard
            title="Best Concurrency"
            value={result?.summary?.best_concurrency ?? "N/A"}
            icon={Activity}
          />
          <MetricCard
            title="Error Rate"
            value={result?.summary?.overall_error_rate?.toFixed(2) ?? "0.00"}
            unit="%"
            icon={AlertCircle}
            trend={(result?.summary?.overall_error_rate ?? 0) > 1 ? "down" : "up"}
          />
        </div>
      )}

      {/* Goodput Summary - 완료 후에만 표시 */}
      {!isRunning && result?.summary?.avg_goodput_percent !== undefined && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Goodput
          </h2>
          <div className="flex items-center gap-4">
            <div className="text-4xl font-bold text-blue-600">
              {result.summary.avg_goodput_percent.toFixed(1)}%
            </div>
            <div className="text-gray-600 dark:text-gray-400">
              SLO 임계값을 만족하는 평균 요청 비율
            </div>
          </div>
        </div>
      )}

      {/* Chart - 완료 후에만 표시 */}
      {!isRunning && chartData.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Throughput & Latency by Concurrency
            </h2>
          </div>
          <div className="h-96">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={chartData}
                margin={{ top: 20, right: 80, left: 20, bottom: 20 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
                <XAxis
                  dataKey="concurrency"
                  tick={{ fontSize: 12 }}
                  tickMargin={10}
                />
                <YAxis
                  yAxisId="left"
                  tick={{ fontSize: 12 }}
                  tickMargin={10}
                  label={{
                    value: "Throughput (tok/s)",
                    angle: -90,
                    position: "insideLeft",
                    style: { textAnchor: 'middle', fontSize: 12 }
                  }}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fontSize: 12 }}
                  tickMargin={10}
                  label={{
                    value: "Latency (ms)",
                    angle: 90,
                    position: "insideRight",
                    style: { textAnchor: 'middle', fontSize: 12 }
                  }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "rgb(31, 41, 55)",
                    border: "1px solid rgb(55, 65, 81)",
                    borderRadius: "0.5rem",
                    color: "white",
                    fontSize: 12,
                  }}
                  formatter={(value: number, name: string) => {
                    if (name.includes("Throughput")) return [`${value.toFixed(1)} tok/s`, name];
                    return [`${value.toFixed(1)} ms`, name];
                  }}
                  labelFormatter={(label) => `Concurrency: ${label}`}
                />
                <Legend
                  wrapperStyle={{ paddingTop: 20 }}
                  iconType="line"
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="throughput"
                  stroke="#2563eb"
                  name="Throughput"
                  strokeWidth={2}
                  dot={{ r: 5, fill: "#2563eb" }}
                  activeDot={{ r: 7 }}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="ttft_p50"
                  stroke="#10b981"
                  name="TTFT p50"
                  strokeWidth={2}
                  dot={{ r: 5, fill: "#10b981" }}
                  activeDot={{ r: 7 }}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="ttft_p99"
                  stroke="#f59e0b"
                  name="TTFT p99"
                  strokeWidth={2}
                  dot={{ r: 5, fill: "#f59e0b" }}
                  activeDot={{ r: 7 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Results Table - 완료 후에만 표시 */}
      {!isRunning && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              상세 결과
            </h2>
            <div className="flex items-center gap-3">
              {result?.results && result.results.length > 0 && (
                <Link
                  href={`/benchmark/${runId}/analysis`}
                  className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 font-medium"
                >
                  <FileText className="h-4 w-4" />
                  AI 분석 보고서 →
                </Link>
              )}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                <th className="px-4 py-3 font-medium">Concurrency</th>
                <th className="px-4 py-3 font-medium">Throughput</th>
                <th className="px-4 py-3 font-medium">TTFT p50</th>
                <th className="px-4 py-3 font-medium">TTFT p99</th>
                <th className="px-4 py-3 font-medium">Error Rate</th>
                <th className="px-4 py-3 font-medium">Goodput</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {result?.results?.map((r: ConcurrencyResult) => (
                <tr key={r.concurrency} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                    {r.concurrency}
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {r.throughput_tokens_per_sec.toFixed(1)} tok/s
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {r.ttft.p50.toFixed(1)} ms
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {r.ttft.p99.toFixed(1)} ms
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {r.error_rate_percent.toFixed(2)}%
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-400">
                    {r.goodput ? `${r.goodput.goodput_percent.toFixed(1)}%` : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      )}
    </div>
  );
}
