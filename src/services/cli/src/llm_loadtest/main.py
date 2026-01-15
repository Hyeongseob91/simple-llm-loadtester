"""LLM Loadtest CLI - Main entry point."""

import sys
from pathlib import Path
from typing import Optional

import typer

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from llm_loadtest import __version__
from llm_loadtest.commands.run import run_command
from llm_loadtest.commands.info import info_command
from llm_loadtest.commands.gpu import gpu_command
from llm_loadtest.commands.recommend import recommend_command

app = typer.Typer(
    name="llm-loadtest",
    help="LLM server load testing tool",
    add_completion=False,
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(f"llm-loadtest version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """LLM Loadtest - Server load testing tool for LLM inference.

    Test your LLM server's performance under various concurrency levels.
    Supports vLLM, SGLang, Ollama, and other OpenAI-compatible servers.

    Examples:

        # Basic load test
        llm-loadtest run --server http://localhost:8000 --model qwen3-14b

        # Test with multiple concurrency levels
        llm-loadtest run --server http://localhost:8000 --model qwen3-14b \\
            --concurrency 1,10,50,100 --num-prompts 100

        # With Goodput measurement
        llm-loadtest run --server http://localhost:8000 --model qwen3-14b \\
            --goodput ttft:500,tpot:50

        # Save results to JSON
        llm-loadtest run --server http://localhost:8000 --model qwen3-14b \\
            --output results.json
    """
    pass


# Register commands
app.command("run", help="Run load test against an LLM server")(run_command)
app.command("info", help="Show system information")(info_command)
app.command("gpu", help="Show GPU status")(gpu_command)
app.command("recommend", help="Recommend GPU infrastructure for target workload")(recommend_command)


if __name__ == "__main__":
    app()
