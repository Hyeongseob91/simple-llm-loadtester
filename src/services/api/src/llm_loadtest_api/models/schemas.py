"""API request/response schemas."""

from datetime import datetime
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


# ============================================================
# Framework Types
# ============================================================

FrameworkType = Literal["vllm", "sglang", "ollama", "triton"]


class GoodputThresholdsSchema(BaseModel):
    """Goodput SLO thresholds."""

    ttft_ms: Optional[float] = Field(default=None, description="TTFT threshold (ms)")
    tpot_ms: Optional[float] = Field(default=None, description="TPOT threshold (ms)")
    e2e_ms: Optional[float] = Field(default=None, description="E2E threshold (ms)")


class ValidationConfig(BaseModel):
    """Validation configuration for cross-checking client metrics against server."""

    enabled: bool = Field(default=False, description="Enable validation")
    docker_enabled: bool = Field(
        default=True,
        description="Docker deployment (False = Prometheus only validation)"
    )
    container_name: Optional[str] = Field(
        default=None,
        description="Docker container name (auto-detected if not provided)"
    )
    tolerance: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Tolerance for metric comparison (default 5%)"
    )


class VLLMConfigInput(BaseModel):
    """User-provided vLLM configuration for analysis accuracy.

    These values cannot be auto-detected from vLLM API, so users can
    optionally provide them to improve AI analysis accuracy.
    """

    gpu_memory_utilization: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="GPU memory allocation ratio (0.0~1.0). vLLM default: 0.9"
    )
    tensor_parallel_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of GPUs for tensor parallelism. vLLM default: 1"
    )
    max_num_seqs: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum concurrent sequences. vLLM default: 256"
    )
    quantization: Optional[str] = Field(
        default=None,
        description="Quantization method (e.g., awq, gptq, fp8, None)"
    )


class SGLangConfigInput(BaseModel):
    """User-provided SGLang configuration for analysis accuracy."""

    tensor_parallel_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of GPUs for tensor parallelism. Default: 1"
    )
    chunked_prefill: Optional[bool] = Field(
        default=None,
        description="Enable chunked prefill. Default: true"
    )
    mem_fraction_static: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Static memory fraction. Default: 0.9"
    )


class OllamaConfigInput(BaseModel):
    """User-provided Ollama configuration for analysis accuracy."""

    context_length: Optional[int] = Field(
        default=None,
        ge=1,
        description="Context length. Default: 4096"
    )
    num_gpu: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of GPUs to use. Default: 1"
    )


class TritonConfigInput(BaseModel):
    """User-provided Triton configuration for analysis accuracy."""

    backend: Optional[str] = Field(
        default=None,
        description="Backend type (e.g., tensorrt_llm, vllm). Default: tensorrt_llm"
    )
    instance_count: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of instances. Default: 1"
    )


# Union type for framework configs
FrameworkConfigInput = Union[
    VLLMConfigInput,
    SGLangConfigInput,
    OllamaConfigInput,
    TritonConfigInput
]


class BenchmarkRequest(BaseModel):
    """Request to start a benchmark."""

    server_url: str = Field(description="LLM server URL")
    model: str = Field(description="Model name")
    adapter: str = Field(default="openai", description="Server adapter type")
    concurrency: list[int] = Field(default=[1], description="Concurrency levels")
    num_prompts: int = Field(default=100, description="Number of prompts per level")
    input_len: int = Field(default=256, description="Input token length")
    output_len: int = Field(default=128, description="Output token length")
    stream: bool = Field(default=True, description="Enable streaming")
    warmup: int = Field(default=3, description="Warmup requests")
    timeout: float = Field(default=120.0, description="Request timeout (s)")
    api_key: Optional[str] = Field(default=None, description="API key")
    duration_seconds: Optional[int] = Field(default=None, description="Duration mode")
    goodput_thresholds: Optional[GoodputThresholdsSchema] = Field(
        default=None, description="Goodput SLO thresholds"
    )
    # New framework fields (v1.1)
    framework: Optional[FrameworkType] = Field(
        default="vllm",
        description="Serving framework type (vllm, sglang, ollama, triton)"
    )
    framework_config: Optional[FrameworkConfigInput] = Field(
        default=None,
        description="Framework-specific configuration for improved analysis accuracy"
    )
    # Deprecated: use framework_config instead
    vllm_config: Optional[VLLMConfigInput] = Field(
        default=None,
        description="[Deprecated] Use framework_config instead. vLLM configuration for analysis"
    )
    validation_config: Optional[ValidationConfig] = Field(
        default=None,
        description="Optional validation configuration for cross-checking metrics"
    )


class BenchmarkStatus(BaseModel):
    """Benchmark run status."""

    run_id: str
    status: str  # pending, running, completed, failed
    server_url: str
    model: str
    adapter: str
    framework: Optional[FrameworkType] = Field(
        default="vllm",
        description="Serving framework type"
    )
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class LatencyStatsSchema(BaseModel):
    """Latency statistics."""

    min: float
    max: float
    mean: float
    p50: float
    p95: float
    p99: float


class GoodputResultSchema(BaseModel):
    """Goodput result."""

    satisfied_requests: int
    total_requests: int
    goodput_percent: float


class ConcurrencyResultSchema(BaseModel):
    """Results for a concurrency level."""

    concurrency: int
    ttft: LatencyStatsSchema
    tpot: Optional[LatencyStatsSchema] = None
    e2e_latency: LatencyStatsSchema
    throughput_tokens_per_sec: float
    request_rate_per_sec: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate_percent: float
    goodput: Optional[GoodputResultSchema] = None


class BenchmarkResponse(BaseModel):
    """Benchmark result response."""

    run_id: str
    server_url: str
    model: str
    adapter: str
    framework: Optional[FrameworkType] = Field(
        default="vllm",
        description="Serving framework type"
    )
    framework_config: Optional[dict] = Field(
        default=None,
        description="Framework-specific configuration"
    )
    results: list[ConcurrencyResultSchema]
    summary: dict
    started_at: datetime
    completed_at: datetime
    duration_seconds: float


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    timestamp: datetime


class RunListResponse(BaseModel):
    """List of benchmark runs."""

    runs: list[BenchmarkStatus]
    total: int
    limit: int
    offset: int


class CompareRequest(BaseModel):
    """Request to compare benchmark results."""

    run_ids: list[str] = Field(min_length=2, max_length=5)


class CompareResponse(BaseModel):
    """Comparison result."""

    runs: list[BenchmarkResponse]
    comparison: dict  # Summary comparison metrics


# ============================================================
# Phase 5: Infrastructure Recommendation Schemas
# ============================================================


class WorkloadSpecSchema(BaseModel):
    """Workload specification for recommendation."""

    peak_concurrency: int = Field(description="Peak concurrent users")
    daily_active_users: Optional[int] = Field(default=None, description="DAU")
    requests_per_user_per_day: int = Field(default=10, description="Requests per user")
    avg_input_tokens: int = Field(default=256, description="Average input tokens")
    avg_output_tokens: int = Field(default=512, description="Average output tokens")
    ttft_target_ms: float = Field(default=500.0, description="TTFT target (ms)")
    tpot_target_ms: float = Field(default=50.0, description="TPOT target (ms)")
    goodput_target_percent: float = Field(default=95.0, description="Goodput target (%)")


class TestConfigSchema(BaseModel):
    """Test configuration for recommendation profiling."""

    concurrency_steps: list[int] = Field(
        default=[1, 10, 50, 100, 200], description="Concurrency levels to test"
    )
    num_requests_per_step: int = Field(default=50, description="Requests per level")


class RecommendRequest(BaseModel):
    """Request to start infrastructure recommendation."""

    server_url: str = Field(description="LLM server URL")
    model: str = Field(description="Model name")
    adapter: str = Field(default="openai", description="Server adapter type")
    workload: WorkloadSpecSchema = Field(description="Target workload specification")
    headroom_percent: float = Field(default=20.0, description="Safety headroom (%)")
    test_config: Optional[TestConfigSchema] = Field(
        default=None, description="Test configuration"
    )
    stream: bool = Field(default=True, description="Enable streaming")
    warmup: int = Field(default=3, description="Warmup requests")
    timeout: float = Field(default=120.0, description="Request timeout (s)")
    api_key: Optional[str] = Field(default=None, description="API key")


class InfraProfileSchema(BaseModel):
    """Current infrastructure profile."""

    gpu_model: str
    gpu_count: int
    gpu_memory_gb: float
    max_concurrency_at_slo: int
    throughput_tokens_per_sec: float
    goodput_at_max_concurrency: float
    saturation_concurrency: int
    saturation_goodput: float


class InfraRecommendationSchema(BaseModel):
    """Infrastructure recommendation result."""

    model_name: str
    recommended_gpu: str
    recommended_count: int
    tensor_parallelism: int
    estimated_max_concurrency: int
    estimated_goodput: float
    estimated_throughput: float
    headroom_percent: float
    calculation_formula: str
    reasoning: str
    estimated_monthly_cost_usd: Optional[float] = None


class RecommendResponse(BaseModel):
    """Recommendation result response."""

    run_id: str
    recommendation: InfraRecommendationSchema
    current_infra: InfraProfileSchema
    workload: WorkloadSpecSchema
    test_results: list[ConcurrencyResultSchema]
    started_at: datetime
    completed_at: datetime
    duration_seconds: float


class RecommendStatus(BaseModel):
    """Recommendation run status."""

    run_id: str
    status: str  # pending, running, completed, failed
    server_url: str
    model: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
