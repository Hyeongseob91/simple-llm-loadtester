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
