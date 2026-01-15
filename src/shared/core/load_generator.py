"""Asyncio-based load generator for LLM servers."""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Callable, Optional, Protocol

from shared.core.metrics import MetricsCalculator
from shared.core.models import (
    BenchmarkConfig,
    BenchmarkResult,
    ConcurrencyResult,
    RequestResult,
    ValidationResult,
)
from shared.core.validator import MetricsValidator, format_validation_result

logger = logging.getLogger(__name__)


class ServerAdapter(Protocol):
    """Protocol for server adapters."""

    async def send_request(
        self,
        request_id: int,
        prompt: str,
        max_tokens: int,
        stream: bool,
    ) -> RequestResult:
        """Send a request to the server."""
        ...

    async def health_check(self) -> bool:
        """Check server health."""
        ...

    async def warmup(self, num_requests: int, input_len: int, output_len: int) -> None:
        """Run warmup requests."""
        ...


ProgressCallback = Callable[[int, int, Optional[str | dict]], None]


class LoadGenerator:
    """Asyncio-based load generator for LLM server benchmarking."""

    def __init__(self, adapter: ServerAdapter):
        """Initialize load generator with a server adapter.

        Args:
            adapter: Server adapter implementing ServerAdapter protocol.
        """
        self.adapter = adapter

    def _generate_prompt(self, input_len: int) -> str:
        """Generate a prompt with approximately the specified token count.

        Args:
            input_len: Target input token length.

        Returns:
            Generated prompt string.
        """
        base_prompt = "Write a detailed explanation about the following topic: "
        filler = "artificial intelligence and machine learning " * (input_len // 5)
        return base_prompt + filler[: input_len * 4]

    def _calculate_partial_metrics(
        self,
        results: list[RequestResult],
        elapsed: float,
        concurrency: int,
    ) -> dict | None:
        """Calculate partial metrics from in-progress results.

        Args:
            results: List of completed request results.
            elapsed: Elapsed time in seconds.
            concurrency: Current concurrency level.

        Returns:
            Dictionary with partial metrics or None if no successful results.
        """
        successful = [r for r in results if r.success]
        if not successful:
            return None

        ttfts = [r.ttft_ms for r in successful if r.ttft_ms is not None]
        e2es = [r.e2e_latency_ms for r in successful if r.e2e_latency_ms is not None]
        total_tokens = sum(r.output_tokens for r in successful if r.output_tokens)

        return {
            "concurrency": concurrency,
            "completed": len(results),
            "success_count": len(successful),
            "error_count": len(results) - len(successful),
            "ttft_avg": sum(ttfts) / len(ttfts) if ttfts else 0,
            "ttft_p50": sorted(ttfts)[len(ttfts) // 2] if ttfts else 0,
            "e2e_avg": sum(e2es) / len(e2es) if e2es else 0,
            "throughput_current": total_tokens / elapsed if elapsed > 0 else 0,
            "timestamp": time.time(),  # Unix timestamp for time-series charts
        }

    async def _run_concurrent_requests(
        self,
        concurrency: int,
        num_requests: int,
        input_len: int,
        output_len: int,
        stream: bool,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> tuple[list[RequestResult], float]:
        """Run concurrent requests at specified concurrency level.

        Args:
            concurrency: Number of concurrent requests.
            num_requests: Total number of requests to send.
            input_len: Input token length.
            output_len: Output token length.
            stream: Whether to use streaming.
            progress_callback: Optional callback for progress updates.

        Returns:
            Tuple of (results list, duration in seconds).
        """
        results: list[RequestResult] = []
        semaphore = asyncio.Semaphore(concurrency)
        prompt = self._generate_prompt(input_len)
        completed = 0
        last_metrics_at = 0
        lock = asyncio.Lock()
        metrics_interval = max(10, num_requests // 20)  # 최소 10개, 또는 5%마다

        start_time = time.perf_counter()

        async def send_request(request_id: int) -> RequestResult:
            nonlocal completed, last_metrics_at
            async with semaphore:
                result = await self.adapter.send_request(
                    request_id, prompt, output_len, stream
                )

                async with lock:
                    results.append(result)  # 결과 즉시 저장
                    completed += 1

                    if progress_callback:
                        # 요청별 로그 정보 생성
                        request_log = {
                            "request_id": request_id,
                            "status": "completed" if result.success else "failed",
                            "ttft_ms": result.ttft_ms,
                            "e2e_ms": result.e2e_latency_ms,
                            "output_tokens": result.output_tokens,
                            "success": result.success,
                            "error_type": result.error_type,
                            "timestamp": time.time(),
                        }

                        # 매 N개 요청마다 실시간 메트릭 계산
                        if completed - last_metrics_at >= metrics_interval:
                            last_metrics_at = completed
                            elapsed = time.perf_counter() - start_time
                            partial_metrics = self._calculate_partial_metrics(
                                results, elapsed, concurrency
                            )
                            # 메트릭과 요청 로그 함께 전달
                            progress_callback(
                                completed,
                                num_requests,
                                {"metrics": partial_metrics, "request_log": request_log},
                            )
                        else:
                            # 요청 로그만 전달
                            progress_callback(
                                completed,
                                num_requests,
                                {"request_log": request_log},
                            )

                return result

        tasks = [send_request(i) for i in range(num_requests)]
        await asyncio.gather(*tasks)

        end_time = time.perf_counter()
        duration = end_time - start_time

        return results, duration

    async def _run_duration_based(
        self,
        concurrency: int,
        duration_seconds: int,
        input_len: int,
        output_len: int,
        stream: bool,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> tuple[list[RequestResult], float]:
        """Run requests for a specified duration.

        Args:
            concurrency: Number of concurrent requests.
            duration_seconds: How long to run the test.
            input_len: Input token length.
            output_len: Output token length.
            stream: Whether to use streaming.
            progress_callback: Optional callback for progress updates.

        Returns:
            Tuple of (results list, actual duration in seconds).
        """
        results: list[RequestResult] = []
        prompt = self._generate_prompt(input_len)
        request_id = 0
        lock = asyncio.Lock()

        start_time = time.perf_counter()
        end_time = start_time + duration_seconds

        async def worker():
            nonlocal request_id
            while time.perf_counter() < end_time:
                async with lock:
                    current_id = request_id
                    request_id += 1

                result = await self.adapter.send_request(
                    current_id, prompt, output_len, stream
                )

                async with lock:
                    results.append(result)
                    if progress_callback:
                        elapsed = time.perf_counter() - start_time
                        progress_callback(
                            int(elapsed),
                            duration_seconds,
                            f"{len(results)} requests",
                        )

        workers = [worker() for _ in range(concurrency)]
        await asyncio.gather(*workers)

        actual_duration = time.perf_counter() - start_time
        return results, actual_duration

    async def run(
        self,
        config: BenchmarkConfig,
        progress_callback: Optional[ProgressCallback] = None,
        enable_validation: bool = False,
        docker_enabled: bool = True,
        container_name: Optional[str] = None,
        validation_progress_callback: Optional[callable] = None,
    ) -> BenchmarkResult:
        """Run the load test.

        Args:
            config: Benchmark configuration.
            progress_callback: Optional callback for progress updates.
            enable_validation: Enable cross-validation against server metrics.
            docker_enabled: Enable Docker log validation (False = Prometheus only).
            container_name: Docker container name for log validation (auto-detected if None).
            validation_progress_callback: Optional callback for validation progress logs.

        Returns:
            BenchmarkResult with all metrics.
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now()

        # Initialize validator if enabled
        validator: Optional[MetricsValidator] = None
        if enable_validation:
            validator = MetricsValidator(
                server_url=config.server_url,
                docker_enabled=docker_enabled,
                container_name=container_name,
                progress_callback=validation_progress_callback,
            )
            await validator.initialize()
            await validator.collect_before()
            logger.info("Validation enabled: collecting server metrics before benchmark")

        concurrency_results: list[ConcurrencyResult] = []

        for concurrency in config.concurrency:
            if progress_callback:
                progress_callback(0, 1, f"Concurrency: {concurrency}")

            if config.duration_seconds:
                # Duration-based mode
                results, duration = await self._run_duration_based(
                    concurrency=concurrency,
                    duration_seconds=config.duration_seconds,
                    input_len=config.input_len,
                    output_len=config.output_len,
                    stream=config.stream,
                    progress_callback=progress_callback,
                )
            else:
                # Request count-based mode
                results, duration = await self._run_concurrent_requests(
                    concurrency=concurrency,
                    num_requests=config.num_prompts,
                    input_len=config.input_len,
                    output_len=config.output_len,
                    stream=config.stream,
                    progress_callback=progress_callback,
                )

            concurrency_result = MetricsCalculator.aggregate_results(
                results,
                duration,
                concurrency,
                goodput_thresholds=config.goodput_thresholds,
            )
            concurrency_results.append(concurrency_result)

        completed_at = datetime.now()
        total_duration = (completed_at - started_at).total_seconds()

        # Run validation if enabled
        validation_result: Optional[ValidationResult] = None
        if validator:
            await validator.collect_after()

            # Calculate aggregate metrics for validation
            total_requests = sum(r.total_requests for r in concurrency_results)
            successful_requests = sum(r.successful_requests for r in concurrency_results)
            total_output_tokens = sum(r.total_output_tokens for r in concurrency_results)

            # Weighted average TTFT
            ttft_values = [r.ttft.mean * r.successful_requests for r in concurrency_results]
            avg_ttft_ms = sum(ttft_values) / successful_requests if successful_requests > 0 else 0

            # Average throughput
            avg_throughput = sum(r.throughput_tokens_per_sec for r in concurrency_results) / len(
                concurrency_results
            ) if concurrency_results else 0

            validation_result = await validator.validate(
                client_total_requests=total_requests,
                client_successful_requests=successful_requests,
                client_avg_ttft_ms=avg_ttft_ms,
                client_total_output_tokens=total_output_tokens,
                client_throughput=avg_throughput,
            )

            # Log validation result
            logger.info(format_validation_result(validation_result))

        return BenchmarkResult(
            run_id=run_id,
            server_url=config.server_url,
            model=config.model,
            adapter=config.adapter,
            config=config,
            results=concurrency_results,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=total_duration,
            validation=validation_result,
        )
