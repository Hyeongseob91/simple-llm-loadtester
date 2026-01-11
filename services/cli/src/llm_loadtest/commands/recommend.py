"""Recommend command for infrastructure recommendation."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from shared.core.load_generator import LoadGenerator
from shared.core.models import BenchmarkConfig, WorkloadSpec
from shared.core.recommend import InfraRecommender
from shared.adapters.base import AdapterFactory
from shared.adapters.openai_compat import OpenAICompatibleAdapter  # Registers the adapter


def parse_concurrency_steps(value: str) -> list[int]:
    """Parse concurrency steps string like '1,10,50,100,200' into list of ints."""
    return [int(x.strip()) for x in value.split(",")]


def print_progress(stage: str, current: int, total: int) -> None:
    """Print progress for recommendation process."""
    if total == 0:
        print(f"\r[llm-loadtest] {stage}...", end="", flush=True)
        return

    percent = current / total * 100 if total > 0 else 0
    bar_length = 20
    filled = int(bar_length * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (bar_length - filled)

    print(f"\r[llm-loadtest] {stage} [{bar}] {percent:5.1f}%", end="", flush=True)


def recommend_command(
    server: str = typer.Option(
        ...,
        "--server", "-s",
        help="Server URL (e.g., http://localhost:8000)",
    ),
    model: str = typer.Option(
        ...,
        "--model", "-m",
        help="Model name",
    ),
    peak_concurrency: int = typer.Option(
        ...,
        "--peak-concurrency", "-p",
        help="Target peak concurrent users",
    ),
    ttft_target: float = typer.Option(
        500.0,
        "--ttft-target",
        help="TTFT target in milliseconds (default: 500)",
    ),
    tpot_target: float = typer.Option(
        50.0,
        "--tpot-target",
        help="TPOT target in milliseconds (default: 50)",
    ),
    goodput_target: float = typer.Option(
        95.0,
        "--goodput-target",
        help="Goodput target percentage (default: 95)",
    ),
    headroom: float = typer.Option(
        20.0,
        "--headroom",
        help="Safety headroom percentage (default: 20)",
    ),
    concurrency_steps: str = typer.Option(
        "1,10,50,100,200",
        "--concurrency-steps",
        help="Concurrency levels to test (comma-separated)",
    ),
    num_requests: int = typer.Option(
        50,
        "--num-requests", "-n",
        help="Number of requests per concurrency level",
    ),
    input_len: int = typer.Option(
        256,
        "--input-len",
        help="Average input token length",
    ),
    output_len: int = typer.Option(
        512,
        "--output-len",
        help="Average output token length",
    ),
    stream: bool = typer.Option(
        True,
        "--stream/--no-stream",
        help="Enable streaming mode",
    ),
    warmup: int = typer.Option(
        3,
        "--warmup",
        help="Number of warmup requests",
    ),
    timeout: float = typer.Option(
        120.0,
        "--timeout",
        help="Request timeout in seconds",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="API key for authentication",
        envvar="LLM_API_KEY",
    ),
    adapter: str = typer.Option(
        "openai",
        "--adapter",
        help="Server adapter (openai, triton, trtllm)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (JSON)",
    ),
) -> None:
    """Recommend GPU infrastructure for target workload.

    This command profiles the current server infrastructure and recommends
    the number of GPUs needed to handle the target concurrent users with
    the specified SLO requirements.

    Examples:

        # Basic recommendation
        llm-loadtest recommend -s http://localhost:8000 -m qwen3-14b -p 500

        # With custom SLO targets
        llm-loadtest recommend -s http://localhost:8000 -m qwen3-14b -p 500 \\
            --ttft-target 500 --goodput-target 95

        # With custom concurrency test steps
        llm-loadtest recommend -s http://localhost:8000 -m qwen3-14b -p 500 \\
            --concurrency-steps 1,10,50,100,200,300

        # Save results
        llm-loadtest recommend -s http://localhost:8000 -m qwen3-14b -p 500 \\
            -o recommendation.json
    """
    print("╭─────────────────────────────────────────────────────────────╮")
    print("│           Infrastructure Recommendation                     │")
    print("╰─────────────────────────────────────────────────────────────╯")
    print()
    print(f"[llm-loadtest] Server: {server}")
    print(f"[llm-loadtest] Model: {model}")
    print(f"[llm-loadtest] Adapter: {adapter}")
    print()
    print(f"[llm-loadtest] Target Workload:")
    print(f"[llm-loadtest]   Peak Concurrency: {peak_concurrency} users")
    print(f"[llm-loadtest]   TTFT Target: < {ttft_target} ms")
    print(f"[llm-loadtest]   TPOT Target: < {tpot_target} ms")
    print(f"[llm-loadtest]   Goodput Target: > {goodput_target}%")
    print(f"[llm-loadtest]   Headroom: {headroom}%")
    print()

    # Parse concurrency steps
    steps = parse_concurrency_steps(concurrency_steps)
    print(f"[llm-loadtest] Test concurrency levels: {steps}")
    print(f"[llm-loadtest] Requests per level: {num_requests}")
    print()

    # Create workload spec
    workload = WorkloadSpec(
        peak_concurrency=peak_concurrency,
        avg_input_tokens=input_len,
        avg_output_tokens=output_len,
        ttft_target_ms=ttft_target,
        tpot_target_ms=tpot_target,
        goodput_target_percent=goodput_target,
    )

    # Create base config
    config = BenchmarkConfig(
        server_url=server,
        model=model,
        adapter=adapter,
        input_len=input_len,
        output_len=output_len,
        num_prompts=num_requests,
        concurrency=steps,
        stream=stream,
        warmup=warmup,
        timeout=timeout,
        api_key=api_key,
    )

    # Create adapter
    try:
        server_adapter = AdapterFactory.create(
            name=adapter,
            server_url=server,
            model=model,
            api_key=api_key,
            timeout=timeout,
        )
    except ValueError as e:
        print(f"[llm-loadtest] Error: {e}")
        raise typer.Exit(1)

    async def run_recommendation():
        generator = LoadGenerator(server_adapter)
        recommender = InfraRecommender(generator)

        # Health check
        print("[llm-loadtest] Checking server health...")
        healthy = await server_adapter.health_check()
        if not healthy:
            print("[llm-loadtest] Warning: Server health check failed, proceeding anyway...")

        # Warmup
        if warmup > 0:
            print(f"[llm-loadtest] Running {warmup} warmup requests...")
            await server_adapter.warmup(warmup, input_len // 4, output_len // 4)

        # Run recommendation
        print("[llm-loadtest] Starting infrastructure profiling...")
        print()

        recommendation, benchmark_result = await recommender.recommend(
            config=config,
            workload=workload,
            concurrency_steps=steps,
            num_requests_per_step=num_requests,
            headroom=headroom / 100.0,  # Convert percentage to decimal
            progress_callback=print_progress,
        )

        print()  # New line after progress
        return recommendation, benchmark_result

    # Run async
    recommendation, benchmark_result = asyncio.run(run_recommendation())

    # Print recommendation result
    print()
    print("╔═════════════════════════════════════════════════════════════╗")
    print("║                     RECOMMENDATION                          ║")
    print("╠═════════════════════════════════════════════════════════════╣")
    print("║                                                             ║")
    print(f"║   {recommendation.recommended_gpu:^20} x {recommendation.recommended_count:<3}장                   ║")
    print("║                                                             ║")
    print("╚═════════════════════════════════════════════════════════════╝")
    print()

    # Current infrastructure
    profile = recommendation.current_infra
    print("┌─────────────────────────────────────────────────────────────┐")
    print("│ CURRENT INFRASTRUCTURE                                      │")
    print("├─────────────────────────────────────────────────────────────┤")
    print(f"│ GPU               : {profile.gpu_model:<39} │")
    print(f"│ GPU Count         : {profile.gpu_count:<39} │")
    print(f"│ GPU Memory        : {profile.gpu_memory_gb:.1f} GB{'':<33} │")
    print(f"│ Max Concurrency   : {profile.max_concurrency_at_slo} (at {profile.goodput_at_max_concurrency:.1f}% Goodput){'':<16} │")
    print(f"│ Throughput        : {profile.throughput_tokens_per_sec:.1f} tokens/s{'':<25} │")
    print(f"│ Saturation Point  : {profile.saturation_concurrency} concurrent{'':<25} │")
    print("└─────────────────────────────────────────────────────────────┘")
    print()

    # Estimated performance
    print("┌─────────────────────────────────────────────────────────────┐")
    print("│ ESTIMATED PERFORMANCE                                       │")
    print("├─────────────────────────────────────────────────────────────┤")
    print(f"│ Max Concurrency   : {recommendation.estimated_max_concurrency} users{'':<29} │")
    print(f"│ Estimated Goodput : {recommendation.estimated_goodput:.1f}%{'':<34} │")
    print(f"│ Throughput        : {recommendation.estimated_throughput:.1f} tokens/s{'':<25} │")
    print(f"│ Tensor Parallelism: {recommendation.tensor_parallelism}{'':<38} │")
    print(f"│ Headroom          : {recommendation.headroom_percent:.0f}%{'':<35} │")
    print("└─────────────────────────────────────────────────────────────┘")
    print()

    # Calculation
    print("┌─────────────────────────────────────────────────────────────┐")
    print("│ CALCULATION                                                 │")
    print("├─────────────────────────────────────────────────────────────┤")
    formula = recommendation.calculation_formula
    print(f"│ Formula: {formula:<50} │")
    print("├─────────────────────────────────────────────────────────────┤")
    print("│ Reasoning:                                                  │")

    # Word wrap reasoning
    reasoning = recommendation.reasoning
    max_line_len = 57
    words = reasoning.split()
    line = ""
    for word in words:
        if len(line) + len(word) + 1 <= max_line_len:
            line = f"{line} {word}" if line else word
        else:
            print(f"│ {line:<57} │")
            line = word
    if line:
        print(f"│ {line:<57} │")

    print("└─────────────────────────────────────────────────────────────┘")
    print()

    # Save results
    output_data = {
        "recommendation": recommendation.model_dump(mode="json"),
        "benchmark_result": benchmark_result.model_dump(mode="json"),
    }

    if output:
        output_path = Path(output)
    else:
        output_path = Path(f"recommendation_{benchmark_result.run_id[:8]}.json")

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2, default=str)

    print(f"[llm-loadtest] Results saved to: {output_path}")
    print()
