"""Benchmark API routes."""

import csv
import io
import json
from datetime import datetime
from typing import Literal, Optional

import httpx
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response, StreamingResponse

from llm_loadtest_api.auth import APIKeyAuth
from shared.database import Database
from llm_loadtest_api.logging_config import get_logger, log_benchmark_event
from llm_loadtest_api.services.benchmark_service import BenchmarkService
from llm_loadtest_api.models.schemas import (
    BenchmarkRequest,
    BenchmarkResponse,
    BenchmarkStatus,
    CompareRequest,
    CompareResponse,
    HealthResponse,
    RunListResponse,
)
from llm_loadtest_api import __version__

# GPU 모니터링
try:
    from shared.core.gpu_monitor import get_gpu_info
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    get_gpu_info = None

# Logger
logger = get_logger(__name__)


router = APIRouter(prefix="/api/v1/benchmark", tags=["benchmark"])

# Database and service instances (singleton pattern)
_db: Optional[Database] = None
_service: Optional[BenchmarkService] = None


def get_db() -> Database:
    """Get database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db


def get_service() -> BenchmarkService:
    """Get benchmark service instance."""
    global _service
    if _service is None:
        _service = BenchmarkService(get_db())
    return _service


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check API health."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        timestamp=datetime.now(),
    )


@router.post("/run", response_model=dict, dependencies=[Depends(APIKeyAuth(required=True))])
async def start_benchmark(
    request: BenchmarkRequest,
    service: BenchmarkService = Depends(get_service),
) -> dict:
    """Start a new benchmark run.

    Requires API key authentication via X-API-Key header.

    Returns the run_id for tracking progress.
    """
    logger.info(
        "benchmark_request_received",
        server_url=request.server_url,
        model=request.model,
        adapter=request.adapter,
    )

    run_id = await service.start_benchmark(request)

    log_benchmark_event(
        "benchmark_started",
        run_id=run_id,
        extra={
            "server_url": request.server_url,
            "model": request.model,
            "adapter": request.adapter,
        },
    )

    return {"run_id": run_id, "status": "started"}


@router.get("/run/{run_id}", response_model=BenchmarkStatus)
async def get_run_status(
    run_id: str,
    service: BenchmarkService = Depends(get_service),
) -> BenchmarkStatus:
    """Get benchmark run status."""
    run = service.get_status(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return BenchmarkStatus(
        run_id=run["id"],
        status=run["status"],
        server_url=run["server_url"],
        model=run["model"],
        adapter=run["adapter"],
        started_at=run.get("started_at"),
        completed_at=run.get("completed_at"),
        created_at=run["created_at"],
    )


@router.get("/result/{run_id}")
async def get_run_result(
    run_id: str,
    service: BenchmarkService = Depends(get_service),
) -> dict:
    """Get benchmark result."""
    result = service.get_result(run_id)
    if not result:
        # Check if run exists but not completed
        run = service.get_status(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] == "running":
            raise HTTPException(status_code=202, detail="Benchmark still running")
        if run["status"] == "failed":
            raise HTTPException(status_code=500, detail="Benchmark failed")
        raise HTTPException(status_code=404, detail="Result not found")

    # Add summary if not present
    if "summary" not in result and "results" in result:
        results = result["results"]
        if results:
            best_throughput = max(r["throughput_tokens_per_sec"] for r in results)
            best_ttft = min(r["ttft"]["p50"] for r in results)
            best_result = max(results, key=lambda r: r["throughput_tokens_per_sec"])
            total_requests = sum(r["total_requests"] for r in results)
            failed_requests = sum(r["failed_requests"] for r in results)

            result["summary"] = {
                "best_throughput": best_throughput,
                "best_ttft_p50": best_ttft,
                "best_concurrency": best_result["concurrency"],
                "total_requests": total_requests,
                "overall_error_rate": (failed_requests / total_requests * 100) if total_requests > 0 else 0,
            }

            # Add Goodput if available
            goodput_results = [r["goodput"] for r in results if r.get("goodput")]
            if goodput_results:
                avg_goodput = sum(g["goodput_percent"] for g in goodput_results) / len(goodput_results)
                result["summary"]["avg_goodput_percent"] = avg_goodput

    return result


@router.get("/history", response_model=RunListResponse)
async def list_runs(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    service: BenchmarkService = Depends(get_service),
) -> RunListResponse:
    """List benchmark runs."""
    runs = service.list_runs(limit, offset, status)

    return RunListResponse(
        runs=[
            BenchmarkStatus(
                run_id=r["id"],
                status=r["status"],
                server_url=r["server_url"],
                model=r["model"],
                adapter=r["adapter"],
                started_at=r.get("started_at"),
                completed_at=r.get("completed_at"),
                created_at=r["created_at"],
            )
            for r in runs
        ],
        total=len(runs),  # TODO: Get actual total count
        limit=limit,
        offset=offset,
    )


@router.delete("/run/{run_id}", dependencies=[Depends(APIKeyAuth(required=True))])
async def delete_run(
    run_id: str,
    service: BenchmarkService = Depends(get_service),
) -> dict:
    """Delete a benchmark run.

    Requires API key authentication via X-API-Key header.
    """
    logger.info("benchmark_delete_request", run_id=run_id)

    deleted = service.delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Run not found")

    log_benchmark_event("benchmark_deleted", run_id=run_id)

    return {"deleted": run_id}


@router.post("/compare")
async def compare_runs(
    request: CompareRequest,
    service: BenchmarkService = Depends(get_service),
) -> dict:
    """Compare multiple benchmark runs."""
    comparison = service.compare_runs(request.run_ids)
    return comparison


@router.get("/result/{run_id}/export")
async def export_result(
    run_id: str,
    format: Literal["csv", "xlsx"] = "csv",
    service: BenchmarkService = Depends(get_service),
) -> Response:
    """Export benchmark result to CSV or Excel format.

    Args:
        run_id: The benchmark run ID.
        format: Export format ('csv' or 'xlsx').

    Returns:
        File download response.
    """
    result = service.get_result(run_id)
    if not result:
        run = service.get_status(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] == "running":
            raise HTTPException(status_code=202, detail="Benchmark still running")
        if run["status"] == "failed":
            raise HTTPException(status_code=500, detail="Benchmark failed")
        raise HTTPException(status_code=404, detail="Result not found")

    if format == "csv":
        content = _export_to_csv(result)
        return Response(
            content=content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{run_id[:8]}_benchmark.csv"'
            },
        )
    else:
        content = _export_to_xlsx(result)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{run_id[:8]}_benchmark.xlsx"'
            },
        )


def _export_to_csv(result: dict) -> str:
    """Convert benchmark result to CSV format."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Metadata section
    writer.writerow(["# Benchmark Result Export"])
    writer.writerow(["Run ID", result.get("run_id", "N/A")])
    writer.writerow(["Model", result.get("model", "N/A")])
    writer.writerow(["Server URL", result.get("server_url", "N/A")])
    writer.writerow(["Adapter", result.get("adapter", "N/A")])
    writer.writerow(["Started At", result.get("started_at", "N/A")])
    writer.writerow(["Completed At", result.get("completed_at", "N/A")])
    writer.writerow(["Duration (s)", result.get("duration_seconds", "N/A")])
    writer.writerow([])

    # Summary section
    summary = result.get("summary", {})
    writer.writerow(["# Summary"])
    writer.writerow(["Best Throughput (tok/s)", summary.get("best_throughput", "N/A")])
    writer.writerow(["Best TTFT p50 (ms)", summary.get("best_ttft_p50", "N/A")])
    writer.writerow(["Best Concurrency", summary.get("best_concurrency", "N/A")])
    writer.writerow(["Total Requests", summary.get("total_requests", "N/A")])
    writer.writerow(["Overall Error Rate (%)", summary.get("overall_error_rate", "N/A")])
    if summary.get("avg_goodput_percent") is not None:
        writer.writerow(["Avg Goodput (%)", summary.get("avg_goodput_percent")])
    writer.writerow([])

    # Results table
    writer.writerow(["# Detailed Results by Concurrency"])
    writer.writerow([
        "Concurrency",
        "Throughput (tok/s)",
        "Request Rate (req/s)",
        "TTFT p50 (ms)",
        "TTFT p95 (ms)",
        "TTFT p99 (ms)",
        "TPOT p50 (ms)",
        "TPOT p95 (ms)",
        "TPOT p99 (ms)",
        "E2E p50 (ms)",
        "E2E p95 (ms)",
        "E2E p99 (ms)",
        "Total Requests",
        "Successful",
        "Failed",
        "Error Rate (%)",
        "Goodput (%)",
    ])

    for r in result.get("results", []):
        ttft = r.get("ttft", {})
        tpot = r.get("tpot", {})
        e2e = r.get("e2e_latency", {})
        goodput = r.get("goodput", {})

        writer.writerow([
            r.get("concurrency", "N/A"),
            f"{r.get('throughput_tokens_per_sec', 0):.2f}",
            f"{r.get('request_rate_per_sec', 0):.2f}",
            f"{ttft.get('p50', 0):.2f}",
            f"{ttft.get('p95', 0):.2f}",
            f"{ttft.get('p99', 0):.2f}",
            f"{tpot.get('p50', 0):.2f}" if tpot else "N/A",
            f"{tpot.get('p95', 0):.2f}" if tpot else "N/A",
            f"{tpot.get('p99', 0):.2f}" if tpot else "N/A",
            f"{e2e.get('p50', 0):.2f}",
            f"{e2e.get('p95', 0):.2f}",
            f"{e2e.get('p99', 0):.2f}",
            r.get("total_requests", 0),
            r.get("successful_requests", 0),
            r.get("failed_requests", 0),
            f"{r.get('error_rate_percent', 0):.2f}",
            f"{goodput.get('goodput_percent', 0):.2f}" if goodput else "N/A",
        ])

    return output.getvalue()


def _export_to_xlsx(result: dict) -> bytes:
    """Convert benchmark result to Excel format."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Excel export not available. Install openpyxl: pip install openpyxl",
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Benchmark Results"

    # Styles
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font_white = Font(bold=True, color="FFFFFF")

    row = 1

    # Metadata section
    ws.cell(row=row, column=1, value="Benchmark Result Export").font = Font(bold=True, size=14)
    row += 2

    metadata = [
        ("Run ID", result.get("run_id", "N/A")),
        ("Model", result.get("model", "N/A")),
        ("Server URL", result.get("server_url", "N/A")),
        ("Adapter", result.get("adapter", "N/A")),
        ("Started At", result.get("started_at", "N/A")),
        ("Completed At", result.get("completed_at", "N/A")),
        ("Duration (s)", result.get("duration_seconds", "N/A")),
    ]

    for label, value in metadata:
        ws.cell(row=row, column=1, value=label).font = header_font
        ws.cell(row=row, column=2, value=value)
        row += 1

    row += 1

    # Summary section
    ws.cell(row=row, column=1, value="Summary").font = Font(bold=True, size=12)
    row += 1

    summary = result.get("summary", {})
    summary_data = [
        ("Best Throughput (tok/s)", summary.get("best_throughput", "N/A")),
        ("Best TTFT p50 (ms)", summary.get("best_ttft_p50", "N/A")),
        ("Best Concurrency", summary.get("best_concurrency", "N/A")),
        ("Total Requests", summary.get("total_requests", "N/A")),
        ("Overall Error Rate (%)", summary.get("overall_error_rate", "N/A")),
    ]
    if summary.get("avg_goodput_percent") is not None:
        summary_data.append(("Avg Goodput (%)", summary.get("avg_goodput_percent")))

    for label, value in summary_data:
        ws.cell(row=row, column=1, value=label).font = header_font
        ws.cell(row=row, column=2, value=value)
        row += 1

    row += 2

    # Results table
    ws.cell(row=row, column=1, value="Detailed Results by Concurrency").font = Font(bold=True, size=12)
    row += 1

    headers = [
        "Concurrency", "Throughput", "Req Rate", "TTFT p50", "TTFT p95", "TTFT p99",
        "TPOT p50", "TPOT p95", "TPOT p99", "E2E p50", "E2E p95", "E2E p99",
        "Total", "Success", "Failed", "Error %", "Goodput %",
    ]

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    row += 1

    for r in result.get("results", []):
        ttft = r.get("ttft", {})
        tpot = r.get("tpot", {})
        e2e = r.get("e2e_latency", {})
        goodput = r.get("goodput", {})

        values = [
            r.get("concurrency", 0),
            round(r.get("throughput_tokens_per_sec", 0), 2),
            round(r.get("request_rate_per_sec", 0), 2),
            round(ttft.get("p50", 0), 2),
            round(ttft.get("p95", 0), 2),
            round(ttft.get("p99", 0), 2),
            round(tpot.get("p50", 0), 2) if tpot else None,
            round(tpot.get("p95", 0), 2) if tpot else None,
            round(tpot.get("p99", 0), 2) if tpot else None,
            round(e2e.get("p50", 0), 2),
            round(e2e.get("p95", 0), 2),
            round(e2e.get("p99", 0), 2),
            r.get("total_requests", 0),
            r.get("successful_requests", 0),
            r.get("failed_requests", 0),
            round(r.get("error_rate_percent", 0), 2),
            round(goodput.get("goodput_percent", 0), 2) if goodput else None,
        ]

        for col, value in enumerate(values, 1):
            ws.cell(row=row, column=col, value=value)
        row += 1

    # Adjust column widths
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[chr(64 + col)].width = 12

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


@router.get("/result/{run_id}/analysis")
async def analyze_result(
    run_id: str,
    server_url: str = Query(default="http://host.docker.internal:8000", description="vLLM server URL"),
    model: str = Query(default="", description="Model name (uses benchmark model if empty)"),
    service: BenchmarkService = Depends(get_service),
) -> StreamingResponse:
    """Generate AI analysis of benchmark results using vLLM.

    Streams the analysis response in real-time using Server-Sent Events (SSE).

    Args:
        run_id: The benchmark run ID.
        server_url: vLLM server URL for analysis generation.
        model: Model to use for analysis (defaults to benchmark's model).

    Returns:
        StreamingResponse with SSE format.
    """
    result = service.get_result(run_id)
    if not result:
        run = service.get_status(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] == "running":
            raise HTTPException(status_code=202, detail="Benchmark still running")
        if run["status"] == "failed":
            raise HTTPException(status_code=500, detail="Benchmark failed")
        raise HTTPException(status_code=404, detail="Result not found")

    # Use model from result if not specified
    analysis_model = model if model else result.get("model", "qwen3-14b")

    # Build analysis prompt
    prompt = _build_analysis_prompt(result)

    async def generate_analysis():
        """Stream analysis from vLLM."""
        # System prompt: /no_think로 thinking 모드 비활성화 시도
        # Qwen3 VL 모델은 </think> 태그로 thinking 종료
        system_prompt = """/no_think
당신은 LLM 서버 성능 분석 전문가입니다. 벤치마크 결과를 분석하여 마크다운 형식의 보고서를 작성합니다.

[답변 원칙]
- 한국어로 답변
- 전문 용어는 괄호 안에 간단한 설명 추가 (예: TTFT(첫 토큰 응답 시간))
- 구조화된 마크다운 형식 사용
- 핵심부터 설명, 불필요한 서론 생략"""

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, read=300.0)) as client:
                async with client.stream(
                    "POST",
                    f"{server_url}/v1/chat/completions",
                    json={
                        "model": analysis_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": system_prompt
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "stream": True,
                        "max_tokens": 8192,
                        "temperature": 0.3,
                    },
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield f"data: {json.dumps({'error': f'vLLM error: {error_text.decode()}'})}\n\n"
                        return

                    # Thinking 모델 대응: </think> 태그가 나오면 그 이후만 출력
                    # Qwen3-VL 특성: <think> 시작 없이 thinking 시작, </think>로 종료
                    buffer = ""
                    report_started = False
                    think_end_tag = "</think>"

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                # 버퍼에 남은 내용이 있으면 출력 (thinking이 없었던 경우)
                                if buffer and not report_started:
                                    yield f"data: {json.dumps({'content': buffer})}\n\n"
                                yield "data: [DONE]\n\n"
                                break
                            try:
                                chunk = json.loads(data)
                                content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if content:
                                    if report_started:
                                        # 보고서 시작된 후에는 바로 출력
                                        yield f"data: {json.dumps({'content': content})}\n\n"
                                    else:
                                        # 버퍼에 축적
                                        buffer += content
                                        # </think> 태그가 나오면 보고서 시작
                                        if think_end_tag in buffer:
                                            # </think> 이후 내용만 추출
                                            idx = buffer.find(think_end_tag)
                                            remaining = buffer[idx + len(think_end_tag):].lstrip()
                                            report_started = True
                                            if remaining:
                                                yield f"data: {json.dumps({'content': remaining})}\n\n"
                                            buffer = ""
                                        # /no_think이 작동하면 바로 마크다운으로 시작할 수 있음
                                        elif buffer.lstrip().startswith("#") and len(buffer) > 50:
                                            # thinking 없이 바로 보고서 시작
                                            report_started = True
                                            yield f"data: {json.dumps({'content': buffer.lstrip()})}\n\n"
                                            buffer = ""
                            except json.JSONDecodeError:
                                continue
        except httpx.ConnectError:
            yield f"data: {json.dumps({'error': f'vLLM 서버에 연결할 수 없습니다: {server_url}'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_analysis(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _build_analysis_prompt(result: dict) -> str:
    """Build analysis prompt from benchmark result."""
    model = result.get("model", "Unknown")
    server_url = result.get("server_url", "Unknown")
    duration = result.get("duration_seconds", 0)
    results = result.get("results", [])

    # GPU 인프라 정보 수집
    gpu_info_section = ""
    if GPU_AVAILABLE and get_gpu_info:
        try:
            gpu_result = get_gpu_info()
            if gpu_result.available and gpu_result.metrics:
                gpu_lines = []
                for gpu in gpu_result.metrics:
                    gpu_lines.append(
                        f"  - **GPU {gpu.gpu_index}**: {gpu.device_name} "
                        f"({gpu.memory_total_gb:.1f}GB VRAM, "
                        f"현재 {gpu.memory_used_gb:.1f}GB 사용 중)"
                    )
                gpu_list_str = "\n".join(gpu_lines)
                gpu_info_section = f"""
## 서버 인프라 (자동 감지)
- **GPU 수**: {gpu_result.gpu_count}장
{gpu_list_str}

> 위 인프라 환경을 고려하여 분석해주세요. 특히 GPU 메모리와 처리량 간의 관계를 분석하세요.
"""
        except Exception as e:
            logger.warning(f"GPU 정보 수집 실패: {e}")

    # 테이블 데이터에서 직접 요약 통계 계산 (summary 필드가 없거나 0인 경우 대비)
    best_throughput = 0.0
    best_ttft_p50 = float('inf')
    best_concurrency = None
    total_errors = 0
    total_requests = 0
    goodput_values = []

    for r in results:
        throughput = r.get('throughput_tokens_per_sec', 0) or 0
        if throughput > best_throughput:
            best_throughput = throughput
            best_concurrency = r.get('concurrency', 0)

        ttft = r.get("ttft") or {}
        ttft_p50 = ttft.get('p50', 0) or 0
        if ttft_p50 > 0 and ttft_p50 < best_ttft_p50:
            best_ttft_p50 = ttft_p50

        total_requests += r.get('total_requests', 0) or 0
        total_errors += r.get('error_count', 0) or 0

        goodput = r.get("goodput") or {}
        if goodput and 'goodput_percent' in goodput:
            goodput_values.append(goodput['goodput_percent'])

    # 계산된 값으로 요약
    overall_error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
    avg_goodput = sum(goodput_values) / len(goodput_values) if goodput_values else None
    if best_ttft_p50 == float('inf'):
        best_ttft_p50 = 0

    # Build concurrency results table
    results_table = "| Concurrency | Throughput (tok/s) | TTFT p50 (ms) | TTFT p99 (ms) | Error Rate (%) | Goodput (%) |\n"
    results_table += "|-------------|-------------------|---------------|---------------|----------------|-------------|\n"

    for r in results:
        ttft = r.get("ttft") or {}
        goodput = r.get("goodput") or {}
        goodput_str = f"{goodput.get('goodput_percent', 0):.1f}" if goodput else "N/A"
        results_table += f"| {r.get('concurrency', 0)} | {r.get('throughput_tokens_per_sec', 0):.1f} | {ttft.get('p50', 0):.1f} | {ttft.get('p99', 0):.1f} | {r.get('error_rate_percent', 0):.2f} | {goodput_str} |\n"

    # 요약 문자열 생성
    goodput_summary = f"{avg_goodput:.1f}%" if avg_goodput is not None else "N/A"
    concurrency_summary = best_concurrency if best_concurrency else "N/A"

    prompt = f"""다음 LLM 서버 벤치마크 결과를 분석해주세요.

## 테스트 환경
- **모델**: {model}
- **서버**: {server_url}
- **테스트 시간**: {duration:.1f}초
{gpu_info_section}
## 성능 요약 (테이블 기반 계산)
- **최고 처리량**: {best_throughput:.1f} tok/s (동시성 {concurrency_summary}에서)
- **최저 TTFT p50**: {best_ttft_p50:.1f} ms
- **전체 에러율**: {overall_error_rate:.2f}%
- **평균 Goodput**: {goodput_summary}

## Concurrency별 상세 결과
{results_table}

## 분석 요청
위 벤치마크 결과를 분석하여 **전문가 보고서**를 작성해주세요.

**[용어 설명 규칙]**
- 전문 용어는 처음 사용 시 괄호 안에 간단한 설명 추가
- 예: "TTFT(첫 토큰 응답 시간, Time To First Token)"
- 예: "Throughput(처리량, 초당 처리 토큰 수)"
- 예: "Goodput(유효 처리량, SLA 기준을 충족하는 요청 비율)"

**[분석 항목]**

# 1. 성능 개요
전반적인 서버 성능을 요약하세요.

# 2. Concurrency 영향 분석
동시성(동시 요청 수) 증가에 따른 성능 변화 패턴을 분석하세요. 표 데이터를 기반으로 구체적인 수치를 인용하세요.

# 3. 병목 지점 식별
성능이 저하되기 시작하는 동시성 레벨과 그 원인을 추정하세요.

# 4. TTFT vs Throughput 트레이드오프
응답 시간과 처리량 간의 관계를 분석하세요. 낮은 지연시간과 높은 처리량 사이의 균형점을 찾으세요.

# 5. 권장 운영 동시성
실제 서비스에서 권장하는 최적 동시성 레벨과 그 이유를 제시하세요.

# 6. 개선 제안
성능 향상을 위한 구체적인 제안을 해주세요. 인프라, 모델, 설정 측면에서 실행 가능한 조치를 포함하세요.

각 항목을 **마크다운 헤딩(#)으로 구분**하여 작성해주세요."""

    return prompt
