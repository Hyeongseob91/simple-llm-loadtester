"""Infrastructure Recommendation API routes."""

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.core.load_generator import LoadGenerator
from shared.core.models import BenchmarkConfig, WorkloadSpec
from shared.core.recommend import InfraRecommender
from shared.adapters.base import AdapterFactory
from shared.adapters.openai_compat import OpenAICompatibleAdapter  # Registers the adapter

from llm_loadtest_api.auth import APIKeyAuth
from llm_loadtest_api.logging_config import get_logger, log_benchmark_event
from llm_loadtest_api.models.schemas import (
    RecommendRequest,
    RecommendResponse,
    RecommendStatus,
    WorkloadSpecSchema,
    InfraProfileSchema,
    InfraRecommendationSchema,
    ConcurrencyResultSchema,
    LatencyStatsSchema,
    GoodputResultSchema,
)

# Logger
logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/benchmark", tags=["recommend"])

# In-memory storage for recommendation runs
_recommend_runs: dict[str, dict] = {}
_recommend_results: dict[str, dict] = {}
_running_tasks: dict[str, asyncio.Task] = {}


def _convert_latency_stats(stats) -> LatencyStatsSchema:
    """Convert LatencyStats to schema."""
    return LatencyStatsSchema(
        min=stats.min,
        max=stats.max,
        mean=stats.mean,
        p50=stats.p50,
        p95=stats.p95,
        p99=stats.p99,
    )


def _convert_concurrency_result(result) -> ConcurrencyResultSchema:
    """Convert ConcurrencyResult to schema."""
    goodput = None
    if result.goodput:
        goodput = GoodputResultSchema(
            satisfied_requests=result.goodput.satisfied_requests,
            total_requests=result.goodput.total_requests,
            goodput_percent=result.goodput.goodput_percent,
        )

    return ConcurrencyResultSchema(
        concurrency=result.concurrency,
        ttft=_convert_latency_stats(result.ttft),
        tpot=_convert_latency_stats(result.tpot) if result.tpot else None,
        e2e_latency=_convert_latency_stats(result.e2e_latency),
        throughput_tokens_per_sec=result.throughput_tokens_per_sec,
        request_rate_per_sec=result.request_rate_per_sec,
        total_requests=result.total_requests,
        successful_requests=result.successful_requests,
        failed_requests=result.failed_requests,
        error_rate_percent=result.error_rate_percent,
        goodput=goodput,
    )


async def _run_recommendation(run_id: str, request: RecommendRequest) -> None:
    """Background task to run infrastructure recommendation."""
    try:
        # Update status to running
        _recommend_runs[run_id]["status"] = "running"
        _recommend_runs[run_id]["started_at"] = datetime.now()

        # Create adapter
        server_adapter = AdapterFactory.create(
            name=request.adapter,
            server_url=request.server_url,
            model=request.model,
            api_key=request.api_key,
            timeout=request.timeout,
        )

        # Create load generator and recommender
        generator = LoadGenerator(server_adapter)
        recommender = InfraRecommender(generator)

        # Warmup
        if request.warmup > 0:
            await server_adapter.warmup(
                request.warmup,
                request.workload.avg_input_tokens // 4,
                request.workload.avg_output_tokens // 4,
            )

        # Get test config
        test_config = request.test_config
        concurrency_steps = test_config.concurrency_steps if test_config else [1, 10, 50, 100, 200]
        num_requests = test_config.num_requests_per_step if test_config else 50

        # Create workload spec
        workload = WorkloadSpec(
            daily_active_users=request.workload.daily_active_users,
            peak_concurrency=request.workload.peak_concurrency,
            requests_per_user_per_day=request.workload.requests_per_user_per_day,
            avg_input_tokens=request.workload.avg_input_tokens,
            avg_output_tokens=request.workload.avg_output_tokens,
            ttft_target_ms=request.workload.ttft_target_ms,
            tpot_target_ms=request.workload.tpot_target_ms,
            goodput_target_percent=request.workload.goodput_target_percent,
        )

        # Create config
        config = BenchmarkConfig(
            server_url=request.server_url,
            model=request.model,
            adapter=request.adapter,
            input_len=request.workload.avg_input_tokens,
            output_len=request.workload.avg_output_tokens,
            num_prompts=num_requests,
            concurrency=concurrency_steps,
            stream=request.stream,
            warmup=request.warmup,
            timeout=request.timeout,
            api_key=request.api_key,
        )

        # Run recommendation
        recommendation, benchmark_result = await recommender.recommend(
            config=config,
            workload=workload,
            concurrency_steps=concurrency_steps,
            num_requests_per_step=num_requests,
            headroom=request.headroom_percent / 100.0,
        )

        # Convert results to schema
        test_results = [
            _convert_concurrency_result(r) for r in benchmark_result.results
        ]

        # Store result
        _recommend_results[run_id] = {
            "run_id": run_id,
            "recommendation": InfraRecommendationSchema(
                model_name=recommendation.model_name,
                recommended_gpu=recommendation.recommended_gpu,
                recommended_count=recommendation.recommended_count,
                tensor_parallelism=recommendation.tensor_parallelism,
                estimated_max_concurrency=recommendation.estimated_max_concurrency,
                estimated_goodput=recommendation.estimated_goodput,
                estimated_throughput=recommendation.estimated_throughput,
                headroom_percent=recommendation.headroom_percent,
                calculation_formula=recommendation.calculation_formula,
                reasoning=recommendation.reasoning,
                estimated_monthly_cost_usd=recommendation.estimated_monthly_cost_usd,
            ),
            "current_infra": InfraProfileSchema(
                gpu_model=recommendation.current_infra.gpu_model,
                gpu_count=recommendation.current_infra.gpu_count,
                gpu_memory_gb=recommendation.current_infra.gpu_memory_gb,
                max_concurrency_at_slo=recommendation.current_infra.max_concurrency_at_slo,
                throughput_tokens_per_sec=recommendation.current_infra.throughput_tokens_per_sec,
                goodput_at_max_concurrency=recommendation.current_infra.goodput_at_max_concurrency,
                saturation_concurrency=recommendation.current_infra.saturation_concurrency,
                saturation_goodput=recommendation.current_infra.saturation_goodput,
            ),
            "workload": request.workload,
            "test_results": test_results,
            "started_at": _recommend_runs[run_id]["started_at"],
            "completed_at": datetime.now(),
            "duration_seconds": (datetime.now() - _recommend_runs[run_id]["started_at"]).total_seconds(),
        }

        # Update status
        _recommend_runs[run_id]["status"] = "completed"
        _recommend_runs[run_id]["completed_at"] = datetime.now()

        log_benchmark_event(
            "recommendation_completed",
            run_id=run_id,
            extra={
                "recommended_gpu": recommendation.recommended_gpu,
                "recommended_count": recommendation.recommended_count,
            },
        )

    except Exception as e:
        logger.error("recommendation_failed", run_id=run_id, error=str(e))
        _recommend_runs[run_id]["status"] = "failed"
        _recommend_runs[run_id]["error"] = str(e)

    finally:
        # Clean up task reference
        if run_id in _running_tasks:
            del _running_tasks[run_id]


@router.post("/recommend", response_model=dict, dependencies=[Depends(APIKeyAuth(required=True))])
async def start_recommendation(
    request: RecommendRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Start infrastructure recommendation analysis.

    Requires API key authentication via X-API-Key header.

    This endpoint profiles the target server by running load tests at multiple
    concurrency levels and recommends the number of GPUs needed to handle the
    specified workload with SLO requirements.

    Returns the run_id for tracking progress.
    """
    run_id = str(uuid.uuid4())

    logger.info(
        "recommendation_request_received",
        run_id=run_id,
        server_url=request.server_url,
        model=request.model,
        peak_concurrency=request.workload.peak_concurrency,
    )

    # Create run record
    _recommend_runs[run_id] = {
        "id": run_id,
        "status": "pending",
        "server_url": request.server_url,
        "model": request.model,
        "created_at": datetime.now(),
        "started_at": None,
        "completed_at": None,
        "error": None,
    }

    # Start background task
    task = asyncio.create_task(_run_recommendation(run_id, request))
    _running_tasks[run_id] = task

    log_benchmark_event(
        "recommendation_started",
        run_id=run_id,
        extra={
            "server_url": request.server_url,
            "model": request.model,
            "peak_concurrency": request.workload.peak_concurrency,
        },
    )

    return {"run_id": run_id, "status": "started"}


@router.get("/recommend/{run_id}", response_model=RecommendStatus)
async def get_recommendation_status(run_id: str) -> RecommendStatus:
    """Get recommendation run status."""
    run = _recommend_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Recommendation run not found")

    return RecommendStatus(
        run_id=run["id"],
        status=run["status"],
        server_url=run["server_url"],
        model=run["model"],
        created_at=run["created_at"],
        started_at=run.get("started_at"),
        completed_at=run.get("completed_at"),
        error=run.get("error"),
    )


@router.get("/recommend/{run_id}/result", response_model=RecommendResponse)
async def get_recommendation_result(run_id: str) -> RecommendResponse:
    """Get recommendation result."""
    result = _recommend_results.get(run_id)
    if not result:
        run = _recommend_runs.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Recommendation run not found")
        if run["status"] == "running":
            raise HTTPException(status_code=202, detail="Recommendation still running")
        if run["status"] == "failed":
            raise HTTPException(
                status_code=500,
                detail=f"Recommendation failed: {run.get('error', 'Unknown error')}",
            )
        raise HTTPException(status_code=404, detail="Result not found")

    return RecommendResponse(**result)


@router.delete("/recommend/{run_id}", dependencies=[Depends(APIKeyAuth(required=True))])
async def delete_recommendation(run_id: str) -> dict:
    """Delete a recommendation run.

    Requires API key authentication via X-API-Key header.

    If the run is still in progress, it will be cancelled.
    """
    if run_id not in _recommend_runs:
        raise HTTPException(status_code=404, detail="Recommendation run not found")

    # Cancel if running
    if run_id in _running_tasks:
        _running_tasks[run_id].cancel()
        del _running_tasks[run_id]

    # Delete records
    del _recommend_runs[run_id]
    if run_id in _recommend_results:
        del _recommend_results[run_id]

    logger.info("recommendation_deleted", run_id=run_id)

    return {"deleted": run_id}
