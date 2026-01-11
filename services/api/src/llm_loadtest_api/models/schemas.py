"""API request/response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GoodputThresholdsSchema(BaseModel):
    """Goodput SLO thresholds."""

    ttft_ms: Optional[float] = Field(default=None, description="TTFT threshold (ms)")
    tpot_ms: Optional[float] = Field(default=None, description="TPOT threshold (ms)")
    e2e_ms: Optional[float] = Field(default=None, description="E2E threshold (ms)")


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


class BenchmarkStatus(BaseModel):
    """Benchmark run status."""

    run_id: str
    status: str  # pending, running, completed, failed
    server_url: str
    model: str
    adapter: str
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
