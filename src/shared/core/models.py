"""Data models for LLM load testing."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LatencyStats(BaseModel):
    """Latency statistics in milliseconds."""

    min: float = Field(description="Minimum latency (ms)")
    max: float = Field(description="Maximum latency (ms)")
    mean: float = Field(description="Mean latency (ms)")
    median: float = Field(description="Median latency (ms)")
    p50: float = Field(description="50th percentile (ms)")
    p95: float = Field(description="95th percentile (ms)")
    p99: float = Field(description="99th percentile (ms)")
    std: float = Field(description="Standard deviation (ms)")


class GoodputThresholds(BaseModel):
    """SLO thresholds for Goodput calculation."""

    ttft_ms: Optional[float] = Field(default=None, description="TTFT threshold (ms)")
    tpot_ms: Optional[float] = Field(default=None, description="TPOT threshold (ms)")
    e2e_ms: Optional[float] = Field(default=None, description="E2E latency threshold (ms)")


class GoodputResult(BaseModel):
    """Goodput measurement result."""

    thresholds: GoodputThresholds = Field(description="SLO thresholds used")
    satisfied_requests: int = Field(description="Requests meeting all SLOs")
    total_requests: int = Field(description="Total requests")
    goodput_percent: float = Field(description="Percentage meeting SLOs")

    # Per-threshold breakdown
    ttft_satisfied: Optional[int] = Field(default=None, description="Requests meeting TTFT SLO")
    tpot_satisfied: Optional[int] = Field(default=None, description="Requests meeting TPOT SLO")
    e2e_satisfied: Optional[int] = Field(default=None, description="Requests meeting E2E SLO")


class GPUMetrics(BaseModel):
    """GPU metrics during benchmark."""

    device_name: str = Field(description="GPU device name")
    gpu_index: int = Field(default=0, description="GPU index")
    memory_used_gb: float = Field(description="Used memory in GB")
    memory_total_gb: float = Field(description="Total memory in GB")
    memory_util_percent: float = Field(description="Memory utilization percentage")
    gpu_util_percent: float = Field(description="GPU utilization percentage")
    temperature_celsius: Optional[float] = Field(default=None, description="GPU temperature")
    power_draw_watts: Optional[float] = Field(default=None, description="Power consumption")


class RequestResult(BaseModel):
    """Individual request result."""

    request_id: int = Field(description="Request identifier")
    ttft_ms: float = Field(description="Time to first token (ms)")
    tpot_ms: Optional[float] = Field(default=None, description="Time per output token (ms)")
    e2e_latency_ms: float = Field(description="End-to-end latency (ms)")
    input_tokens: int = Field(description="Number of input tokens")
    output_tokens: int = Field(description="Number of output tokens")
    success: bool = Field(default=True, description="Request success status")
    error_type: Optional[str] = Field(default=None, description="Error type if failed")
    itl_ms: Optional[list[float]] = Field(default=None, description="Inter-token latencies")


class BenchmarkConfig(BaseModel):
    """Benchmark configuration."""

    server_url: str = Field(description="Server URL")
    model: str = Field(description="Model name")
    adapter: str = Field(default="openai", description="Server adapter type")
    input_len: int = Field(default=256, description="Input token length")
    output_len: int = Field(default=128, description="Output token length")
    num_prompts: int = Field(default=100, description="Number of prompts to send")
    concurrency: list[int] = Field(default=[1], description="Concurrency levels to test")
    stream: bool = Field(default=True, description="Enable streaming")
    warmup: int = Field(default=3, description="Number of warmup requests")
    timeout: float = Field(default=120.0, description="Request timeout (seconds)")
    api_key: Optional[str] = Field(default=None, description="API key")

    # Duration mode (alternative to num_prompts)
    duration_seconds: Optional[int] = Field(default=None, description="Test duration in seconds")

    # Goodput thresholds
    goodput_thresholds: Optional[GoodputThresholds] = Field(
        default=None, description="SLO thresholds for Goodput"
    )


class ConcurrencyResult(BaseModel):
    """Results for a specific concurrency level."""

    concurrency: int = Field(description="Concurrency level")
    ttft: LatencyStats = Field(description="TTFT statistics")
    tpot: Optional[LatencyStats] = Field(default=None, description="TPOT statistics")
    itl: Optional[LatencyStats] = Field(default=None, description="ITL statistics")
    e2e_latency: LatencyStats = Field(description="E2E latency statistics")
    throughput_tokens_per_sec: float = Field(description="Tokens per second")
    request_rate_per_sec: float = Field(description="Requests per second")
    total_requests: int = Field(description="Total requests")
    successful_requests: int = Field(description="Successful requests")
    failed_requests: int = Field(description="Failed requests")
    error_rate_percent: float = Field(description="Error rate percentage")
    total_input_tokens: int = Field(description="Total input tokens")
    total_output_tokens: int = Field(description="Total output tokens")
    duration_seconds: float = Field(description="Test duration in seconds")

    # Goodput (optional)
    goodput: Optional[GoodputResult] = Field(default=None, description="Goodput result")


class BenchmarkResult(BaseModel):
    """Complete benchmark result."""

    run_id: str = Field(description="Unique run identifier")
    server_url: str = Field(description="Server URL")
    model: str = Field(description="Model name")
    adapter: str = Field(default="openai", description="Adapter type")
    config: BenchmarkConfig = Field(description="Benchmark configuration")
    results: list[ConcurrencyResult] = Field(description="Results per concurrency level")
    gpu_metrics: Optional[GPUMetrics] = Field(default=None, description="GPU metrics (deprecated)")
    started_at: datetime = Field(description="Start timestamp")
    completed_at: datetime = Field(description="Completion timestamp")
    duration_seconds: float = Field(description="Total duration in seconds")

    # Server infrastructure info (for AI analysis)
    server_infra: Optional["ServerInfraInfo"] = Field(
        default=None, description="Server infrastructure captured at benchmark start"
    )

    # Validation result (Prometheus + Docker logs)
    validation: Optional["ValidationResult"] = Field(
        default=None, description="Cross-validation result against server metrics"
    )

    def get_summary(self) -> dict:
        """Get summary of best results across concurrency levels."""
        if not self.results:
            return {}

        best_throughput = max(r.throughput_tokens_per_sec for r in self.results)
        best_ttft = min(r.ttft.p50 for r in self.results)
        best_result = max(self.results, key=lambda r: r.throughput_tokens_per_sec)

        summary = {
            "best_throughput": best_throughput,
            "best_ttft_p50": best_ttft,
            "best_concurrency": best_result.concurrency,
            "total_requests": sum(r.total_requests for r in self.results),
            "overall_error_rate": (
                sum(r.failed_requests for r in self.results)
                / sum(r.total_requests for r in self.results)
                * 100
                if self.results
                else 0
            ),
        }

        # Add Goodput if available
        goodput_results = [r.goodput for r in self.results if r.goodput]
        if goodput_results:
            avg_goodput = sum(g.goodput_percent for g in goodput_results) / len(goodput_results)
            summary["avg_goodput_percent"] = avg_goodput

        return summary


# ============================================================
# Phase 5: Infrastructure Recommendation Models
# ============================================================


class WorkloadSpec(BaseModel):
    """User-defined workload specification for infrastructure recommendation."""

    # Traffic scale
    daily_active_users: Optional[int] = Field(
        default=None, description="Daily Active Users (DAU)"
    )
    peak_concurrency: int = Field(description="Peak concurrent requests (required)")
    requests_per_user_per_day: int = Field(
        default=10, description="Requests per user per day"
    )

    # Request characteristics
    avg_input_tokens: int = Field(default=256, description="Average input tokens")
    avg_output_tokens: int = Field(default=512, description="Average output tokens")

    # SLO requirements
    ttft_target_ms: float = Field(default=500.0, description="TTFT target (ms)")
    tpot_target_ms: float = Field(default=50.0, description="TPOT target (ms)")
    goodput_target_percent: float = Field(default=95.0, description="Goodput target (%)")


class InfraProfile(BaseModel):
    """Measured GPU infrastructure performance profile."""

    # GPU information
    gpu_model: str = Field(description="GPU model name (e.g., 'NVIDIA H100')")
    gpu_count: int = Field(description="Current GPU count")
    gpu_memory_gb: float = Field(description="Total VRAM in GB")

    # Measured performance (from load test)
    max_concurrency_at_slo: int = Field(
        description="Maximum concurrency meeting SLO requirements"
    )
    throughput_tokens_per_sec: float = Field(description="Throughput (tokens/sec)")
    goodput_at_max_concurrency: float = Field(
        description="Goodput percentage at max concurrency"
    )

    # Saturation analysis
    saturation_concurrency: int = Field(
        description="Concurrency level where performance starts degrading"
    )
    saturation_goodput: float = Field(description="Goodput at saturation point")


class InfraRecommendation(BaseModel):
    """Infrastructure recommendation result."""

    # Input information
    model_name: str = Field(description="LLM model name")
    workload: WorkloadSpec = Field(description="Workload specification")
    current_infra: InfraProfile = Field(description="Current infrastructure profile")

    # Recommendation
    recommended_gpu: str = Field(description="Recommended GPU model")
    recommended_count: int = Field(description="Recommended GPU count")
    tensor_parallelism: int = Field(default=1, description="Recommended TP setting")

    # Estimated performance
    estimated_max_concurrency: int = Field(
        description="Estimated max concurrency with recommended infra"
    )
    estimated_goodput: float = Field(description="Estimated goodput percentage")
    estimated_throughput: float = Field(description="Estimated throughput (tokens/sec)")

    # Calculation details
    headroom_percent: float = Field(default=20.0, description="Headroom percentage")
    calculation_formula: str = Field(description="Calculation formula explanation")
    reasoning: str = Field(description="Detailed reasoning")

    # Cost estimation (optional)
    estimated_monthly_cost_usd: Optional[float] = Field(
        default=None, description="Estimated monthly cloud cost (USD)"
    )


# ============================================================
# Server Infrastructure Models (for AI Analysis)
# ============================================================


class SystemInfo(BaseModel):
    """System hardware information (CPU, RAM)."""

    cpu_model: str = Field(description="CPU model name")
    cpu_cores_physical: int = Field(description="Physical CPU cores")
    cpu_cores_logical: int = Field(description="Logical CPU cores (with HT)")
    cpu_frequency_mhz: Optional[float] = Field(default=None, description="CPU frequency in MHz")
    numa_nodes: int = Field(default=1, description="Number of NUMA nodes")
    ram_total_gb: float = Field(description="Total RAM in GB")
    ram_available_gb: Optional[float] = Field(default=None, description="Available RAM in GB")


class GPUStaticInfo(BaseModel):
    """Static GPU hardware information (captured at benchmark start)."""

    gpu_count: int = Field(description="Number of GPUs")
    gpu_model: str = Field(description="GPU model name (e.g., NVIDIA H100)")
    gpu_memory_total_gb: float = Field(description="Total VRAM per GPU in GB")
    driver_version: Optional[str] = Field(default=None, description="NVIDIA driver version")
    cuda_version: Optional[str] = Field(default=None, description="CUDA version")
    mig_enabled: Optional[bool] = Field(default=None, description="MIG mode enabled")
    gpu_details: Optional[list[dict]] = Field(
        default=None, description="Per-GPU details for multi-GPU systems"
    )


class ServingEngineInfo(BaseModel):
    """Serving engine configuration (vLLM, TGI, etc.)."""

    engine_type: str = Field(default="unknown", description="Engine type (vLLM/TGI/TensorRT-LLM)")
    engine_version: Optional[str] = Field(default=None, description="Engine version")
    model_name: Optional[str] = Field(default=None, description="Loaded model name")
    quantization: Optional[str] = Field(default=None, description="Quantization method (AWQ/GPTQ/FP16)")
    context_length: Optional[int] = Field(default=None, description="Max context length")
    max_num_seqs: Optional[int] = Field(default=None, description="Max concurrent sequences (vLLM)")
    max_num_batched_tokens: Optional[int] = Field(
        default=None, description="Max batched tokens (vLLM)"
    )
    gpu_memory_utilization: Optional[float] = Field(
        default=None, description="GPU memory utilization setting (vLLM)"
    )
    tensor_parallel_size: Optional[int] = Field(default=None, description="Tensor parallelism size")


class GPUMetricsDuringBenchmark(BaseModel):
    """GPU metrics captured during benchmark execution."""

    gpu_index: int = Field(description="GPU index")
    device_name: Optional[str] = Field(default=None, description="GPU device name")
    avg_memory_used_gb: float = Field(description="Average memory used in GB")
    peak_memory_used_gb: float = Field(description="Peak memory used in GB")
    avg_gpu_util_percent: float = Field(description="Average GPU utilization %")
    peak_gpu_util_percent: float = Field(description="Peak GPU utilization %")
    avg_temperature_celsius: Optional[float] = Field(default=None, description="Average temperature")
    peak_temperature_celsius: Optional[float] = Field(default=None, description="Peak temperature")
    avg_power_draw_watts: Optional[float] = Field(default=None, description="Average power draw")
    peak_power_draw_watts: Optional[float] = Field(default=None, description="Peak power draw")


class ServerInfraInfo(BaseModel):
    """Complete server infrastructure information for AI analysis."""

    system: Optional[SystemInfo] = Field(default=None, description="System hardware info")
    gpu: Optional[GPUStaticInfo] = Field(default=None, description="GPU hardware info")
    serving_engine: Optional[ServingEngineInfo] = Field(
        default=None, description="Serving engine configuration"
    )
    gpu_metrics_during_benchmark: Optional[list[GPUMetricsDuringBenchmark]] = Field(
        default=None, description="GPU metrics captured during benchmark"
    )
    captured_at: Optional[datetime] = Field(default=None, description="Capture timestamp")


# ============================================================
# Validation Models (Phase: Validation Loop)
# ============================================================


class MetricComparison(BaseModel):
    """Individual metric comparison result."""

    metric_name: str = Field(description="Name of the metric being compared")
    client_value: float = Field(description="Value measured by client")
    server_value: float = Field(description="Value from server (Prometheus/Docker)")
    difference_percent: float = Field(description="Difference percentage")
    passed: bool = Field(description="Whether within tolerance")


class DockerLogMetrics(BaseModel):
    """Metrics parsed from Docker container logs."""

    # HTTP request statistics
    http_200_count: int = Field(default=0, description="Successful HTTP 200 responses")
    http_error_count: int = Field(default=0, description="HTTP 4xx/5xx errors")

    # Engine statistics (from vLLM logs)
    avg_prompt_throughput: float = Field(default=0.0, description="Average prompt throughput (tokens/s)")
    avg_generation_throughput: float = Field(
        default=0.0, description="Average generation throughput (tokens/s)"
    )
    peak_kv_cache_usage: float = Field(default=0.0, description="Peak KV cache usage percentage")
    avg_running_reqs: float = Field(default=0.0, description="Average running requests")
    avg_waiting_reqs: float = Field(default=0.0, description="Average waiting requests")
    prefix_cache_hit_rate: float = Field(default=0.0, description="Prefix cache hit rate percentage")

    # Error/warning logs
    error_messages: list[str] = Field(default_factory=list, description="ERROR level log messages")
    warning_messages: list[str] = Field(default_factory=list, description="WARNING level log messages")

    # Metadata
    log_start_time: Optional[datetime] = Field(default=None, description="Log collection start time")
    log_end_time: Optional[datetime] = Field(default=None, description="Log collection end time")
    total_log_lines: int = Field(default=0, description="Total log lines processed")
    container_name: Optional[str] = Field(default=None, description="Docker container name")


class DockerLogValidation(BaseModel):
    """Docker log-based validation result."""

    passed: bool = Field(description="Overall validation passed")
    http_request_match: bool = Field(description="Client requests vs HTTP 200 count matched")
    throughput_match: bool = Field(description="Throughput within tolerance")
    has_errors: bool = Field(description="ERROR logs detected")
    comparisons: list[MetricComparison] = Field(
        default_factory=list, description="Detailed metric comparisons"
    )
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    docker_metrics: Optional[DockerLogMetrics] = Field(
        default=None, description="Raw Docker log metrics"
    )


class PrometheusValidation(BaseModel):
    """Prometheus metrics-based validation result."""

    passed: bool = Field(description="Overall validation passed")
    comparisons: list[MetricComparison] = Field(
        default_factory=list, description="Detailed metric comparisons"
    )
    warnings: list[str] = Field(default_factory=list, description="Warning messages")


class ValidationResult(BaseModel):
    """Combined validation result (Prometheus + Docker logs)."""

    overall_passed: bool = Field(description="Overall validation passed")
    tolerance: float = Field(default=0.05, description="Default tolerance (5%)")

    # Prometheus validation
    prometheus_validation: Optional[PrometheusValidation] = Field(
        default=None, description="Prometheus metrics validation"
    )
    prometheus_available: bool = Field(default=False, description="Prometheus metrics were available")

    # Docker log validation
    docker_log_validation: Optional[DockerLogValidation] = Field(
        default=None, description="Docker log validation"
    )
    docker_available: bool = Field(default=False, description="Docker logs were available")

    # Summary
    all_comparisons: list[MetricComparison] = Field(
        default_factory=list, description="All metric comparisons"
    )
    all_warnings: list[str] = Field(default_factory=list, description="All warning messages")
    validated_at: Optional[datetime] = Field(default=None, description="Validation timestamp")
