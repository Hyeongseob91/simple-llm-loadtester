"""Unit tests for Pydantic data models."""

import pytest
from datetime import datetime

from shared.core.models import (
    BenchmarkConfig,
    BenchmarkResult,
    ConcurrencyResult,
    GoodputResult,
    GoodputThresholds,
    GPUMetrics,
    InfraProfile,
    InfraRecommendation,
    LatencyStats,
    RequestResult,
    WorkloadSpec,
)


class TestLatencyStats:
    """Tests for LatencyStats model."""

    def test_create_latency_stats(self):
        """Test creating LatencyStats with all fields."""
        stats = LatencyStats(
            min=100.0,
            max=500.0,
            mean=300.0,
            median=290.0,
            p50=300.0,
            p95=450.0,
            p99=490.0,
            std=100.0,
        )
        assert stats.min == 100.0
        assert stats.max == 500.0
        assert stats.mean == 300.0
        assert stats.p50 == 300.0
        assert stats.p95 == 450.0
        assert stats.p99 == 490.0

    def test_latency_stats_serialization(self):
        """Test model serialization to dict."""
        stats = LatencyStats(
            min=100.0, max=500.0, mean=300.0, median=300.0,
            p50=300.0, p95=450.0, p99=490.0, std=100.0
        )
        data = stats.model_dump()
        assert "min" in data
        assert "p99" in data


class TestGoodputThresholds:
    """Tests for GoodputThresholds model."""

    def test_empty_thresholds(self):
        """Test creating thresholds with no values."""
        thresholds = GoodputThresholds()
        assert thresholds.ttft_ms is None
        assert thresholds.tpot_ms is None
        assert thresholds.e2e_ms is None

    def test_partial_thresholds(self):
        """Test creating thresholds with partial values."""
        thresholds = GoodputThresholds(ttft_ms=500.0)
        assert thresholds.ttft_ms == 500.0
        assert thresholds.tpot_ms is None

    def test_full_thresholds(self):
        """Test creating thresholds with all values."""
        thresholds = GoodputThresholds(
            ttft_ms=500.0,
            tpot_ms=50.0,
            e2e_ms=3000.0,
        )
        assert thresholds.ttft_ms == 500.0
        assert thresholds.tpot_ms == 50.0
        assert thresholds.e2e_ms == 3000.0


class TestGoodputResult:
    """Tests for GoodputResult model."""

    def test_create_goodput_result(self, sample_goodput_thresholds: GoodputThresholds):
        """Test creating GoodputResult."""
        result = GoodputResult(
            thresholds=sample_goodput_thresholds,
            satisfied_requests=85,
            total_requests=100,
            goodput_percent=85.0,
            ttft_satisfied=90,
            tpot_satisfied=88,
            e2e_satisfied=95,
        )
        assert result.satisfied_requests == 85
        assert result.goodput_percent == 85.0

    def test_goodput_result_zero_requests(self):
        """Test GoodputResult with zero requests."""
        result = GoodputResult(
            thresholds=GoodputThresholds(),
            satisfied_requests=0,
            total_requests=0,
            goodput_percent=0.0,
        )
        assert result.goodput_percent == 0.0


class TestRequestResult:
    """Tests for RequestResult model."""

    def test_successful_request(self):
        """Test creating a successful request result."""
        result = RequestResult(
            request_id=1,
            ttft_ms=150.0,
            tpot_ms=25.0,
            e2e_latency_ms=1500.0,
            input_tokens=256,
            output_tokens=128,
        )
        assert result.success is True
        assert result.error_type is None

    def test_failed_request(self):
        """Test creating a failed request result."""
        result = RequestResult(
            request_id=2,
            ttft_ms=0.0,
            e2e_latency_ms=0.0,
            input_tokens=256,
            output_tokens=0,
            success=False,
            error_type="TIMEOUT",
        )
        assert result.success is False
        assert result.error_type == "TIMEOUT"

    def test_request_with_itl(self):
        """Test request result with inter-token latencies."""
        itl_values = [25.0, 26.0, 24.0, 25.0, 27.0]
        result = RequestResult(
            request_id=3,
            ttft_ms=150.0,
            tpot_ms=25.4,
            e2e_latency_ms=1500.0,
            input_tokens=256,
            output_tokens=128,
            itl_ms=itl_values,
        )
        assert result.itl_ms == itl_values
        assert len(result.itl_ms) == 5


class TestBenchmarkConfig:
    """Tests for BenchmarkConfig model."""

    def test_minimal_config(self):
        """Test creating config with minimal required fields."""
        config = BenchmarkConfig(
            server_url="http://localhost:8000",
            model="test-model",
        )
        assert config.server_url == "http://localhost:8000"
        assert config.model == "test-model"
        assert config.adapter == "openai"  # default
        assert config.num_prompts == 100  # default
        assert config.concurrency == [1]  # default

    def test_full_config(self):
        """Test creating config with all fields."""
        config = BenchmarkConfig(
            server_url="http://localhost:8000",
            model="qwen3-14b",
            adapter="openai",
            input_len=512,
            output_len=256,
            num_prompts=200,
            concurrency=[1, 10, 50, 100],
            stream=True,
            warmup=5,
            timeout=180.0,
            api_key="test-key",
            goodput_thresholds=GoodputThresholds(ttft_ms=500),
        )
        assert config.concurrency == [1, 10, 50, 100]
        assert config.goodput_thresholds.ttft_ms == 500

    def test_duration_mode_config(self):
        """Test config with duration mode."""
        config = BenchmarkConfig(
            server_url="http://localhost:8000",
            model="test-model",
            duration_seconds=60,
        )
        assert config.duration_seconds == 60


class TestConcurrencyResult:
    """Tests for ConcurrencyResult model."""

    def test_create_concurrency_result(self, sample_latency_stats: LatencyStats):
        """Test creating ConcurrencyResult."""
        result = ConcurrencyResult(
            concurrency=10,
            ttft=sample_latency_stats,
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
        )
        assert result.concurrency == 10
        assert result.error_rate_percent == 5.0


class TestBenchmarkResult:
    """Tests for BenchmarkResult model."""

    def test_get_summary(
        self,
        sample_benchmark_config: BenchmarkConfig,
        sample_latency_stats: LatencyStats,
    ):
        """Test get_summary method."""
        results = [
            ConcurrencyResult(
                concurrency=1,
                ttft=LatencyStats(min=50, max=100, mean=75, median=75, p50=75, p95=95, p99=99, std=10),
                e2e_latency=sample_latency_stats,
                throughput_tokens_per_sec=200.0,
                request_rate_per_sec=2.0,
                total_requests=50,
                successful_requests=50,
                failed_requests=0,
                error_rate_percent=0.0,
                total_input_tokens=12800,
                total_output_tokens=6400,
                duration_seconds=25.0,
            ),
            ConcurrencyResult(
                concurrency=10,
                ttft=LatencyStats(min=100, max=200, mean=150, median=150, p50=150, p95=190, p99=198, std=20),
                e2e_latency=sample_latency_stats,
                throughput_tokens_per_sec=800.0,
                request_rate_per_sec=8.0,
                total_requests=100,
                successful_requests=95,
                failed_requests=5,
                error_rate_percent=5.0,
                total_input_tokens=25600,
                total_output_tokens=12800,
                duration_seconds=12.5,
            ),
        ]

        benchmark = BenchmarkResult(
            run_id="test-run-1",
            server_url="http://localhost:8000",
            model="test-model",
            config=sample_benchmark_config,
            results=results,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_seconds=37.5,
        )

        summary = benchmark.get_summary()
        assert summary["best_throughput"] == 800.0
        assert summary["best_ttft_p50"] == 75.0  # p50 from concurrency=1
        assert summary["best_concurrency"] == 10
        assert summary["total_requests"] == 150

    def test_get_summary_empty_results(self, sample_benchmark_config: BenchmarkConfig):
        """Test get_summary with empty results."""
        benchmark = BenchmarkResult(
            run_id="test-run-2",
            server_url="http://localhost:8000",
            model="test-model",
            config=sample_benchmark_config,
            results=[],
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_seconds=0.0,
        )

        summary = benchmark.get_summary()
        assert summary == {}


class TestWorkloadSpec:
    """Tests for WorkloadSpec model."""

    def test_minimal_workload(self):
        """Test creating workload with minimal required fields."""
        workload = WorkloadSpec(peak_concurrency=100)
        assert workload.peak_concurrency == 100
        assert workload.ttft_target_ms == 500.0  # default
        assert workload.goodput_target_percent == 95.0  # default

    def test_full_workload(self):
        """Test creating workload with all fields."""
        workload = WorkloadSpec(
            daily_active_users=10000,
            peak_concurrency=500,
            requests_per_user_per_day=20,
            avg_input_tokens=512,
            avg_output_tokens=1024,
            ttft_target_ms=300.0,
            tpot_target_ms=30.0,
            goodput_target_percent=99.0,
        )
        assert workload.daily_active_users == 10000
        assert workload.peak_concurrency == 500


class TestInfraProfile:
    """Tests for InfraProfile model."""

    def test_create_infra_profile(self):
        """Test creating infrastructure profile."""
        profile = InfraProfile(
            gpu_model="NVIDIA H100",
            gpu_count=1,
            gpu_memory_gb=80.0,
            max_concurrency_at_slo=120,
            throughput_tokens_per_sec=1245.0,
            goodput_at_max_concurrency=95.5,
            saturation_concurrency=150,
            saturation_goodput=88.0,
        )
        assert profile.gpu_model == "NVIDIA H100"
        assert profile.max_concurrency_at_slo == 120


class TestInfraRecommendation:
    """Tests for InfraRecommendation model."""

    def test_create_recommendation(
        self,
        sample_workload_spec: WorkloadSpec,
        sample_infra_profile: InfraProfile,
    ):
        """Test creating infrastructure recommendation."""
        recommendation = InfraRecommendation(
            model_name="qwen3-14b",
            workload=sample_workload_spec,
            current_infra=sample_infra_profile,
            recommended_gpu="NVIDIA H100",
            recommended_count=5,
            tensor_parallelism=1,
            estimated_max_concurrency=600,
            estimated_goodput=97.0,
            estimated_throughput=6225.0,
            headroom_percent=20.0,
            calculation_formula="ceil(500 / 120) * 1.2 = 5",
            reasoning="Based on current GPU performance...",
        )
        assert recommendation.recommended_count == 5
        assert recommendation.headroom_percent == 20.0


class TestGPUMetrics:
    """Tests for GPUMetrics model."""

    def test_create_gpu_metrics(self):
        """Test creating GPU metrics."""
        metrics = GPUMetrics(
            device_name="NVIDIA H100",
            gpu_index=0,
            memory_used_gb=40.0,
            memory_total_gb=80.0,
            memory_util_percent=50.0,
            gpu_util_percent=85.0,
            temperature_celsius=65.0,
            power_draw_watts=450.0,
        )
        assert metrics.device_name == "NVIDIA H100"
        assert metrics.memory_util_percent == 50.0

    def test_gpu_metrics_optional_fields(self):
        """Test GPU metrics with optional fields."""
        metrics = GPUMetrics(
            device_name="NVIDIA A100",
            gpu_index=0,
            memory_used_gb=30.0,
            memory_total_gb=40.0,
            memory_util_percent=75.0,
            gpu_util_percent=90.0,
        )
        assert metrics.temperature_celsius is None
        assert metrics.power_draw_watts is None
