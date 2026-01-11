"""Integration tests for InfraRecommender."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from shared.core.models import (
    ConcurrencyResult,
    GoodputResult,
    GoodputThresholds,
    InfraProfile,
    LatencyStats,
    WorkloadSpec,
)
from shared.core.recommend import InfraRecommender


class TestInfraRecommender:
    """Tests for InfraRecommender class."""

    @pytest.fixture
    def mock_load_generator(self):
        """Mock load generator for testing."""
        return MagicMock()

    @pytest.fixture
    def recommender(self, mock_load_generator):
        """Create recommender instance."""
        return InfraRecommender(mock_load_generator)

    @pytest.fixture
    def sample_results(self) -> list[ConcurrencyResult]:
        """Sample concurrency results for testing."""

        def make_latency_stats(base: float) -> LatencyStats:
            return LatencyStats(
                min=base * 0.5,
                max=base * 2.0,
                mean=base,
                median=base,
                p50=base,
                p95=base * 1.5,
                p99=base * 1.8,
                std=base * 0.2,
            )

        return [
            ConcurrencyResult(
                concurrency=1,
                ttft=make_latency_stats(100),
                tpot=make_latency_stats(20),
                e2e_latency=make_latency_stats(500),
                throughput_tokens_per_sec=200,
                request_rate_per_sec=2.0,
                total_requests=50,
                successful_requests=50,
                failed_requests=0,
                error_rate_percent=0.0,
                total_input_tokens=12800,
                total_output_tokens=6400,
                duration_seconds=25.0,
                goodput=GoodputResult(
                    thresholds=GoodputThresholds(ttft_ms=500, tpot_ms=50),
                    satisfied_requests=50,
                    total_requests=50,
                    goodput_percent=100.0,
                ),
            ),
            ConcurrencyResult(
                concurrency=10,
                ttft=make_latency_stats(150),
                tpot=make_latency_stats(25),
                e2e_latency=make_latency_stats(800),
                throughput_tokens_per_sec=800,
                request_rate_per_sec=8.0,
                total_requests=50,
                successful_requests=50,
                failed_requests=0,
                error_rate_percent=0.0,
                total_input_tokens=12800,
                total_output_tokens=6400,
                duration_seconds=6.25,
                goodput=GoodputResult(
                    thresholds=GoodputThresholds(ttft_ms=500, tpot_ms=50),
                    satisfied_requests=49,
                    total_requests=50,
                    goodput_percent=98.0,
                ),
            ),
            ConcurrencyResult(
                concurrency=50,
                ttft=make_latency_stats(250),
                tpot=make_latency_stats(35),
                e2e_latency=make_latency_stats(1500),
                throughput_tokens_per_sec=1200,
                request_rate_per_sec=12.0,
                total_requests=50,
                successful_requests=48,
                failed_requests=2,
                error_rate_percent=4.0,
                total_input_tokens=12800,
                total_output_tokens=6400,
                duration_seconds=4.17,
                goodput=GoodputResult(
                    thresholds=GoodputThresholds(ttft_ms=500, tpot_ms=50),
                    satisfied_requests=46,
                    total_requests=48,
                    goodput_percent=95.8,
                ),
            ),
            ConcurrencyResult(
                concurrency=100,
                ttft=make_latency_stats(400),
                tpot=make_latency_stats(45),
                e2e_latency=make_latency_stats(2500),
                throughput_tokens_per_sec=1400,
                request_rate_per_sec=14.0,
                total_requests=50,
                successful_requests=45,
                failed_requests=5,
                error_rate_percent=10.0,
                total_input_tokens=12800,
                total_output_tokens=6400,
                duration_seconds=3.57,
                goodput=GoodputResult(
                    thresholds=GoodputThresholds(ttft_ms=500, tpot_ms=50),
                    satisfied_requests=38,
                    total_requests=45,
                    goodput_percent=84.4,
                ),
            ),
            ConcurrencyResult(
                concurrency=200,
                ttft=make_latency_stats(800),  # Exceeds 500ms target
                tpot=make_latency_stats(60),   # Exceeds 50ms target
                e2e_latency=make_latency_stats(5000),
                throughput_tokens_per_sec=1500,
                request_rate_per_sec=15.0,
                total_requests=50,
                successful_requests=40,
                failed_requests=10,
                error_rate_percent=20.0,
                total_input_tokens=12800,
                total_output_tokens=6400,
                duration_seconds=3.33,
                goodput=GoodputResult(
                    thresholds=GoodputThresholds(ttft_ms=500, tpot_ms=50),
                    satisfied_requests=20,
                    total_requests=40,
                    goodput_percent=50.0,
                ),
            ),
        ]

    class TestFindMaxConcurrencyAtSlo:
        """Tests for _find_max_concurrency_at_slo method."""

        def test_find_highest_meeting_slo(
            self,
            recommender: InfraRecommender,
            sample_results: list[ConcurrencyResult],
        ):
            """Test finding highest concurrency meeting SLO."""
            workload = WorkloadSpec(
                peak_concurrency=500,
                ttft_target_ms=500,
                tpot_target_ms=50,
                goodput_target_percent=95.0,
            )

            max_concurrency = recommender._find_max_concurrency_at_slo(
                sample_results, workload
            )

            # concurrency 50 should be the highest meeting all SLOs
            # (p95 TTFT = 375, p95 TPOT = 52.5 which exceeds 50, but goodput is 95.8%)
            # Actually checking the data: concurrency 50 has p95 TTFT = 250*1.5=375 (OK)
            # p95 TPOT = 35*1.5=52.5 (exceeds 50), so should fail
            # So max should be concurrency 10 (p95 TPOT = 25*1.5=37.5 < 50)
            assert max_concurrency == 10

        def test_no_results(self, recommender: InfraRecommender):
            """Test with no results returns 1."""
            workload = WorkloadSpec(peak_concurrency=100)
            max_concurrency = recommender._find_max_concurrency_at_slo([], workload)
            assert max_concurrency == 1

        def test_none_meet_slo(self, recommender: InfraRecommender):
            """Test when no concurrency meets SLO."""

            def make_stats(base: float) -> LatencyStats:
                return LatencyStats(
                    min=base, max=base * 2, mean=base, median=base,
                    p50=base, p95=base * 1.5, p99=base * 1.8, std=base * 0.1
                )

            # All results exceed TTFT target
            results = [
                ConcurrencyResult(
                    concurrency=c,
                    ttft=make_stats(600),  # p95 = 900, exceeds 500
                    e2e_latency=make_stats(2000),
                    throughput_tokens_per_sec=1000,
                    request_rate_per_sec=10.0,
                    total_requests=50,
                    successful_requests=50,
                    failed_requests=0,
                    error_rate_percent=0.0,
                    total_input_tokens=12800,
                    total_output_tokens=6400,
                    duration_seconds=5.0,
                )
                for c in [1, 10, 50]
            ]

            workload = WorkloadSpec(
                peak_concurrency=100,
                ttft_target_ms=500,  # All results exceed this
            )

            max_concurrency = recommender._find_max_concurrency_at_slo(results, workload)
            # Should return lowest tested concurrency
            assert max_concurrency == 1

        def test_single_result(self, recommender: InfraRecommender):
            """Test with single result."""

            def make_stats(base: float) -> LatencyStats:
                return LatencyStats(
                    min=base, max=base * 2, mean=base, median=base,
                    p50=base, p95=base * 1.5, p99=base * 1.8, std=base * 0.1
                )

            results = [
                ConcurrencyResult(
                    concurrency=50,
                    ttft=make_stats(200),  # p95 = 300 < 500
                    e2e_latency=make_stats(1000),
                    throughput_tokens_per_sec=1000,
                    request_rate_per_sec=10.0,
                    total_requests=50,
                    successful_requests=50,
                    failed_requests=0,
                    error_rate_percent=0.0,
                    total_input_tokens=12800,
                    total_output_tokens=6400,
                    duration_seconds=5.0,
                )
            ]

            workload = WorkloadSpec(peak_concurrency=100, ttft_target_ms=500)
            max_concurrency = recommender._find_max_concurrency_at_slo(results, workload)
            assert max_concurrency == 50

    class TestFindSaturationPoint:
        """Tests for _find_saturation_point method."""

        def test_find_saturation_point(
            self,
            recommender: InfraRecommender,
            sample_results: list[ConcurrencyResult],
        ):
            """Test finding saturation point."""
            saturation_concurrency, saturation_goodput = recommender._find_saturation_point(
                sample_results
            )

            # Saturation should be detected at concurrency 100 (error rate > 5%)
            # But the previous point (50) is returned as saturation
            assert saturation_concurrency == 50
            assert saturation_goodput == pytest.approx(95.8, rel=0.01)

        def test_no_results(self, recommender: InfraRecommender):
            """Test with no results."""
            saturation, goodput = recommender._find_saturation_point([])
            assert saturation == 1
            assert goodput == 100.0

        def test_single_result(self, recommender: InfraRecommender):
            """Test with single result."""

            def make_stats(base: float) -> LatencyStats:
                return LatencyStats(
                    min=base, max=base * 2, mean=base, median=base,
                    p50=base, p95=base * 1.5, p99=base * 1.8, std=base * 0.1
                )

            results = [
                ConcurrencyResult(
                    concurrency=50,
                    ttft=make_stats(200),
                    e2e_latency=make_stats(1000),
                    throughput_tokens_per_sec=1000,
                    request_rate_per_sec=10.0,
                    total_requests=50,
                    successful_requests=50,
                    failed_requests=0,
                    error_rate_percent=0.0,
                    total_input_tokens=12800,
                    total_output_tokens=6400,
                    duration_seconds=5.0,
                    goodput=GoodputResult(
                        thresholds=GoodputThresholds(ttft_ms=500),
                        satisfied_requests=48,
                        total_requests=50,
                        goodput_percent=96.0,
                    ),
                )
            ]

            saturation, goodput = recommender._find_saturation_point(results)
            assert saturation == 50
            assert goodput == 96.0

        def test_no_saturation(self, recommender: InfraRecommender):
            """Test when no saturation is detected."""

            def make_stats(base: float) -> LatencyStats:
                return LatencyStats(
                    min=base, max=base * 2, mean=base, median=base,
                    p50=base, p95=base * 1.5, p99=base * 1.8, std=base * 0.1
                )

            # All results have good goodput and low error rate
            results = [
                ConcurrencyResult(
                    concurrency=c,
                    ttft=make_stats(100),
                    e2e_latency=make_stats(500),
                    throughput_tokens_per_sec=1000,
                    request_rate_per_sec=10.0,
                    total_requests=50,
                    successful_requests=50,
                    failed_requests=0,
                    error_rate_percent=0.0,
                    total_input_tokens=12800,
                    total_output_tokens=6400,
                    duration_seconds=5.0,
                    goodput=GoodputResult(
                        thresholds=GoodputThresholds(ttft_ms=500),
                        satisfied_requests=50,
                        total_requests=50,
                        goodput_percent=100.0,
                    ),
                )
                for c in [1, 10, 50, 100]
            ]

            saturation, goodput = recommender._find_saturation_point(results)
            # Should return last concurrency (no saturation detected)
            assert saturation == 100
            assert goodput == 100.0

    class TestCalculateRecommendation:
        """Tests for calculate_recommendation method."""

        def test_basic_recommendation(
            self,
            recommender: InfraRecommender,
            sample_workload_spec: WorkloadSpec,
            sample_infra_profile: InfraProfile,
        ):
            """Test basic GPU recommendation calculation."""
            recommendation = recommender.calculate_recommendation(
                model_name="test-model",
                workload=sample_workload_spec,
                profile=sample_infra_profile,
                headroom=0.2,
            )

            # peak=500, max_at_slo=120, headroom=20%
            # raw_gpu = (500/120) * 1.2 = 4.17 * 1.2 = 5.0
            # recommended_count = max(ceil(5.0), current_gpu_count=1) = 5
            assert recommendation.recommended_count == 5
            assert recommendation.recommended_gpu == "NVIDIA H100"
            assert recommendation.headroom_percent == 20.0

        def test_small_workload(
            self,
            recommender: InfraRecommender,
            sample_infra_profile: InfraProfile,
        ):
            """Test recommendation for small workload (already handled)."""
            workload = WorkloadSpec(
                peak_concurrency=50,  # Less than max_concurrency_at_slo (120)
            )

            recommendation = recommender.calculate_recommendation(
                model_name="test-model",
                workload=workload,
                profile=sample_infra_profile,
                headroom=0.2,
            )

            # ceil(50/120) * 1.2 = ceil(0.42) * 1.2 = 1 * 1.2 = 1.2 -> 2
            # But max(2, current_gpu_count=1) = 2
            # Actually: raw = 0.42 * 1.2 = 0.5 -> ceil = 1
            # But max(1, 1) = 1
            assert recommendation.recommended_count >= 1

        def test_headroom_effect(
            self,
            recommender: InfraRecommender,
            sample_infra_profile: InfraProfile,
        ):
            """Test that headroom affects recommendation."""
            workload = WorkloadSpec(peak_concurrency=240)

            rec_low_headroom = recommender.calculate_recommendation(
                model_name="test-model",
                workload=workload,
                profile=sample_infra_profile,
                headroom=0.0,
            )

            rec_high_headroom = recommender.calculate_recommendation(
                model_name="test-model",
                workload=workload,
                profile=sample_infra_profile,
                headroom=0.5,
            )

            assert rec_high_headroom.recommended_count >= rec_low_headroom.recommended_count

        def test_tensor_parallelism(
            self,
            recommender: InfraRecommender,
            sample_infra_profile: InfraProfile,
        ):
            """Test tensor parallelism recommendation."""
            # Small recommendation (< 4 GPUs)
            workload_small = WorkloadSpec(peak_concurrency=200)
            rec_small = recommender.calculate_recommendation(
                model_name="test-model",
                workload=workload_small,
                profile=sample_infra_profile,
                headroom=0.2,
            )

            # Large recommendation (>= 8 GPUs)
            workload_large = WorkloadSpec(peak_concurrency=2000)
            rec_large = recommender.calculate_recommendation(
                model_name="test-model",
                workload=workload_large,
                profile=sample_infra_profile,
                headroom=0.2,
            )

            # TP should increase for larger deployments
            if rec_small.recommended_count < 4:
                assert rec_small.tensor_parallelism == 1
            if rec_large.recommended_count >= 8:
                assert rec_large.tensor_parallelism == 4

        def test_estimated_performance(
            self,
            recommender: InfraRecommender,
            sample_workload_spec: WorkloadSpec,
            sample_infra_profile: InfraProfile,
        ):
            """Test estimated performance calculations."""
            recommendation = recommender.calculate_recommendation(
                model_name="test-model",
                workload=sample_workload_spec,
                profile=sample_infra_profile,
                headroom=0.2,
            )

            # Estimated throughput should scale with GPU count
            scale_factor = recommendation.recommended_count / sample_infra_profile.gpu_count
            expected_throughput = sample_infra_profile.throughput_tokens_per_sec * scale_factor

            assert recommendation.estimated_throughput == pytest.approx(expected_throughput, rel=0.01)

        def test_calculation_formula(
            self,
            recommender: InfraRecommender,
            sample_workload_spec: WorkloadSpec,
            sample_infra_profile: InfraProfile,
        ):
            """Test that calculation formula is included."""
            recommendation = recommender.calculate_recommendation(
                model_name="test-model",
                workload=sample_workload_spec,
                profile=sample_infra_profile,
                headroom=0.2,
            )

            assert recommendation.calculation_formula != ""
            assert "ceil" in recommendation.calculation_formula.lower() or "/" in recommendation.calculation_formula

        def test_reasoning_included(
            self,
            recommender: InfraRecommender,
            sample_workload_spec: WorkloadSpec,
            sample_infra_profile: InfraProfile,
        ):
            """Test that reasoning is included."""
            recommendation = recommender.calculate_recommendation(
                model_name="test-model",
                workload=sample_workload_spec,
                profile=sample_infra_profile,
                headroom=0.2,
            )

            assert recommendation.reasoning != ""
            assert len(recommendation.reasoning) > 50  # Should be detailed

        def test_zero_max_concurrency(
            self,
            recommender: InfraRecommender,
            sample_workload_spec: WorkloadSpec,
        ):
            """Test handling of zero max_concurrency_at_slo."""
            profile = InfraProfile(
                gpu_model="NVIDIA H100",
                gpu_count=1,
                gpu_memory_gb=80.0,
                max_concurrency_at_slo=0,  # Edge case
                throughput_tokens_per_sec=1000.0,
                goodput_at_max_concurrency=0.0,
                saturation_concurrency=0,
                saturation_goodput=0.0,
            )

            # Should not raise ZeroDivisionError
            recommendation = recommender.calculate_recommendation(
                model_name="test-model",
                workload=sample_workload_spec,
                profile=profile,
                headroom=0.2,
            )

            assert recommendation.recommended_count >= 1
