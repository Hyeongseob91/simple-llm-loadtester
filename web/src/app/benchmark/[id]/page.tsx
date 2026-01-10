"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { MetricCard } from "@/components/metric-card";
import { Gauge, Clock, Activity, AlertCircle, CheckCircle } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Brush,
} from "recharts";

export default function BenchmarkResultPage() {
  const params = useParams();
  const runId = params.id as string;

  const { data: status } = useQuery({
    queryKey: ["run-status", runId],
    queryFn: () => api.getRunStatus(runId),
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 2000 : false,
  });

  const { data: result, isLoading, error } = useQuery({
    queryKey: ["run-result", runId],
    queryFn: () => api.getResult(runId),
    enabled: status?.status === "completed",
  });

  if (isLoading || status?.status === "running") {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Benchmark Result
        </h1>
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-12 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">
            {status?.status === "running"
              ? "Benchmark in progress..."
              : "Loading results..."}
          </p>
        </div>
      </div>
    );
  }

  if (error || status?.status === "failed") {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Benchmark Result
        </h1>
        <div className="bg-red-50 dark:bg-red-900/20 rounded-xl p-6 text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-600 dark:text-red-400">
            {status?.status === "failed"
              ? "Benchmark failed"
              : error instanceof Error
              ? error.message
              : "An unknown error occurred"}
          </p>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Benchmark Result
        </h1>
        <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-6 text-center">
          <p className="text-gray-600 dark:text-gray-400">No result found</p>
        </div>
      </div>
    );
  }

  const chartData = result.results.map((r) => ({
    concurrency: r.concurrency,
    throughput: r.throughput_tokens_per_sec,
    ttft_p50: r.ttft.p50,
    ttft_p99: r.ttft.p99,
    error_rate: r.error_rate_percent,
    goodput: r.goodput?.goodput_percent ?? null,
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Benchmark Result
          </h1>
          <p className="mt-1 text-gray-600 dark:text-gray-400">
            {result.model} @ {result.server_url}
          </p>
        </div>
        <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
          <CheckCircle className="h-5 w-5" />
          <span className="font-medium">Completed</span>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Best Throughput"
          value={result.summary.best_throughput.toFixed(1)}
          unit="tok/s"
          icon={Gauge}
          trend="up"
        />
        <MetricCard
          title="Best TTFT (p50)"
          value={result.summary.best_ttft_p50.toFixed(1)}
          unit="ms"
          icon={Clock}
          trend="up"
        />
        <MetricCard
          title="Best Concurrency"
          value={result.summary.best_concurrency}
          icon={Activity}
        />
        <MetricCard
          title="Error Rate"
          value={result.summary.overall_error_rate.toFixed(2)}
          unit="%"
          icon={AlertCircle}
          trend={result.summary.overall_error_rate > 1 ? "down" : "up"}
        />
      </div>

      {/* Goodput Summary */}
      {result.summary.avg_goodput_percent !== undefined && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Goodput
          </h2>
          <div className="flex items-center gap-4">
            <div className="text-4xl font-bold text-blue-600">
              {result.summary.avg_goodput_percent.toFixed(1)}%
            </div>
            <div className="text-gray-600 dark:text-gray-400">
              Average requests meeting SLO thresholds
            </div>
          </div>
        </div>
      )}

      {/* Combined Throughput & Latency Chart with Multi Y-Axis */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Throughput & Latency by Concurrency
        </h2>
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
              <XAxis
                dataKey="concurrency"
                label={{ value: "Concurrency", position: "insideBottom", offset: -5 }}
                className="text-gray-600 dark:text-gray-400"
              />
              <YAxis
                yAxisId="left"
                label={{ value: "Throughput (tok/s)", angle: -90, position: "insideLeft" }}
                className="text-gray-600 dark:text-gray-400"
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                label={{ value: "Latency (ms)", angle: 90, position: "insideRight" }}
                className="text-gray-600 dark:text-gray-400"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "rgb(31, 41, 55)",
                  border: "1px solid rgb(55, 65, 81)",
                  borderRadius: "0.5rem",
                  color: "white",
                }}
              />
              <Legend />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="throughput"
                stroke="#2563eb"
                name="Throughput (tok/s)"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="ttft_p50"
                stroke="#10b981"
                name="TTFT p50 (ms)"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="ttft_p99"
                stroke="#f59e0b"
                name="TTFT p99 (ms)"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
              <Brush
                dataKey="concurrency"
                height={30}
                stroke="#2563eb"
                fill="rgb(31, 41, 55)"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Error Rate & Goodput Chart */}
      {result.results.some(r => r.goodput) && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Error Rate & Goodput by Concurrency
          </h2>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
                <XAxis
                  dataKey="concurrency"
                  label={{ value: "Concurrency", position: "insideBottom", offset: -5 }}
                  className="text-gray-600 dark:text-gray-400"
                />
                <YAxis
                  label={{ value: "Percentage (%)", angle: -90, position: "insideLeft" }}
                  className="text-gray-600 dark:text-gray-400"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "rgb(31, 41, 55)",
                    border: "1px solid rgb(55, 65, 81)",
                    borderRadius: "0.5rem",
                    color: "white",
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="error_rate"
                  stroke="#ef4444"
                  name="Error Rate (%)"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
                <Line
                  type="monotone"
                  dataKey="goodput"
                  stroke="#10b981"
                  name="Goodput (%)"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
                <Brush
                  dataKey="concurrency"
                  height={30}
                  stroke="#2563eb"
                  fill="rgb(31, 41, 55)"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Results Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Detailed Results
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                <th className="px-6 py-3 font-medium">Concurrency</th>
                <th className="px-6 py-3 font-medium">Throughput</th>
                <th className="px-6 py-3 font-medium">TTFT p50</th>
                <th className="px-6 py-3 font-medium">TTFT p99</th>
                <th className="px-6 py-3 font-medium">Error Rate</th>
                {result.results[0]?.goodput && (
                  <th className="px-6 py-3 font-medium">Goodput</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {result.results.map((r) => (
                <tr key={r.concurrency}>
                  <td className="px-6 py-4 font-medium text-gray-900 dark:text-white">
                    {r.concurrency}
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                    {r.throughput_tokens_per_sec.toFixed(1)} tok/s
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                    {r.ttft.p50.toFixed(1)} ms
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                    {r.ttft.p99.toFixed(1)} ms
                  </td>
                  <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                    {r.error_rate_percent.toFixed(2)}%
                  </td>
                  {r.goodput && (
                    <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                      {r.goodput.goodput_percent.toFixed(1)}%
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
