"""Common test fixtures for LLM Loadtest tests."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shared.core.models import (
    BenchmarkConfig,
    BenchmarkResult,
    ConcurrencyResult,
    GoodputResult,
    GoodputThresholds,
    InfraProfile,
    InfraRecommendation,
    LatencyStats,
    RequestResult,
    WorkloadSpec,
)


# ============================================================
# Sample Data Fixtures
# ============================================================


@pytest.fixture
def sample_latency_values() -> list[float]:
    """Sample latency values for testing."""
    return [100.0, 150.0, 200.0, 250.0, 300.0, 350.0, 400.0, 450.0, 500.0, 1000.0]


@pytest.fixture
def sample_latency_stats() -> LatencyStats:
    """Sample latency statistics."""
    return LatencyStats(
        min=100.0,
        max=500.0,
        mean=300.0,
        median=300.0,
        p50=300.0,
        p95=480.0,
        p99=496.0,
        std=141.42,
    )


@pytest.fixture
def sample_goodput_thresholds() -> GoodputThresholds:
    """Sample Goodput thresholds."""
    return GoodputThresholds(
        ttft_ms=500.0,
        tpot_ms=50.0,
        e2e_ms=3000.0,
    )


@pytest.fixture
def sample_request_result() -> RequestResult:
    """Sample single request result."""
    return RequestResult(
        request_id=1,
        ttft_ms=150.0,
        tpot_ms=25.0,
        e2e_latency_ms=1500.0,
        input_tokens=256,
        output_tokens=128,
        success=True,
        error_type=None,
        itl_ms=[25.0, 26.0, 24.0, 25.0, 27.0],
    )


@pytest.fixture
def sample_request_results() -> list[RequestResult]:
    """Sample list of request results for metrics testing."""
    results = []
    for i in range(100):
        # 80% meet all SLOs, 20% exceed one or more
        ttft = 200.0 + (i % 10) * 30  # 200-470ms
        tpot = 20.0 + (i % 5) * 8  # 20-52ms (some exceed 50)
        e2e = 1000.0 + (i % 20) * 100  # 1000-2900ms

        results.append(RequestResult(
            request_id=i,
            ttft_ms=ttft,
            tpot_ms=tpot,
            e2e_latency_ms=e2e,
            input_tokens=256,
            output_tokens=128,
            success=True if i < 95 else False,  # 5% failures
            error_type=None if i < 95 else "TIMEOUT",
        ))
    return results


@pytest.fixture
def sample_benchmark_config() -> BenchmarkConfig:
    """Sample benchmark configuration."""
    return BenchmarkConfig(
        server_url="http://localhost:8000",
        model="test-model",
        adapter="openai",
        input_len=256,
        output_len=128,
        num_prompts=100,
        concurrency=[1, 10, 50],
        stream=True,
        warmup=3,
        timeout=120.0,
    )


@pytest.fixture
def sample_concurrency_result(sample_latency_stats: LatencyStats) -> ConcurrencyResult:
    """Sample concurrency result."""
    return ConcurrencyResult(
        concurrency=10,
        ttft=sample_latency_stats,
        tpot=sample_latency_stats,
        e2e_latency=sample_latency_stats,
        throughput_tokens_per_sec=500.0,
        request_rate_per_sec=5.0,
        total_requests=100,
        successful_requests=95,
        failed_requests=5,
        error_rate_percent=5.0,
        total_input_tokens=25600,
        total_output_tokens=12800,
        duration_seconds=20.0,
        goodput=GoodputResult(
            thresholds=GoodputThresholds(ttft_ms=500),
            satisfied_requests=90,
            total_requests=95,
            goodput_percent=94.7,
        ),
    )


@pytest.fixture
def sample_workload_spec() -> WorkloadSpec:
    """Sample workload specification for infrastructure recommendation."""
    return WorkloadSpec(
        peak_concurrency=500,
        daily_active_users=10000,
        requests_per_user_per_day=10,
        avg_input_tokens=256,
        avg_output_tokens=512,
        ttft_target_ms=500.0,
        tpot_target_ms=50.0,
        goodput_target_percent=95.0,
    )


@pytest.fixture
def sample_infra_profile() -> InfraProfile:
    """Sample infrastructure profile."""
    return InfraProfile(
        gpu_model="NVIDIA H100",
        gpu_count=1,
        gpu_memory_gb=80.0,
        max_concurrency_at_slo=120,
        throughput_tokens_per_sec=1245.0,
        goodput_at_max_concurrency=95.5,
        saturation_concurrency=150,
        saturation_goodput=88.0,
    )


# ============================================================
# Mock Classes
# ============================================================


class MockServerAdapter:
    """Mock server adapter for testing without a real server."""

    def __init__(
        self,
        base_ttft: float = 150.0,
        base_tpot: float = 25.0,
        failure_rate: float = 0.0,
    ):
        self.base_ttft = base_ttft
        self.base_tpot = base_tpot
        self.failure_rate = failure_rate
        self.request_count = 0

    async def send_request(
        self,
        request_id: int,
        prompt: str,
        max_tokens: int,
        stream: bool = True,
    ) -> RequestResult:
        """Simulate a request to the server."""
        import random

        self.request_count += 1

        # Simulate failure
        if random.random() < self.failure_rate:
            return RequestResult(
                request_id=request_id,
                ttft_ms=0,
                tpot_ms=None,
                e2e_latency_ms=0,
                input_tokens=len(prompt.split()),
                output_tokens=0,
                success=False,
                error_type="TIMEOUT",
            )

        # Simulate variable latency
        ttft = self.base_ttft + random.uniform(-50, 100)
        tpot = self.base_tpot + random.uniform(-5, 15)
        output_tokens = max_tokens
        e2e = ttft + tpot * (output_tokens - 1)

        return RequestResult(
            request_id=request_id,
            ttft_ms=ttft,
            tpot_ms=tpot,
            e2e_latency_ms=e2e,
            input_tokens=len(prompt.split()),
            output_tokens=output_tokens,
            success=True,
        )

    async def health_check(self) -> bool:
        """Simulate health check."""
        return True

    async def warmup(self, num_requests: int, input_len: int, output_len: int) -> None:
        """Simulate warmup."""
        pass


@pytest.fixture
def mock_adapter() -> MockServerAdapter:
    """Mock server adapter fixture."""
    return MockServerAdapter()


@pytest.fixture
def mock_adapter_with_failures() -> MockServerAdapter:
    """Mock server adapter with 10% failure rate."""
    return MockServerAdapter(failure_rate=0.1)
