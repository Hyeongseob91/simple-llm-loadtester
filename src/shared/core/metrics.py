"""Metrics calculation utilities including Goodput."""

from typing import Optional

import numpy as np

from shared.core.models import (
    ConcurrencyResult,
    GoodputResult,
    GoodputThresholds,
    LatencyStats,
    RequestResult,
)


class MetricsCalculator:
    """Calculate benchmark metrics from raw results."""

    @staticmethod
    def calculate_latency_stats(values: list[float]) -> LatencyStats:
        """Calculate latency statistics from a list of values.

        Args:
            values: List of latency values in milliseconds.

        Returns:
            LatencyStats object with min, max, mean, median, percentiles, and std.
        """
        if not values:
            return LatencyStats(
                min=0.0,
                max=0.0,
                mean=0.0,
                median=0.0,
                p50=0.0,
                p95=0.0,
                p99=0.0,
                std=0.0,
            )

        arr = np.array(values)
        return LatencyStats(
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            mean=float(np.mean(arr)),
            median=float(np.median(arr)),
            p50=float(np.percentile(arr, 50)),
            p95=float(np.percentile(arr, 95)),
            p99=float(np.percentile(arr, 99)),
            std=float(np.std(arr)),
        )

    @staticmethod
    def calculate_throughput(total_tokens: int, duration_seconds: float) -> float:
        """Calculate throughput in tokens per second."""
        if duration_seconds <= 0:
            return 0.0
        return total_tokens / duration_seconds

    @staticmethod
    def calculate_request_rate(total_requests: int, duration_seconds: float) -> float:
        """Calculate request rate in requests per second."""
        if duration_seconds <= 0:
            return 0.0
        return total_requests / duration_seconds

    @staticmethod
    def aggregate_results(
        results: list[RequestResult],
        duration_seconds: float,
        concurrency: int,
        goodput_thresholds: Optional[GoodputThresholds] = None,
    ) -> ConcurrencyResult:
        """Aggregate individual request results into concurrency-level statistics.

        Args:
            results: List of individual request results.
            duration_seconds: Total test duration in seconds.
            concurrency: Concurrency level for this batch.
            goodput_thresholds: Optional SLO thresholds for Goodput calculation.

        Returns:
            ConcurrencyResult with aggregated statistics.
        """
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        # Extract metric values
        ttft_values = [r.ttft_ms for r in successful]
        e2e_values = [r.e2e_latency_ms for r in successful]
        tpot_values = [r.tpot_ms for r in successful if r.tpot_ms is not None]

        itl_all: list[float] = []
        for r in successful:
            if r.itl_ms:
                itl_all.extend(r.itl_ms)

        # Token counts
        total_input = sum(r.input_tokens for r in successful)
        total_output = sum(r.output_tokens for r in successful)

        # Calculate statistics
        ttft_stats = MetricsCalculator.calculate_latency_stats(ttft_values)
        e2e_stats = MetricsCalculator.calculate_latency_stats(e2e_values)
        tpot_stats = (
            MetricsCalculator.calculate_latency_stats(tpot_values) if tpot_values else None
        )
        itl_stats = MetricsCalculator.calculate_latency_stats(itl_all) if itl_all else None

        # Throughput and rates
        throughput = MetricsCalculator.calculate_throughput(total_output, duration_seconds)
        request_rate = MetricsCalculator.calculate_request_rate(len(successful), duration_seconds)
        error_rate = len(failed) / len(results) * 100 if results else 0.0

        # Calculate Goodput if thresholds provided
        goodput_result = None
        if goodput_thresholds:
            goodput_result = GoodputCalculator.calculate(successful, goodput_thresholds)

        return ConcurrencyResult(
            concurrency=concurrency,
            ttft=ttft_stats,
            tpot=tpot_stats,
            itl=itl_stats,
            e2e_latency=e2e_stats,
            throughput_tokens_per_sec=throughput,
            request_rate_per_sec=request_rate,
            total_requests=len(results),
            successful_requests=len(successful),
            failed_requests=len(failed),
            error_rate_percent=error_rate,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            duration_seconds=duration_seconds,
            goodput=goodput_result,
        )


class GoodputCalculator:
    """Calculate Goodput based on SLO thresholds.

    Goodput is the percentage of requests that meet ALL specified SLO thresholds.
    Reference: NVIDIA GenAI-Perf Goodput concept.
    """

    @staticmethod
    def calculate(
        results: list[RequestResult],
        thresholds: GoodputThresholds,
    ) -> GoodputResult:
        """Calculate Goodput from request results.

        Args:
            results: List of successful request results.
            thresholds: SLO thresholds to check against.

        Returns:
            GoodputResult with satisfaction counts and percentage.
        """
        if not results:
            return GoodputResult(
                thresholds=thresholds,
                satisfied_requests=0,
                total_requests=0,
                goodput_percent=0.0,
            )

        total = len(results)

        # Count per-threshold satisfaction
        ttft_satisfied = None
        tpot_satisfied = None
        e2e_satisfied = None

        if thresholds.ttft_ms is not None:
            ttft_satisfied = sum(1 for r in results if r.ttft_ms <= thresholds.ttft_ms)

        if thresholds.tpot_ms is not None:
            tpot_satisfied = sum(
                1 for r in results
                if r.tpot_ms is not None and r.tpot_ms <= thresholds.tpot_ms
            )

        if thresholds.e2e_ms is not None:
            e2e_satisfied = sum(1 for r in results if r.e2e_latency_ms <= thresholds.e2e_ms)

        # Count requests meeting ALL thresholds
        satisfied = 0
        for r in results:
            meets_all = True

            if thresholds.ttft_ms is not None and r.ttft_ms > thresholds.ttft_ms:
                meets_all = False
            if thresholds.tpot_ms is not None:
                if r.tpot_ms is None or r.tpot_ms > thresholds.tpot_ms:
                    meets_all = False
            if thresholds.e2e_ms is not None and r.e2e_latency_ms > thresholds.e2e_ms:
                meets_all = False

            if meets_all:
                satisfied += 1

        goodput_percent = (satisfied / total * 100) if total > 0 else 0.0

        return GoodputResult(
            thresholds=thresholds,
            satisfied_requests=satisfied,
            total_requests=total,
            goodput_percent=goodput_percent,
            ttft_satisfied=ttft_satisfied,
            tpot_satisfied=tpot_satisfied,
            e2e_satisfied=e2e_satisfied,
        )
