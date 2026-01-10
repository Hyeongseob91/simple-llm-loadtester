"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, Clock, Gauge, AlertCircle } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { MetricCard } from "@/components/metric-card";

export default function DashboardPage() {
  const { data: runs, isLoading, error } = useQuery({
    queryKey: ["runs"],
    queryFn: () => api.listRuns({ limit: 10 }),
  });

  const recentRuns = runs?.runs ?? [];
  const completedRuns = recentRuns.filter((r) => r.status === "completed");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Dashboard
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          LLM server load testing overview
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Total Runs"
          value={runs?.total ?? 0}
          icon={Activity}
        />
        <MetricCard
          title="Completed"
          value={completedRuns.length}
          icon={Gauge}
          trend="up"
        />
        <MetricCard
          title="Running"
          value={recentRuns.filter((r) => r.status === "running").length}
          icon={Clock}
          trend="neutral"
        />
        <MetricCard
          title="Failed"
          value={recentRuns.filter((r) => r.status === "failed").length}
          icon={AlertCircle}
          trend="down"
        />
      </div>

      {/* Recent Runs */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Recent Runs
            </h2>
            <Link
              href="/history"
              className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400"
            >
              View all →
            </Link>
          </div>
        </div>

        {isLoading ? (
          <div className="p-6 text-center text-gray-500">Loading...</div>
        ) : error ? (
          <div className="p-6 text-center text-red-500">
            Error loading runs: {error instanceof Error ? error.message : "An unknown error occurred"}
          </div>
        ) : recentRuns.length === 0 ? (
          <div className="p-6 text-center text-gray-500">
            No benchmark runs yet.{" "}
            <Link
              href="/benchmark/new"
              className="text-blue-600 hover:text-blue-700"
            >
              Start your first test
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                  <th className="px-6 py-3 font-medium">Model</th>
                  <th className="px-6 py-3 font-medium">Server</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                  <th className="px-6 py-3 font-medium">Created</th>
                  <th className="px-6 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {recentRuns.map((run) => (
                  <tr
                    key={run.run_id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  >
                    <td className="px-6 py-4 font-medium text-gray-900 dark:text-white">
                      {run.model}
                    </td>
                    <td className="px-6 py-4 text-gray-600 dark:text-gray-400 text-sm">
                      {run.server_url}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          run.status === "completed"
                            ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                            : run.status === "running"
                            ? "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400"
                            : run.status === "failed"
                            ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
                            : "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300"
                        }`}
                      >
                        {run.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-600 dark:text-gray-400 text-sm">
                      {new Date(run.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4">
                      <Link
                        href={`/benchmark/${run.run_id}`}
                        className="text-blue-600 hover:text-blue-700 dark:text-blue-400 text-sm font-medium"
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Quick Actions
        </h2>
        <div className="flex gap-4">
          <Link
            href="/benchmark/new"
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            New Benchmark
          </Link>
          <Link
            href="/compare"
            className="px-4 py-2 bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors font-medium"
          >
            Compare Results
          </Link>
        </div>
      </div>
    </div>
  );
}
