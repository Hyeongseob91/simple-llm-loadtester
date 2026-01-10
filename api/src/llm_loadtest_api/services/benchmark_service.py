"""Benchmark service for running load tests."""

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from core.load_generator import LoadGenerator
from core.models import BenchmarkConfig, BenchmarkResult, GoodputThresholds
from adapters.base import AdapterFactory
from adapters.openai_compat import OpenAICompatibleAdapter  # Register adapter

from llm_loadtest_api.database import Database
from llm_loadtest_api.models.schemas import BenchmarkRequest


class BenchmarkService:
    """Service for managing benchmark runs."""

    def __init__(self, db: Database):
        self.db = db
        self._running_tasks: dict[str, asyncio.Task] = {}

    async def start_benchmark(self, request: BenchmarkRequest) -> str:
        """Start a new benchmark run.

        Args:
            request: Benchmark request parameters.

        Returns:
            Run ID for the new benchmark.
        """
        run_id = str(uuid.uuid4())

        # Convert request to config
        goodput_thresholds = None
        if request.goodput_thresholds:
            goodput_thresholds = GoodputThresholds(
                ttft_ms=request.goodput_thresholds.ttft_ms,
                tpot_ms=request.goodput_thresholds.tpot_ms,
                e2e_ms=request.goodput_thresholds.e2e_ms,
            )

        config = BenchmarkConfig(
            server_url=request.server_url,
            model=request.model,
            adapter=request.adapter,
            input_len=request.input_len,
            output_len=request.output_len,
            num_prompts=request.num_prompts,
            concurrency=request.concurrency,
            stream=request.stream,
            warmup=request.warmup,
            timeout=request.timeout,
            api_key=request.api_key,
            duration_seconds=request.duration_seconds,
            goodput_thresholds=goodput_thresholds,
        )

        # Save to database
        self.db.create_run(
            run_id=run_id,
            server_url=request.server_url,
            model=request.model,
            adapter=request.adapter,
            config=config.model_dump(),
        )

        # Start background task
        task = asyncio.create_task(self._run_benchmark(run_id, config))
        self._running_tasks[run_id] = task

        return run_id

    async def _run_benchmark(self, run_id: str, config: BenchmarkConfig) -> None:
        """Run benchmark in background.

        Args:
            run_id: Unique run identifier.
            config: Benchmark configuration.
        """
        try:
            # Update status to running
            self.db.update_status(run_id, "running", started_at=datetime.now())

            # Create adapter
            adapter = AdapterFactory.create(
                name=config.adapter,
                server_url=config.server_url,
                model=config.model,
                api_key=config.api_key,
                timeout=config.timeout,
            )

            # Run warmup
            if config.warmup > 0:
                await adapter.warmup(
                    config.warmup,
                    config.input_len // 4,
                    config.output_len // 4,
                )

            # Run load generator
            generator = LoadGenerator(adapter)
            result = await generator.run(config)

            # Save result
            self.db.save_result(run_id, result.model_dump(mode="json"))

        except Exception as e:
            # Update status to failed
            self.db.update_status(run_id, "failed")
            # Optionally log error
            print(f"[BenchmarkService] Run {run_id} failed: {e}")

        finally:
            # Clean up task reference
            if run_id in self._running_tasks:
                del self._running_tasks[run_id]

    def get_status(self, run_id: str) -> Optional[dict]:
        """Get benchmark run status."""
        return self.db.get_run(run_id)

    def get_result(self, run_id: str) -> Optional[dict]:
        """Get benchmark result."""
        return self.db.get_result(run_id)

    def list_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[dict]:
        """List benchmark runs."""
        return self.db.list_runs(limit, offset, status)

    def delete_run(self, run_id: str) -> bool:
        """Delete a benchmark run."""
        # Cancel if running
        if run_id in self._running_tasks:
            self._running_tasks[run_id].cancel()
            del self._running_tasks[run_id]

        return self.db.delete_run(run_id)

    def compare_runs(self, run_ids: list[str]) -> dict:
        """Compare multiple benchmark runs.

        Args:
            run_ids: List of run IDs to compare.

        Returns:
            Comparison summary.
        """
        results = []
        for run_id in run_ids:
            result = self.get_result(run_id)
            if result:
                results.append(result)

        if len(results) < 2:
            return {"error": "Need at least 2 completed runs to compare"}

        # Build comparison
        comparison = {
            "run_count": len(results),
            "best_throughput": {
                "run_id": "",
                "value": 0.0,
            },
            "best_ttft": {
                "run_id": "",
                "value": float("inf"),
            },
            "by_concurrency": {},
        }

        for result in results:
            run_id = result.get("run_id", "unknown")
            for cr in result.get("results", []):
                throughput = cr.get("throughput_tokens_per_sec", 0)
                ttft_p50 = cr.get("ttft", {}).get("p50", float("inf"))

                if throughput > comparison["best_throughput"]["value"]:
                    comparison["best_throughput"] = {
                        "run_id": run_id,
                        "value": throughput,
                        "concurrency": cr.get("concurrency"),
                    }

                if ttft_p50 < comparison["best_ttft"]["value"]:
                    comparison["best_ttft"] = {
                        "run_id": run_id,
                        "value": ttft_p50,
                        "concurrency": cr.get("concurrency"),
                    }

        return comparison
