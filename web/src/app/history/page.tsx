"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Trash2 } from "lucide-react";
import { api } from "@/lib/api";

export default function HistoryPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["runs-history"],
    queryFn: () => api.listRuns({ limit: 50 }),
  });

  const deleteMutation = useMutation({
    mutationFn: (runId: string) => api.deleteRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs-history"] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          History
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          All benchmark runs
        </p>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
        {isLoading ? (
          <div className="p-6 text-center text-gray-500">Loading...</div>
        ) : error ? (
          <div className="p-6 text-center text-red-500">
            Error: {error instanceof Error ? error.message : "An unknown error occurred"}
          </div>
        ) : !data?.runs.length ? (
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
                  <th className="px-6 py-3 font-medium">Run ID</th>
                  <th className="px-6 py-3 font-medium">Model</th>
                  <th className="px-6 py-3 font-medium">Server</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                  <th className="px-6 py-3 font-medium">Created</th>
                  <th className="px-6 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {data.runs.map((run) => (
                  <tr
                    key={run.run_id}
                    className="hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  >
                    <td className="px-6 py-4 font-mono text-sm text-gray-600 dark:text-gray-400">
                      {run.run_id.slice(0, 8)}...
                    </td>
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
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/benchmark/${run.run_id}`}
                          className="text-blue-600 hover:text-blue-700 dark:text-blue-400 text-sm font-medium"
                        >
                          View
                        </Link>
                        <button
                          onClick={() => {
                            if (confirm("Delete this run?")) {
                              deleteMutation.mutate(run.run_id);
                            }
                          }}
                          className="text-red-600 hover:text-red-700 dark:text-red-400 p-1"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
