"use client";

import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  recommendApi,
  RecommendRequest,
  RecommendResponse,
  RecommendStatus,
} from "@/lib/api";
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

export default function RecommendPage() {
  const router = useRouter();
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<RecommendStatus | null>(null);
  const [result, setResult] = useState<RecommendResponse | null>(null);

  const [config, setConfig] = useState({
    server_url: "http://localhost:8000",
    model: "",
    adapter: "openai",
    peak_concurrency: 500,
    ttft_target: 500,
    tpot_target: 50,
    goodput_target: 95,
    headroom: 20,
    concurrency_steps: "1,10,50,100,200",
    num_requests: 50,
    input_len: 256,
    output_len: 512,
    warmup: 3,
    timeout: 120,
    api_key: "",
  });

  const mutation = useMutation({
    mutationFn: (request: RecommendRequest) => recommendApi.startRecommend(request),
    onSuccess: (data) => {
      setRunId(data.run_id);
    },
  });

  // Poll for status
  useEffect(() => {
    if (!runId) return;

    const interval = setInterval(async () => {
      try {
        const newStatus = await recommendApi.getStatus(runId);
        setStatus(newStatus);

        if (newStatus.status === "completed") {
          clearInterval(interval);
          const resultData = await recommendApi.getResult(runId);
          setResult(resultData);
        } else if (newStatus.status === "failed") {
          clearInterval(interval);
        }
      } catch (error) {
        console.error("Failed to get status:", error);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [runId]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const request: RecommendRequest = {
      server_url: config.server_url,
      model: config.model,
      adapter: config.adapter,
      workload: {
        peak_concurrency: config.peak_concurrency,
        avg_input_tokens: config.input_len,
        avg_output_tokens: config.output_len,
        ttft_target_ms: config.ttft_target,
        tpot_target_ms: config.tpot_target,
        goodput_target_percent: config.goodput_target,
      },
      headroom_percent: config.headroom,
      test_config: {
        concurrency_steps: config.concurrency_steps.split(",").map(Number),
        num_requests_per_step: config.num_requests,
      },
      warmup: config.warmup,
      timeout: config.timeout,
      api_key: config.api_key || undefined,
    };

    mutation.mutate(request);
  };

  const handleReset = () => {
    setRunId(null);
    setStatus(null);
    setResult(null);
    mutation.reset();
  };

  // Show result view
  if (result) {
    const chartData = result.test_results.map((r) => ({
      concurrency: r.concurrency,
      throughput: r.throughput_tokens_per_sec,
      ttft_p95: r.ttft.p95,
      goodput: r.goodput?.goodput_percent ?? 100,
    }));

    return (
      <div className="max-w-5xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Infrastructure Recommendation
          </h1>
          <button
            onClick={handleReset}
            className="px-4 py-2 bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
          >
            New Recommendation
          </button>
        </div>

        {/* Recommendation Box */}
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-xl p-8 mb-6 text-white shadow-lg">
          <div className="text-center">
            <p className="text-blue-100 mb-2">Recommended Infrastructure</p>
            <div className="text-4xl font-bold mb-2">
              {result.recommendation.recommended_gpu} x {result.recommendation.recommended_count}
            </div>
            <p className="text-blue-100">
              Model: {result.recommendation.model_name}
            </p>
          </div>
        </div>

        {/* Info Cards */}
        <div className="grid grid-cols-2 gap-6 mb-6">
          {/* Current Infrastructure */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Current Infrastructure
            </h2>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">GPU</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {result.current_infra.gpu_model}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Count</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {result.current_infra.gpu_count}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Memory</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {result.current_infra.gpu_memory_gb.toFixed(1)} GB
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Max Concurrency</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {result.current_infra.max_concurrency_at_slo}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Throughput</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {result.current_infra.throughput_tokens_per_sec.toFixed(1)} tok/s
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Saturation Point</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {result.current_infra.saturation_concurrency} concurrent
                </span>
              </div>
            </div>
          </div>

          {/* Estimated Performance */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Estimated Performance
            </h2>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Max Concurrency</span>
                <span className="font-medium text-green-600 dark:text-green-400">
                  {result.recommendation.estimated_max_concurrency} users
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Est. Goodput</span>
                <span className="font-medium text-green-600 dark:text-green-400">
                  {result.recommendation.estimated_goodput.toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Est. Throughput</span>
                <span className="font-medium text-green-600 dark:text-green-400">
                  {result.recommendation.estimated_throughput.toFixed(1)} tok/s
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Tensor Parallelism</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {result.recommendation.tensor_parallelism}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Headroom</span>
                <span className="font-medium text-gray-900 dark:text-white">
                  {result.recommendation.headroom_percent}%
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Calculation */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Calculation Details
          </h2>
          <div className="space-y-4">
            <div>
              <span className="text-sm text-gray-500 dark:text-gray-400">Formula</span>
              <p className="font-mono text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-700 px-3 py-2 rounded">
                {result.recommendation.calculation_formula}
              </p>
            </div>
            <div>
              <span className="text-sm text-gray-500 dark:text-gray-400">Reasoning</span>
              <p className="text-gray-700 dark:text-gray-300">
                {result.recommendation.reasoning}
              </p>
            </div>
          </div>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-2 gap-6 mb-6">
          {/* Throughput Chart */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Throughput by Concurrency
            </h2>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="concurrency" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="throughput"
                  stroke="#2563eb"
                  strokeWidth={2}
                  name="Throughput (tok/s)"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Goodput Chart */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Goodput by Concurrency
            </h2>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="concurrency" />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="goodput"
                  stroke="#16a34a"
                  strokeWidth={2}
                  name="Goodput (%)"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Duration */}
        <div className="text-sm text-gray-500 dark:text-gray-400 text-center">
          Analysis completed in {result.duration_seconds.toFixed(1)} seconds
        </div>
      </div>
    );
  }

  // Show progress view
  if (status) {
    return (
      <div className="max-w-3xl">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">
          Infrastructure Recommendation
        </h1>

        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-8 text-center">
          {status.status === "running" && (
            <>
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                Analyzing Infrastructure...
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Running load tests at multiple concurrency levels to profile your server.
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-4">
                This may take several minutes depending on your test configuration.
              </p>
            </>
          )}
          {status.status === "pending" && (
            <>
              <div className="h-12 w-12 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">...</span>
              </div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                Starting Analysis
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Initializing recommendation process...
              </p>
            </>
          )}
          {status.status === "failed" && (
            <>
              <div className="h-12 w-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl text-red-600">!</span>
              </div>
              <h2 className="text-xl font-semibold text-red-600 mb-2">
                Analysis Failed
              </h2>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                {status.error || "An error occurred during analysis."}
              </p>
              <button
                onClick={handleReset}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Try Again
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  // Show form
  return (
    <div className="max-w-3xl">
      <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-6">
        Infrastructure Recommendation
      </h1>

      <div className="bg-blue-50 dark:bg-blue-900/30 rounded-xl p-4 mb-6">
        <p className="text-blue-800 dark:text-blue-200 text-sm">
          This tool profiles your LLM server and recommends the number of GPUs needed
          to handle your target workload with specified SLO requirements.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Server Settings */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Server Settings
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Server URL
              </label>
              <input
                type="text"
                value={config.server_url}
                onChange={(e) => setConfig({ ...config, server_url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="http://localhost:8000"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Model Name
              </label>
              <input
                type="text"
                value={config.model}
                onChange={(e) => setConfig({ ...config, model: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="qwen3-14b"
                required
              />
            </div>
          </div>
        </div>

        {/* Workload Requirements */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Target Workload
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Peak Concurrency *
              </label>
              <input
                type="number"
                value={config.peak_concurrency}
                onChange={(e) => setConfig({ ...config, peak_concurrency: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                required
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Target peak concurrent users
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Headroom (%)
              </label>
              <input
                type="number"
                value={config.headroom}
                onChange={(e) => setConfig({ ...config, headroom: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Safety margin percentage
              </p>
            </div>
          </div>
        </div>

        {/* SLO Targets */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            SLO Targets
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                TTFT Target (ms)
              </label>
              <input
                type="number"
                value={config.ttft_target}
                onChange={(e) => setConfig({ ...config, ttft_target: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Time to First Token
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                TPOT Target (ms)
              </label>
              <input
                type="number"
                value={config.tpot_target}
                onChange={(e) => setConfig({ ...config, tpot_target: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Time Per Output Token
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Goodput Target (%)
              </label>
              <input
                type="number"
                value={config.goodput_target}
                onChange={(e) => setConfig({ ...config, goodput_target: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Requests meeting SLO
              </p>
            </div>
          </div>
        </div>

        {/* Test Configuration */}
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Test Configuration
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Concurrency Steps
              </label>
              <input
                type="text"
                value={config.concurrency_steps}
                onChange={(e) => setConfig({ ...config, concurrency_steps: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                placeholder="1,10,50,100,200"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Concurrency levels to test (comma-separated)
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Requests per Step
              </label>
              <input
                type="number"
                value={config.num_requests}
                onChange={(e) => setConfig({ ...config, num_requests: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Number of requests per concurrency level
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Avg Input Tokens
              </label>
              <input
                type="number"
                value={config.input_len}
                onChange={(e) => setConfig({ ...config, input_len: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Avg Output Tokens
              </label>
              <input
                type="number"
                value={config.output_len}
                onChange={(e) => setConfig({ ...config, output_len: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex gap-4">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {mutation.isPending ? "Starting..." : "Start Analysis"}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="px-6 py-2 bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 font-medium"
          >
            Cancel
          </button>
        </div>

        {mutation.error && (
          <p className="text-red-500 text-sm">
            Error: {(mutation.error as Error).message}
          </p>
        )}
      </form>
    </div>
  );
}
