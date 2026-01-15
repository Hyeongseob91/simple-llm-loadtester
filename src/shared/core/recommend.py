"""Infrastructure recommendation engine for LLM serving workloads.

This module provides GPU infrastructure recommendations based on:
1. Workload specifications (peak concurrency, SLO requirements)
2. Current infrastructure performance profile (from load tests)
3. Scaling calculations with configurable headroom

Reference: PRD Phase 5 - Infrastructure Recommendation
"""

import math
from typing import Callable, Optional

from shared.core.gpu_monitor import get_gpu_info
from shared.core.load_generator import LoadGenerator
from shared.core.models import (
    BenchmarkConfig,
    BenchmarkResult,
    ConcurrencyResult,
    GoodputThresholds,
    InfraProfile,
    InfraRecommendation,
    WorkloadSpec,
)


ProgressCallback = Callable[[str, int, int], None]


class InfraRecommender:
    """GPU infrastructure recommendation engine.

    This class performs load tests at multiple concurrency levels and
    recommends the number of GPUs needed to handle target workload.

    Example:
        >>> recommender = InfraRecommender(load_generator)
        >>> result = await recommender.recommend(
        ...     config=benchmark_config,
        ...     workload=WorkloadSpec(peak_concurrency=500),
        ...     concurrency_steps=[1, 10, 50, 100, 200],
        ...     headroom=0.2,
        ... )
        >>> print(f"Recommended: {result.recommended_gpu} x {result.recommended_count}")
    """

    def __init__(self, load_generator: LoadGenerator):
        """Initialize recommender with a load generator.

        Args:
            load_generator: LoadGenerator instance configured with server adapter.
        """
        self.load_generator = load_generator

    async def recommend(
        self,
        config: BenchmarkConfig,
        workload: WorkloadSpec,
        concurrency_steps: list[int] = [1, 10, 50, 100, 200],
        num_requests_per_step: int = 50,
        headroom: float = 0.2,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> tuple[InfraRecommendation, BenchmarkResult]:
        """Run profiling tests and generate infrastructure recommendation.

        Args:
            config: Base benchmark configuration (server_url, model, etc.)
            workload: Target workload specification with SLO requirements.
            concurrency_steps: List of concurrency levels to test.
            num_requests_per_step: Number of requests per concurrency level.
            headroom: Safety margin percentage (default: 20%).
            progress_callback: Optional callback(stage, current, total) for progress.

        Returns:
            Tuple of (InfraRecommendation, BenchmarkResult from profiling).
        """
        # Step 1: Profile current infrastructure
        if progress_callback:
            progress_callback("Profiling infrastructure", 0, len(concurrency_steps))

        profile_config = BenchmarkConfig(
            server_url=config.server_url,
            model=config.model,
            adapter=config.adapter,
            input_len=workload.avg_input_tokens,
            output_len=workload.avg_output_tokens,
            num_prompts=num_requests_per_step,
            concurrency=concurrency_steps,
            stream=config.stream,
            warmup=config.warmup,
            timeout=config.timeout,
            api_key=config.api_key,
            goodput_thresholds=GoodputThresholds(
                ttft_ms=workload.ttft_target_ms,
                tpot_ms=workload.tpot_target_ms,
            ),
        )

        # Run profiling benchmark
        def benchmark_progress(current: int, total: int, msg: Optional[str]) -> None:
            if progress_callback:
                progress_callback(f"Testing: {msg or ''}", current, total)

        benchmark_result = await self.load_generator.run(
            profile_config, progress_callback=benchmark_progress
        )

        # Step 2: Build infrastructure profile from results
        if progress_callback:
            progress_callback("Analyzing results", 0, 1)

        infra_profile = self._build_infra_profile(
            benchmark_result, workload
        )

        # Step 3: Calculate recommendation
        if progress_callback:
            progress_callback("Calculating recommendation", 0, 1)

        recommendation = self.calculate_recommendation(
            model_name=config.model,
            workload=workload,
            profile=infra_profile,
            headroom=headroom,
        )

        if progress_callback:
            progress_callback("Complete", 1, 1)

        return recommendation, benchmark_result

    def _build_infra_profile(
        self,
        benchmark_result: BenchmarkResult,
        workload: WorkloadSpec,
    ) -> InfraProfile:
        """Build infrastructure profile from benchmark results.

        Args:
            benchmark_result: Results from profiling benchmark.
            workload: Target workload specification.

        Returns:
            InfraProfile with measured performance characteristics.
        """
        # Get GPU information
        gpu_info = get_gpu_info()
        if gpu_info.available and gpu_info.metrics:
            gpu = gpu_info.metrics[0]
            gpu_model = gpu.device_name
            gpu_count = gpu_info.gpu_count
            gpu_memory_gb = gpu.memory_total_gb * gpu_count
        else:
            # Fallback if GPU info not available
            gpu_model = "Unknown GPU"
            gpu_count = 1
            gpu_memory_gb = 0.0

        # Find max concurrency meeting SLO
        max_concurrency_at_slo = self._find_max_concurrency_at_slo(
            benchmark_result.results, workload
        )

        # Find saturation point
        saturation_concurrency, saturation_goodput = self._find_saturation_point(
            benchmark_result.results
        )

        # Get throughput at max SLO concurrency
        throughput = 0.0
        goodput_at_max = 0.0
        for result in benchmark_result.results:
            if result.concurrency == max_concurrency_at_slo:
                throughput = result.throughput_tokens_per_sec
                if result.goodput:
                    goodput_at_max = result.goodput.goodput_percent
                break

        # If no exact match, use the best result
        if throughput == 0.0 and benchmark_result.results:
            best = max(benchmark_result.results, key=lambda r: r.throughput_tokens_per_sec)
            throughput = best.throughput_tokens_per_sec
            if best.goodput:
                goodput_at_max = best.goodput.goodput_percent

        return InfraProfile(
            gpu_model=gpu_model,
            gpu_count=gpu_count,
            gpu_memory_gb=gpu_memory_gb,
            max_concurrency_at_slo=max_concurrency_at_slo,
            throughput_tokens_per_sec=throughput,
            goodput_at_max_concurrency=goodput_at_max,
            saturation_concurrency=saturation_concurrency,
            saturation_goodput=saturation_goodput,
        )

    def _find_max_concurrency_at_slo(
        self,
        results: list[ConcurrencyResult],
        workload: WorkloadSpec,
    ) -> int:
        """Find maximum concurrency level meeting SLO requirements.

        Args:
            results: List of concurrency test results.
            workload: Target workload with SLO thresholds.

        Returns:
            Maximum concurrency meeting SLO, or lowest tested if none meet SLO.
        """
        if not results:
            return 1

        # Sort by concurrency descending to find highest meeting SLO
        sorted_results = sorted(results, key=lambda r: r.concurrency, reverse=True)

        for result in sorted_results:
            meets_slo = True

            # Check TTFT (using p95 to be safe)
            if result.ttft.p95 > workload.ttft_target_ms:
                meets_slo = False

            # Check TPOT if available
            if result.tpot and result.tpot.p95 > workload.tpot_target_ms:
                meets_slo = False

            # Check Goodput if available
            if result.goodput:
                if result.goodput.goodput_percent < workload.goodput_target_percent:
                    meets_slo = False

            if meets_slo:
                return result.concurrency

        # If no concurrency meets SLO, return the lowest tested
        return min(r.concurrency for r in results)

    def _find_saturation_point(
        self,
        results: list[ConcurrencyResult],
    ) -> tuple[int, float]:
        """Find the saturation point where performance starts degrading.

        The saturation point is identified by:
        1. Goodput dropping below threshold (if available)
        2. Error rate increasing significantly
        3. Latency increasing disproportionately

        Args:
            results: List of concurrency test results.

        Returns:
            Tuple of (saturation_concurrency, goodput_at_saturation).
        """
        if not results:
            return (1, 100.0)

        if len(results) == 1:
            result = results[0]
            goodput = result.goodput.goodput_percent if result.goodput else 100.0
            return (result.concurrency, goodput)

        # Sort by concurrency ascending
        sorted_results = sorted(results, key=lambda r: r.concurrency)

        # Find point where goodput drops significantly or errors increase
        prev_goodput = 100.0
        saturation_concurrency = sorted_results[-1].concurrency
        saturation_goodput = 100.0

        for i, result in enumerate(sorted_results):
            current_goodput = result.goodput.goodput_percent if result.goodput else 100.0

            # Saturation indicators:
            # 1. Goodput drop > 10% from previous
            # 2. Error rate > 5%
            # 3. Goodput below 90%

            is_saturated = False

            if prev_goodput - current_goodput > 10:
                is_saturated = True
            elif result.error_rate_percent > 5:
                is_saturated = True
            elif current_goodput < 90:
                is_saturated = True

            if is_saturated:
                # Use previous concurrency as saturation point (before degradation)
                if i > 0:
                    prev_result = sorted_results[i - 1]
                    saturation_concurrency = prev_result.concurrency
                    saturation_goodput = prev_result.goodput.goodput_percent if prev_result.goodput else 100.0
                else:
                    saturation_concurrency = result.concurrency
                    saturation_goodput = current_goodput
                break

            prev_goodput = current_goodput
            saturation_concurrency = result.concurrency
            saturation_goodput = current_goodput

        return (saturation_concurrency, saturation_goodput)

    def calculate_recommendation(
        self,
        model_name: str,
        workload: WorkloadSpec,
        profile: InfraProfile,
        headroom: float = 0.2,
    ) -> InfraRecommendation:
        """Calculate GPU infrastructure recommendation.

        Formula: ceil(target_concurrency / max_concurrency_at_slo) × (1 + headroom)

        Args:
            model_name: Name of the LLM model.
            workload: Target workload specification.
            profile: Current infrastructure performance profile.
            headroom: Safety margin percentage (default: 20%).

        Returns:
            InfraRecommendation with recommended GPU count and reasoning.
        """
        # Calculate scaling factor
        target = workload.peak_concurrency
        max_at_slo = profile.max_concurrency_at_slo

        if max_at_slo <= 0:
            max_at_slo = 1  # Prevent division by zero

        scaling_factor = target / max_at_slo

        # Apply headroom and round up
        raw_gpu_count = scaling_factor * (1 + headroom)
        recommended_count = max(math.ceil(raw_gpu_count), profile.gpu_count)

        # Determine tensor parallelism recommendation
        # Simple heuristic: TP > 1 for large models or many GPUs
        tensor_parallelism = 1
        if recommended_count >= 4:
            tensor_parallelism = 2
        if recommended_count >= 8:
            tensor_parallelism = 4

        # Calculate estimated performance
        estimated_max_concurrency = int(max_at_slo * recommended_count / profile.gpu_count)
        estimated_throughput = profile.throughput_tokens_per_sec * recommended_count / profile.gpu_count
        estimated_goodput = min(profile.goodput_at_max_concurrency + (headroom * 10), 99.9)

        # Build calculation formula and reasoning
        calculation_formula = (
            f"ceil({target} / {max_at_slo}) × {1 + headroom:.1f} = "
            f"ceil({scaling_factor:.2f}) × {1 + headroom:.1f} = "
            f"{math.ceil(scaling_factor)} × {1 + headroom:.1f} = {raw_gpu_count:.1f} → {recommended_count}"
        )

        reasoning = self._build_reasoning(
            profile=profile,
            workload=workload,
            recommended_count=recommended_count,
            headroom=headroom,
        )

        return InfraRecommendation(
            model_name=model_name,
            workload=workload,
            current_infra=profile,
            recommended_gpu=profile.gpu_model,
            recommended_count=recommended_count,
            tensor_parallelism=tensor_parallelism,
            estimated_max_concurrency=estimated_max_concurrency,
            estimated_goodput=estimated_goodput,
            estimated_throughput=estimated_throughput,
            headroom_percent=headroom * 100,
            calculation_formula=calculation_formula,
            reasoning=reasoning,
        )

    def _build_reasoning(
        self,
        profile: InfraProfile,
        workload: WorkloadSpec,
        recommended_count: int,
        headroom: float,
    ) -> str:
        """Build detailed reasoning for the recommendation.

        Args:
            profile: Current infrastructure profile.
            workload: Target workload specification.
            recommended_count: Recommended GPU count.
            headroom: Applied headroom percentage.

        Returns:
            Detailed reasoning string.
        """
        lines = []

        # Current capability
        lines.append(
            f"현재 {profile.gpu_model} {profile.gpu_count}장으로 "
            f"최대 {profile.max_concurrency_at_slo}명 동시 처리 가능 "
            f"(Goodput {profile.goodput_at_max_concurrency:.1f}%)."
        )

        # Target requirement
        lines.append(
            f"목표: {workload.peak_concurrency}명 동시 처리 "
            f"(TTFT < {workload.ttft_target_ms}ms, Goodput > {workload.goodput_target_percent}%)."
        )

        # Scaling explanation
        max_at_slo = profile.max_concurrency_at_slo if profile.max_concurrency_at_slo > 0 else 1
        scale_factor = workload.peak_concurrency / max_at_slo
        lines.append(f"스케일링 비율: {scale_factor:.2f}배 필요.")

        # Headroom explanation
        lines.append(f"안전 여유분 {headroom * 100:.0f}% 적용.")

        # Final recommendation
        lines.append(
            f"결론: {profile.gpu_model} {recommended_count}장 필요."
        )

        # Saturation warning if applicable
        if profile.saturation_concurrency < workload.peak_concurrency:
            lines.append(
                f"참고: 포화점 {profile.saturation_concurrency} 동시성에서 "
                f"Goodput이 {profile.saturation_goodput:.1f}%로 감소 시작."
            )

        return " ".join(lines)
