"""Benchmark service for running load tests."""

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Add src directory to path
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.core.load_generator import LoadGenerator
from shared.core.models import BenchmarkConfig, BenchmarkResult, GoodputThresholds
from shared.core.gpu_monitor import GPUMonitor, get_gpu_static_info
from shared.core.system_info import get_system_info
from shared.core.serving_engine_info import get_vllm_engine_info
from shared.adapters.base import AdapterFactory
from shared.adapters.openai_compat import OpenAICompatibleAdapter  # Register adapter

from shared.database import Database
from llm_loadtest_api.models.schemas import BenchmarkRequest
from llm_loadtest_api.routers.websocket import get_connection_manager


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

        # Extract user-provided vLLM config (optional)
        vllm_config = None
        if request.vllm_config:
            vllm_config = {
                k: v for k, v in request.vllm_config.model_dump().items()
                if v is not None
            }
            if not vllm_config:
                vllm_config = None

        # Extract validation config (optional)
        validation_config = None
        if request.validation_config and request.validation_config.enabled:
            validation_config = request.validation_config.model_dump()

        # Save to database
        self.db.create_run(
            run_id=run_id,
            server_url=request.server_url,
            model=request.model,
            adapter=request.adapter,
            config=config.model_dump(),
        )

        # Start background task
        task = asyncio.create_task(
            self._run_benchmark(run_id, config, vllm_config, validation_config)
        )
        self._running_tasks[run_id] = task

        return run_id

    async def _run_benchmark(
        self,
        run_id: str,
        config: BenchmarkConfig,
        vllm_config: Optional[dict] = None,
        validation_config: Optional[dict] = None,
    ) -> None:
        """Run benchmark in background.

        Args:
            run_id: Unique run identifier.
            config: Benchmark configuration.
            vllm_config: User-provided vLLM configuration (optional).
            validation_config: Validation configuration (optional).
        """
        manager = get_connection_manager()
        gpu_monitor: Optional[GPUMonitor] = None
        gpu_monitoring_active = False

        try:
            # Update status to running
            self.db.update_status(run_id, "running", started_at=datetime.now(timezone.utc))

            # Capture server infrastructure info BEFORE benchmark starts
            server_infra = await self._capture_server_infra(config.server_url)

            # Start GPU monitoring in background
            gpu_monitor = GPUMonitor(sample_interval=1.0)
            gpu_monitoring_active = gpu_monitor.start()

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

            # Run load generator with progress callback
            generator = LoadGenerator(adapter)

            # Setup progress tracking
            concurrency_levels = list(config.concurrency)
            total_levels = len(concurrency_levels)
            state = {"level_index": 0, "current_level": concurrency_levels[0]}

            def progress_callback(current: int, total: int, extra: Any) -> None:
                """Callback to send progress updates via WebSocket."""
                # extra가 "Concurrency: X" 형태면 새 레벨 시작
                if isinstance(extra, str) and extra.startswith("Concurrency:"):
                    try:
                        level_value = int(extra.split(":")[1].strip())
                        state["current_level"] = level_value
                        if level_value in concurrency_levels:
                            state["level_index"] = concurrency_levels.index(level_value)
                    except (ValueError, IndexError):
                        pass
                    return  # 레벨 시작 알림은 별도로 WebSocket 전송하지 않음

                # extra에서 메트릭과 요청 로그 추출
                partial_metrics = None
                request_log = None
                if isinstance(extra, dict):
                    # 새 형식: {"metrics": {...}, "request_log": {...}}
                    if "metrics" in extra or "request_log" in extra:
                        partial_metrics = extra.get("metrics")
                        request_log = extra.get("request_log")
                    else:
                        # 이전 형식 호환: extra 자체가 메트릭
                        partial_metrics = extra

                # 진행 업데이트를 WebSocket으로 전송 (메트릭 + 요청 로그 포함)
                asyncio.create_task(
                    manager.send_progress(
                        run_id=run_id,
                        status="running",
                        current=current,
                        total=total,
                        concurrency_level=state["current_level"],
                        current_concurrency_index=state["level_index"],
                        total_concurrency_levels=total_levels,
                        metrics=partial_metrics,
                        request_log=request_log,
                    )
                )

            # Run with or without validation
            enable_validation = validation_config is not None
            docker_enabled = validation_config.get("docker_enabled", True) if validation_config else True
            container_name = validation_config.get("container_name") if validation_config else None

            # Setup validation progress callback
            def validation_progress_callback(step: str, message: str, status: str) -> None:
                """Callback to send validation progress logs via WebSocket."""
                asyncio.create_task(
                    manager.send_validation_log(
                        run_id=run_id,
                        step=step,
                        message=message,
                        status=status,
                    )
                )

            result = await generator.run(
                config,
                progress_callback,
                enable_validation=enable_validation,
                docker_enabled=docker_enabled,
                container_name=container_name,
                validation_progress_callback=validation_progress_callback if enable_validation else None,
            )

            # Stop GPU monitoring and collect metrics
            if gpu_monitoring_active and gpu_monitor:
                gpu_result = gpu_monitor.stop()
                gpu_monitoring_active = False
                if server_infra and gpu_result.available and gpu_result.metrics:
                    server_infra["gpu_metrics_during_benchmark"] = [
                        {
                            "gpu_index": m.gpu_index,
                            "device_name": m.device_name,
                            "avg_memory_used_gb": round(m.avg_memory_used_gb, 2),
                            "peak_memory_used_gb": round(m.peak_memory_used_gb, 2),
                            "avg_gpu_util_percent": round(m.avg_gpu_util_percent, 1),
                            "peak_gpu_util_percent": round(m.peak_gpu_util_percent, 1),
                            "avg_temperature_celsius": m.temperature_celsius,
                            "peak_temperature_celsius": m.peak_temperature_celsius,
                            "avg_power_draw_watts": m.power_draw_watts,
                            "peak_power_draw_watts": m.peak_power_draw_watts,
                        }
                        for m in gpu_result.metrics
                    ]

            # Add user-provided vLLM config to server_infra
            if vllm_config and server_infra:
                server_infra["vllm_config"] = vllm_config

            # Save result with summary and server_infra included
            result_dict = result.model_dump(mode="json")
            result_dict["summary"] = result.get_summary()
            result_dict["server_infra"] = server_infra
            self.db.save_result(run_id, result_dict)

            # Send completed message via WebSocket
            await manager.send_completed(run_id, {"status": "completed"})

        except Exception as e:
            # Update status to failed
            self.db.update_status(run_id, "failed")
            # Send failed message via WebSocket
            await manager.send_failed(run_id, str(e))
            # Log error
            print(f"[BenchmarkService] Run {run_id} failed: {e}")

        finally:
            # Stop GPU monitoring if still running
            if gpu_monitoring_active and gpu_monitor:
                try:
                    gpu_monitor.stop()
                except Exception:
                    pass
            # Clean up task reference
            if run_id in self._running_tasks:
                del self._running_tasks[run_id]

    async def _capture_server_infra(self, server_url: str) -> Optional[dict]:
        """Capture server infrastructure information before benchmark.

        Collects:
        - System info (CPU, RAM) using psutil
        - GPU static info (model, driver, CUDA version) using pynvml
        - Serving engine info (vLLM config) from server endpoints

        Args:
            server_url: LLM server URL

        Returns:
            Dictionary with server infrastructure info, or None if collection failed.
        """
        infra: dict = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        # Collect system info (CPU, RAM)
        try:
            system = get_system_info()
            if system:
                infra["system"] = system
        except Exception as e:
            print(f"[BenchmarkService] Failed to collect system info: {e}")

        # Collect GPU static info (model, driver, CUDA)
        try:
            gpu = get_gpu_static_info()
            if gpu:
                infra["gpu"] = gpu
        except Exception as e:
            print(f"[BenchmarkService] Failed to collect GPU info: {e}")

        # Collect serving engine info (vLLM config)
        try:
            engine = await get_vllm_engine_info(server_url)
            if engine:
                infra["serving_engine"] = engine
        except Exception as e:
            print(f"[BenchmarkService] Failed to collect serving engine info: {e}")

        # Return infra if we collected at least some info
        return infra if len(infra) > 1 else None

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
