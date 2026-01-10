"""Run command for load testing."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from core.load_generator import LoadGenerator
from core.models import BenchmarkConfig, GoodputThresholds
from adapters.base import AdapterFactory
from adapters.openai_compat import OpenAICompatibleAdapter  # Registers the adapter


def parse_concurrency(value: str) -> list[int]:
    """Parse concurrency string like '1,10,50,100' into list of ints."""
    return [int(x.strip()) for x in value.split(",")]


def parse_goodput(value: Optional[str]) -> Optional[GoodputThresholds]:
    """Parse goodput string like 'ttft:500,tpot:50,e2e:3000' into thresholds."""
    if not value:
        return None

    thresholds = GoodputThresholds()
    for part in value.split(","):
        key, val = part.split(":")
        key = key.strip().lower()
        val = float(val.strip())

        if key == "ttft":
            thresholds.ttft_ms = val
        elif key == "tpot":
            thresholds.tpot_ms = val
        elif key == "e2e":
            thresholds.e2e_ms = val

    return thresholds


def print_progress(current: int, total: int, message: Optional[str] = None) -> None:
    """Print simple progress bar."""
    if total == 0:
        return

    percent = current / total * 100
    bar_length = 30
    filled = int(bar_length * current / total)
    bar = "█" * filled + "░" * (bar_length - filled)

    status = f" ({message})" if message else ""
    print(f"\r[llm-loadtest] [{bar}] {percent:5.1f}% ({current}/{total}){status}", end="", flush=True)


def run_command(
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
    concurrency: str = typer.Option(
        "1",
        "--concurrency", "-c",
        help="Concurrency levels (comma-separated, e.g., 1,10,50,100)",
    ),
    num_prompts: int = typer.Option(
        100,
        "--num-prompts", "-n",
        help="Number of prompts to send per concurrency level",
    ),
    input_len: int = typer.Option(
        256,
        "--input-len",
        help="Approximate input token length",
    ),
    output_len: int = typer.Option(
        128,
        "--output-len",
        help="Maximum output token length",
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
    goodput: Optional[str] = typer.Option(
        None,
        "--goodput",
        help="Goodput SLO thresholds (e.g., ttft:500,tpot:50,e2e:3000)",
    ),
    duration: Optional[int] = typer.Option(
        None,
        "--duration", "-d",
        help="Test duration in seconds (alternative to --num-prompts)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output file path (JSON)",
    ),
) -> None:
    """Run load test against an LLM server.

    Examples:

        # Basic test
        llm-loadtest run --server http://localhost:8000 --model qwen3-14b

        # Multiple concurrency levels
        llm-loadtest run -s http://localhost:8000 -m qwen3-14b -c 1,10,50 -n 100

        # With Goodput measurement
        llm-loadtest run -s http://localhost:8000 -m qwen3-14b --goodput ttft:500,tpot:50

        # Duration-based test
        llm-loadtest run -s http://localhost:8000 -m qwen3-14b -c 50 --duration 60
    """
    print(f"[llm-loadtest] Starting load test...")
    print(f"[llm-loadtest] Server: {server}")
    print(f"[llm-loadtest] Model: {model}")
    print(f"[llm-loadtest] Adapter: {adapter}")

    # Parse options
    concurrency_levels = parse_concurrency(concurrency)
    goodput_thresholds = parse_goodput(goodput)

    print(f"[llm-loadtest] Concurrency levels: {concurrency_levels}")

    if duration:
        print(f"[llm-loadtest] Duration: {duration}s per concurrency level")
    else:
        print(f"[llm-loadtest] Prompts: {num_prompts} per concurrency level")

    if goodput_thresholds:
        thresholds_str = []
        if goodput_thresholds.ttft_ms:
            thresholds_str.append(f"TTFT<{goodput_thresholds.ttft_ms}ms")
        if goodput_thresholds.tpot_ms:
            thresholds_str.append(f"TPOT<{goodput_thresholds.tpot_ms}ms")
        if goodput_thresholds.e2e_ms:
            thresholds_str.append(f"E2E<{goodput_thresholds.e2e_ms}ms")
        print(f"[llm-loadtest] Goodput SLOs: {', '.join(thresholds_str)}")

    # Create config
    config = BenchmarkConfig(
        server_url=server,
        model=model,
        adapter=adapter,
        input_len=input_len,
        output_len=output_len,
        num_prompts=num_prompts,
        concurrency=concurrency_levels,
        stream=stream,
        warmup=warmup,
        timeout=timeout,
        api_key=api_key,
        duration_seconds=duration,
        goodput_thresholds=goodput_thresholds,
    )

    # Create adapter and run
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

    async def run_test():
        generator = LoadGenerator(server_adapter)

        # Health check
        print(f"[llm-loadtest] Checking server health...")
        healthy = await server_adapter.health_check()
        if not healthy:
            print(f"[llm-loadtest] Warning: Server health check failed, proceeding anyway...")

        # Warmup
        if warmup > 0:
            print(f"[llm-loadtest] Running {warmup} warmup requests...")
            await server_adapter.warmup(warmup, input_len // 4, output_len // 4)

        # Run benchmark
        print(f"[llm-loadtest] Running load test...")
        result = await generator.run(config, progress_callback=print_progress)
        print()  # New line after progress bar

        return result

    # Run async
    result = asyncio.run(run_test())

    # Save result
    if output:
        output_path = Path(output)
        with open(output_path, "w") as f:
            json.dump(result.model_dump(mode="json"), f, indent=2, default=str)
        print(f"[llm-loadtest] Results saved to: {output_path}")
    else:
        # Generate default filename
        default_output = Path(f"loadtest_{result.run_id[:8]}.json")
        with open(default_output, "w") as f:
            json.dump(result.model_dump(mode="json"), f, indent=2, default=str)
        print(f"[llm-loadtest] Results saved to: {default_output}")

    # Print brief summary
    summary = result.get_summary()
    print(f"[llm-loadtest] ─────────────────────────────────────────")
    print(f"[llm-loadtest] Summary:")
    print(f"[llm-loadtest]   Best throughput: {summary.get('best_throughput', 0):.1f} tokens/s")
    print(f"[llm-loadtest]   Best TTFT (p50): {summary.get('best_ttft_p50', 0):.1f} ms")
    print(f"[llm-loadtest]   Best concurrency: {summary.get('best_concurrency', 0)}")
    print(f"[llm-loadtest]   Total requests: {summary.get('total_requests', 0)}")
    print(f"[llm-loadtest]   Error rate: {summary.get('overall_error_rate', 0):.2f}%")

    if "avg_goodput_percent" in summary:
        print(f"[llm-loadtest]   Avg Goodput: {summary['avg_goodput_percent']:.1f}%")

    print(f"[llm-loadtest] ─────────────────────────────────────────")
