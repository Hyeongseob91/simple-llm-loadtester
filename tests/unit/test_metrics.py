"""Unit tests for metrics calculation utilities."""

import pytest

from shared.core.metrics import GoodputCalculator, MetricsCalculator
from shared.core.models import GoodputThresholds, RequestResult


class TestMetricsCalculator:
    """Tests for MetricsCalculator class."""

    class TestCalculateLatencyStats:
        """Tests for calculate_latency_stats method."""

        def test_basic_stats(self, sample_latency_values: list[float]):
            """Test basic latency statistics calculation."""
            stats = MetricsCalculator.calculate_latency_stats(sample_latency_values)

            assert stats.min == 100.0
            assert stats.max == 1000.0
            assert stats.mean == pytest.approx(370.0, rel=0.01)
            assert stats.median == pytest.approx(325.0, rel=0.01)

        def test_percentiles(self, sample_latency_values: list[float]):
            """Test percentile calculations."""
            stats = MetricsCalculator.calculate_latency_stats(sample_latency_values)

            # p50 should be close to median
            assert stats.p50 == pytest.approx(stats.median, rel=0.01)
            # p95 and p99 should be high values
            assert stats.p95 > stats.p50
            assert stats.p99 >= stats.p95

        def test_standard_deviation(self):
            """Test standard deviation calculation."""
            # Uniform values should have 0 std
            uniform_values = [100.0, 100.0, 100.0, 100.0, 100.0]
            stats = MetricsCalculator.calculate_latency_stats(uniform_values)
            assert stats.std == 0.0

            # Variable values should have non-zero std
            variable_values = [100.0, 200.0, 300.0, 400.0, 500.0]
            stats = MetricsCalculator.calculate_latency_stats(variable_values)
            assert stats.std > 0

        def test_empty_values(self):
            """Test with empty values list."""
            stats = MetricsCalculator.calculate_latency_stats([])
            assert stats.min == 0.0
            assert stats.max == 0.0
            assert stats.mean == 0.0
            assert stats.p50 == 0.0

        def test_single_value(self):
            """Test with single value."""
            stats = MetricsCalculator.calculate_latency_stats([250.0])
            assert stats.min == 250.0
            assert stats.max == 250.0
            assert stats.mean == 250.0
            assert stats.p50 == 250.0
            assert stats.std == 0.0

    class TestCalculateThroughput:
        """Tests for calculate_throughput method."""

        def test_basic_throughput(self):
            """Test basic throughput calculation."""
            throughput = MetricsCalculator.calculate_throughput(1000, 10.0)
            assert throughput == 100.0

        def test_zero_duration(self):
            """Test throughput with zero duration."""
            throughput = MetricsCalculator.calculate_throughput(1000, 0.0)
            assert throughput == 0.0

        def test_negative_duration(self):
            """Test throughput with negative duration."""
            throughput = MetricsCalculator.calculate_throughput(1000, -5.0)
            assert throughput == 0.0

        def test_zero_tokens(self):
            """Test throughput with zero tokens."""
            throughput = MetricsCalculator.calculate_throughput(0, 10.0)
            assert throughput == 0.0

        def test_high_throughput(self):
            """Test high throughput calculation."""
            # 10000 tokens in 1 second = 10000 tok/s
            throughput = MetricsCalculator.calculate_throughput(10000, 1.0)
            assert throughput == 10000.0

    class TestCalculateRequestRate:
        """Tests for calculate_request_rate method."""

        def test_basic_request_rate(self):
            """Test basic request rate calculation."""
            rate = MetricsCalculator.calculate_request_rate(100, 10.0)
            assert rate == 10.0

        def test_zero_duration(self):
            """Test request rate with zero duration."""
            rate = MetricsCalculator.calculate_request_rate(100, 0.0)
            assert rate == 0.0

        def test_fractional_rate(self):
            """Test fractional request rate."""
            rate = MetricsCalculator.calculate_request_rate(5, 10.0)
            assert rate == 0.5

    class TestAggregateResults:
        """Tests for aggregate_results method."""

        def test_aggregate_successful_results(self, sample_request_results: list[RequestResult]):
            """Test aggregating results with all successful requests."""
            # Filter only successful results for this test
            successful_results = [r for r in sample_request_results if r.success]

            result = MetricsCalculator.aggregate_results(
                results=successful_results,
                duration_seconds=10.0,
                concurrency=10,
            )

            assert result.concurrency == 10
            assert result.total_requests == len(successful_results)
            assert result.successful_requests == len(successful_results)
            assert result.failed_requests == 0
            assert result.error_rate_percent == 0.0
            assert result.throughput_tokens_per_sec > 0
            assert result.ttft.min > 0

        def test_aggregate_with_failures(self, sample_request_results: list[RequestResult]):
            """Test aggregating results with some failures."""
            result = MetricsCalculator.aggregate_results(
                results=sample_request_results,
                duration_seconds=10.0,
                concurrency=10,
            )

            assert result.total_requests == 100
            assert result.failed_requests == 5  # 5% failure rate in fixture
            assert result.error_rate_percent == pytest.approx(5.0, rel=0.01)

        def test_aggregate_with_goodput(
            self,
            sample_request_results: list[RequestResult],
            sample_goodput_thresholds: GoodputThresholds,
        ):
            """Test aggregating results with Goodput calculation."""
            result = MetricsCalculator.aggregate_results(
                results=sample_request_results,
                duration_seconds=10.0,
                concurrency=10,
                goodput_thresholds=sample_goodput_thresholds,
            )

            assert result.goodput is not None
            assert result.goodput.total_requests > 0
            assert 0 <= result.goodput.goodput_percent <= 100

        def test_aggregate_empty_results(self):
            """Test aggregating empty results."""
            result = MetricsCalculator.aggregate_results(
                results=[],
                duration_seconds=10.0,
                concurrency=10,
            )

            assert result.total_requests == 0
            assert result.successful_requests == 0
            assert result.throughput_tokens_per_sec == 0.0


class TestGoodputCalculator:
    """Tests for GoodputCalculator class."""

    def test_all_requests_meet_slo(self):
        """Test when all requests meet SLO."""
        results = [
            RequestResult(
                request_id=i,
                ttft_ms=100.0,  # Under 500 threshold
                tpot_ms=30.0,  # Under 50 threshold
                e2e_latency_ms=1000.0,  # Under 3000 threshold
                input_tokens=256,
                output_tokens=128,
            )
            for i in range(10)
        ]

        thresholds = GoodputThresholds(ttft_ms=500.0, tpot_ms=50.0, e2e_ms=3000.0)
        goodput = GoodputCalculator.calculate(results, thresholds)

        assert goodput.satisfied_requests == 10
        assert goodput.total_requests == 10
        assert goodput.goodput_percent == 100.0

    def test_no_requests_meet_slo(self):
        """Test when no requests meet SLO."""
        results = [
            RequestResult(
                request_id=i,
                ttft_ms=1000.0,  # Over 500 threshold
                tpot_ms=100.0,  # Over 50 threshold
                e2e_latency_ms=5000.0,  # Over 3000 threshold
                input_tokens=256,
                output_tokens=128,
            )
            for i in range(10)
        ]

        thresholds = GoodputThresholds(ttft_ms=500.0, tpot_ms=50.0, e2e_ms=3000.0)
        goodput = GoodputCalculator.calculate(results, thresholds)

        assert goodput.satisfied_requests == 0
        assert goodput.goodput_percent == 0.0

    def test_partial_slo_compliance(self):
        """Test when some requests meet SLO."""
        results = []
        for i in range(10):
            # First 7 meet all SLOs, last 3 exceed TTFT
            ttft = 200.0 if i < 7 else 600.0
            results.append(RequestResult(
                request_id=i,
                ttft_ms=ttft,
                tpot_ms=30.0,
                e2e_latency_ms=1000.0,
                input_tokens=256,
                output_tokens=128,
            ))

        thresholds = GoodputThresholds(ttft_ms=500.0)
        goodput = GoodputCalculator.calculate(results, thresholds)

        assert goodput.satisfied_requests == 7
        assert goodput.goodput_percent == 70.0
        assert goodput.ttft_satisfied == 7

    def test_ttft_only_threshold(self):
        """Test with only TTFT threshold."""
        results = [
            RequestResult(
                request_id=0,
                ttft_ms=300.0,  # Under threshold
                tpot_ms=100.0,  # Would exceed if checked
                e2e_latency_ms=5000.0,  # Would exceed if checked
                input_tokens=256,
                output_tokens=128,
            )
        ]

        thresholds = GoodputThresholds(ttft_ms=500.0)  # Only TTFT
        goodput = GoodputCalculator.calculate(results, thresholds)

        assert goodput.satisfied_requests == 1
        assert goodput.goodput_percent == 100.0

    def test_tpot_threshold_with_none_values(self):
        """Test TPOT threshold when some results have None TPOT."""
        results = [
            RequestResult(
                request_id=0,
                ttft_ms=200.0,
                tpot_ms=30.0,  # Has TPOT, meets SLO
                e2e_latency_ms=1000.0,
                input_tokens=256,
                output_tokens=128,
            ),
            RequestResult(
                request_id=1,
                ttft_ms=200.0,
                tpot_ms=None,  # No TPOT (non-streaming?)
                e2e_latency_ms=1000.0,
                input_tokens=256,
                output_tokens=128,
            ),
        ]

        thresholds = GoodputThresholds(tpot_ms=50.0)
        goodput = GoodputCalculator.calculate(results, thresholds)

        # Request with None TPOT should fail TPOT check
        assert goodput.satisfied_requests == 1
        assert goodput.goodput_percent == 50.0

    def test_empty_results(self):
        """Test with empty results."""
        thresholds = GoodputThresholds(ttft_ms=500.0)
        goodput = GoodputCalculator.calculate([], thresholds)

        assert goodput.satisfied_requests == 0
        assert goodput.total_requests == 0
        assert goodput.goodput_percent == 0.0

    def test_no_thresholds_set(self):
        """Test with no thresholds set (all should pass)."""
        results = [
            RequestResult(
                request_id=i,
                ttft_ms=1000.0,  # High values but no threshold
                tpot_ms=100.0,
                e2e_latency_ms=10000.0,
                input_tokens=256,
                output_tokens=128,
            )
            for i in range(5)
        ]

        thresholds = GoodputThresholds()  # No thresholds
        goodput = GoodputCalculator.calculate(results, thresholds)

        # All should pass since no thresholds to check
        assert goodput.satisfied_requests == 5
        assert goodput.goodput_percent == 100.0

    def test_and_condition(self):
        """Test that ALL thresholds must be met (AND condition)."""
        results = [
            RequestResult(
                request_id=0,
                ttft_ms=200.0,  # Meets TTFT
                tpot_ms=30.0,  # Meets TPOT
                e2e_latency_ms=5000.0,  # FAILS E2E (> 3000)
                input_tokens=256,
                output_tokens=128,
            )
        ]

        thresholds = GoodputThresholds(ttft_ms=500.0, tpot_ms=50.0, e2e_ms=3000.0)
        goodput = GoodputCalculator.calculate(results, thresholds)

        # Should fail because E2E exceeds threshold
        assert goodput.satisfied_requests == 0
        assert goodput.goodput_percent == 0.0
        assert goodput.ttft_satisfied == 1  # Individual check passed
        assert goodput.tpot_satisfied == 1  # Individual check passed
        assert goodput.e2e_satisfied == 0  # Individual check failed

    def test_per_threshold_breakdown(self):
        """Test per-threshold satisfaction breakdown."""
        results = []
        for i in range(10):
            results.append(RequestResult(
                request_id=i,
                ttft_ms=200.0 if i < 8 else 600.0,  # 80% meet TTFT
                tpot_ms=30.0 if i < 6 else 60.0,  # 60% meet TPOT
                e2e_latency_ms=1000.0 if i < 9 else 4000.0,  # 90% meet E2E
                input_tokens=256,
                output_tokens=128,
            ))

        thresholds = GoodputThresholds(ttft_ms=500.0, tpot_ms=50.0, e2e_ms=3000.0)
        goodput = GoodputCalculator.calculate(results, thresholds)

        assert goodput.ttft_satisfied == 8
        assert goodput.tpot_satisfied == 6
        assert goodput.e2e_satisfied == 9
        # Only those meeting ALL thresholds count
        assert goodput.satisfied_requests <= min(8, 6, 9)

    def test_boundary_values(self):
        """Test boundary values (exactly at threshold)."""
        results = [
            RequestResult(
                request_id=0,
                ttft_ms=500.0,  # Exactly at threshold
                tpot_ms=50.0,  # Exactly at threshold
                e2e_latency_ms=3000.0,  # Exactly at threshold
                input_tokens=256,
                output_tokens=128,
            )
        ]

        thresholds = GoodputThresholds(ttft_ms=500.0, tpot_ms=50.0, e2e_ms=3000.0)
        goodput = GoodputCalculator.calculate(results, thresholds)

        # Values exactly at threshold should meet SLO (<=)
        assert goodput.satisfied_requests == 1
        assert goodput.goodput_percent == 100.0
