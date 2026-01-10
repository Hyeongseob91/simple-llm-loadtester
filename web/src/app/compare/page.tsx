"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";

export default function ComparePage() {
  const [selectedRuns, setSelectedRuns] = useState<string[]>([]);

  const { data: runs } = useQuery({
    queryKey: ["runs-for-compare"],
    queryFn: () => api.listRuns({ limit: 50, status: "completed" }),
  });

  const { data: comparison, isLoading: isComparing } = useQuery({
    queryKey: ["comparison", selectedRuns],
    queryFn: () => api.compareRuns(selectedRuns),
    enabled: selectedRuns.length >= 2,
  });

  const { data: selectedResults } = useQuery({
    queryKey: ["selected-results", selectedRuns],
    queryFn: async () => {
      return Promise.all(selectedRuns.map(id => api.getResult(id)));
    },
    enabled: selectedRuns.length >= 2,
  });

  const toggleRun = (runId: string) => {
    setSelectedRuns((prev) =>
      prev.includes(runId)
        ? prev.filter((id) => id !== runId)
        : prev.length < 5
        ? [...prev, runId]
        : prev
    );
  };

  const comparisonTableData = useMemo(() => {
    if (!selectedResults) return [];

    return selectedResults.map(result => ({
      run_id: result.run_id.slice(0, 8),
      model: result.model,
      best_throughput: result.summary.best_throughput,
      best_ttft: result.summary.best_ttft_p50,
      best_concurrency: result.summary.best_concurrency,
      error_rate: result.summary.overall_error_rate,
      goodput: result.summary.avg_goodput_percent,
    }));
  }, [selectedResults]);

  const concurrencyComparisonData = useMemo(() => {
    if (!selectedResults) return [];

    const allConcurrencies = new Set<number>();
    selectedResults.forEach(result => {
      result.results.forEach(r => allConcurrencies.add(r.concurrency));
    });

    return Array.from(allConcurrencies).sort((a, b) => a - b).map(concurrency => {
      const dataPoint: any = { concurrency };
      selectedResults.forEach((result, idx) => {
        const concurrencyResult = result.results.find(r => r.concurrency === concurrency);
        if (concurrencyResult) {
          dataPoint[`throughput_${idx}`] = concurrencyResult.throughput_tokens_per_sec;
          dataPoint[`model_${idx}`] = result.model;
        }
      });
      return dataPoint;
    });
  }, [selectedResults]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Compare Results
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Select 2-5 benchmark runs to compare
        </p>
      </div>

      {/* Run Selection */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Select Runs ({selectedRuns.length}/5)
        </h2>

        <div className="space-y-2 max-h-96 overflow-y-auto">
          {runs?.runs.map((run) => (
            <label
              key={run.run_id}
              className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${
                selectedRuns.includes(run.run_id)
                  ? "bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700"
                  : "bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700"
              }`}
            >
              <input
                type="checkbox"
                checked={selectedRuns.includes(run.run_id)}
                onChange={() => toggleRun(run.run_id)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <div className="flex-1">
                <div className="font-medium text-gray-900 dark:text-white">
                  {run.model}
                </div>
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  {run.server_url} • {new Date(run.created_at).toLocaleString()}
                </div>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Comparison Results */}
      {selectedRuns.length >= 2 && (
        <>
          {/* Summary Cards */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Best Results
            </h2>

            {isComparing ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">Comparing...</div>
            ) : comparison ? (
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <div className="text-sm text-green-600 dark:text-green-400 font-medium">
                    Best Throughput
                  </div>
                  <div className="text-2xl font-bold text-green-700 dark:text-green-300">
                    {comparison.comparison.best_throughput?.value?.toFixed(1) ?? "N/A"} tok/s
                  </div>
                  <div className="text-sm text-green-600 dark:text-green-400">
                    Run: {comparison.comparison.best_throughput?.run_id?.slice(0, 8) ?? "N/A"}...
                  </div>
                </div>
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <div className="text-sm text-blue-600 dark:text-blue-400 font-medium">
                    Best TTFT (p50)
                  </div>
                  <div className="text-2xl font-bold text-blue-700 dark:text-blue-300">
                    {comparison.comparison.best_ttft?.value?.toFixed(1) ?? "N/A"} ms
                  </div>
                  <div className="text-sm text-blue-600 dark:text-blue-400">
                    Run: {comparison.comparison.best_ttft?.run_id?.slice(0, 8) ?? "N/A"}...
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          {/* Model Comparison Table */}
          {comparisonTableData.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Model Comparison
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="px-6 py-3 font-medium">Run ID</th>
                      <th className="px-6 py-3 font-medium">Model</th>
                      <th className="px-6 py-3 font-medium">Best Throughput</th>
                      <th className="px-6 py-3 font-medium">Best TTFT</th>
                      <th className="px-6 py-3 font-medium">Best Concurrency</th>
                      <th className="px-6 py-3 font-medium">Error Rate</th>
                      {comparisonTableData.some(d => d.goodput) && (
                        <th className="px-6 py-3 font-medium">Goodput</th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {comparisonTableData.map((data) => (
                      <tr key={data.run_id}>
                        <td className="px-6 py-4 font-mono text-sm text-gray-900 dark:text-white">
                          {data.run_id}
                        </td>
                        <td className="px-6 py-4 font-medium text-gray-900 dark:text-white">
                          {data.model}
                        </td>
                        <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                          {data.best_throughput.toFixed(1)} tok/s
                        </td>
                        <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                          {data.best_ttft.toFixed(1)} ms
                        </td>
                        <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                          {data.best_concurrency}
                        </td>
                        <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                          {data.error_rate.toFixed(2)}%
                        </td>
                        {comparisonTableData.some(d => d.goodput) && (
                          <td className="px-6 py-4 text-gray-600 dark:text-gray-400">
                            {data.goodput ? `${data.goodput.toFixed(1)}%` : "N/A"}
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Concurrency Comparison Chart */}
          {concurrencyComparisonData.length > 0 && selectedResults && (
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Throughput by Concurrency - Model Comparison
              </h2>
              <div className="h-96">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={concurrencyComparisonData}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
                    <XAxis
                      dataKey="concurrency"
                      label={{ value: "Concurrency", position: "insideBottom", offset: -5 }}
                      className="text-gray-600 dark:text-gray-400"
                    />
                    <YAxis
                      label={{ value: "Throughput (tok/s)", angle: -90, position: "insideLeft" }}
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
                    {selectedResults.map((result, idx) => (
                      <Line
                        key={result.run_id}
                        type="monotone"
                        dataKey={`throughput_${idx}`}
                        name={`${result.model} (${result.run_id.slice(0, 8)})`}
                        stroke={["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"][idx]}
                        strokeWidth={2}
                        dot={{ r: 4 }}
                        activeDot={{ r: 6 }}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
