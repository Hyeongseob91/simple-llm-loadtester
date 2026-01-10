/**
 * API client for LLM Loadtest backend.
 */

export const API_BASE = "/api/v1/benchmark";

export interface GoodputThresholds {
  ttft_ms?: number;
  tpot_ms?: number;
  e2e_ms?: number;
}

export interface BenchmarkConfig {
  server_url: string;
  model: string;
  adapter: string;
  concurrency: number[];
  num_prompts: number;
  input_len: number;
  output_len: number;
  stream: boolean;
  warmup: number;
  timeout: number;
  api_key?: string;
  duration_seconds?: number;
  goodput_thresholds?: GoodputThresholds;
}

export interface BenchmarkStatus {
  run_id: string;
  status: string;
  server_url: string;
  model: string;
  adapter: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface LatencyStats {
  min: number;
  max: number;
  mean: number;
  p50: number;
  p95: number;
  p99: number;
}

export interface GoodputResult {
  satisfied_requests: number;
  total_requests: number;
  goodput_percent: number;
}

export interface ConcurrencyResult {
  concurrency: number;
  ttft: LatencyStats;
  tpot?: LatencyStats;
  e2e_latency: LatencyStats;
  throughput_tokens_per_sec: number;
  request_rate_per_sec: number;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  error_rate_percent: number;
  goodput?: GoodputResult;
}

export interface BenchmarkResult {
  run_id: string;
  server_url: string;
  model: string;
  adapter: string;
  results: ConcurrencyResult[];
  summary: {
    best_throughput: number;
    best_ttft_p50: number;
    best_concurrency: number;
    total_requests: number;
    overall_error_rate: number;
    avg_goodput_percent?: number;
  };
  started_at: string;
  completed_at: string;
  duration_seconds: number;
}

export interface RunListResponse {
  runs: BenchmarkStatus[];
  total: number;
  limit: number;
  offset: number;
}

export interface ComparisonMetric {
  run_id: string;
  value: number;
  concurrency?: number;
}

export interface ComparisonResult {
  run_count: number;
  best_throughput: ComparisonMetric;
  best_ttft: ComparisonMetric;
  by_concurrency: Record<string, unknown>;
}

class ApiClient {
  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Health check
  async health(): Promise<{ status: string; version: string }> {
    return this.request<{ status: string; version: string }>("/health");
  }

  // Start benchmark
  async startBenchmark(config: BenchmarkConfig): Promise<{ run_id: string; status: string }> {
    return this.request<{ run_id: string; status: string }>("/run", {
      method: "POST",
      body: JSON.stringify(config),
    });
  }

  // Get run status
  async getRunStatus(runId: string): Promise<BenchmarkStatus> {
    return this.request<BenchmarkStatus>(`/run/${runId}`);
  }

  // Get result
  async getResult(runId: string): Promise<BenchmarkResult> {
    return this.request<BenchmarkResult>(`/result/${runId}`);
  }

  // List runs
  async listRuns(params?: {
    limit?: number;
    offset?: number;
    status?: string;
  }): Promise<RunListResponse> {
    const query = new URLSearchParams();
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.offset) query.set("offset", String(params.offset));
    if (params?.status) query.set("status", params.status);

    return this.request<RunListResponse>(`/history?${query.toString()}`);
  }

  // Delete run
  async deleteRun(runId: string): Promise<void> {
    await this.request(`/run/${runId}`, { method: "DELETE" });
  }

  // Compare runs
  async compareRuns(runIds: string[]): Promise<{ comparison: ComparisonResult }> {
    return this.request<{ comparison: ComparisonResult }>("/compare", {
      method: "POST",
      body: JSON.stringify({ run_ids: runIds }),
    });
  }
}

export const api = new ApiClient();
