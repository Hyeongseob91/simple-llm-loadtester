"""Asyncio-based load generator for LLM servers."""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Callable, Optional, Protocol

from core.metrics import MetricsCalculator
from core.models import (
    BenchmarkConfig,
    BenchmarkResult,
    ConcurrencyResult,
    RequestResult,
)


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


ProgressCallback = Callable[[int, int, Optional[str]], None]


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
        lock = asyncio.Lock()

        async def send_request(request_id: int) -> RequestResult:
            nonlocal completed
            async with semaphore:
                result = await self.adapter.send_request(
                    request_id, prompt, output_len, stream
                )

                async with lock:
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, num_requests, None)

                return result

        start_time = time.perf_counter()

        tasks = [send_request(i) for i in range(num_requests)]
        results = await asyncio.gather(*tasks)

        end_time = time.perf_counter()
        duration = end_time - start_time

        return list(results), duration

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
    ) -> BenchmarkResult:
        """Run the load test.

        Args:
            config: Benchmark configuration.
            progress_callback: Optional callback for progress updates.

        Returns:
            BenchmarkResult with all metrics.
        """
        run_id = str(uuid.uuid4())
        started_at = datetime.now()

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
        )
