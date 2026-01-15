"""Docker log collection and parsing for vLLM validation."""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional

from .models import DockerLogMetrics, DockerLogValidation, MetricComparison

logger = logging.getLogger(__name__)


class DockerLogCollector:
    """Collects and parses Docker container logs for validation."""

    # Regex patterns for vLLM log parsing
    HTTP_REQUEST_PATTERN = re.compile(
        r'"(POST|GET) /v1/(?:chat/completions|completions|embeddings)[^"]*" (\d{3})'
    )
    ENGINE_STATS_PATTERN = re.compile(
        r"Engine \d+: "
        r"Avg prompt throughput: ([\d.]+) tokens/s, "
        r"Avg generation throughput: ([\d.]+) tokens/s, "
        r"Running: (\d+) reqs, "
        r"Waiting: (\d+) reqs, "
        r"GPU KV cache usage: ([\d.]+)%"
        r"(?:, Prefix cache hit rate: ([\d.]+)%)?"
    )
    ERROR_PATTERN = re.compile(r"^.*\bERROR\b.*$", re.MULTILINE)
    WARNING_PATTERN = re.compile(r"^.*\bWARNING\b.*$", re.MULTILINE)

    def __init__(self, container_name: str, timeout: float = 10.0):
        """
        Initialize Docker log collector.

        Args:
            container_name: Docker container name or ID
            timeout: Command timeout in seconds
        """
        self.container_name = container_name
        self.timeout = timeout
        self.start_timestamp: Optional[datetime] = None
        self._docker_available: Optional[bool] = None

    async def check_docker_available(self) -> bool:
        """Check if Docker is available and container exists."""
        if self._docker_available is not None:
            return self._docker_available

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "ps", "-q", "-f", f"name={self.container_name}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            self._docker_available = bool(stdout.strip())

            if not self._docker_available:
                logger.warning(f"Container '{self.container_name}' not found or not running")

            return self._docker_available
        except FileNotFoundError:
            logger.warning("Docker command not found")
            self._docker_available = False
            return False
        except asyncio.TimeoutError:
            logger.warning("Docker command timed out")
            self._docker_available = False
            return False
        except Exception as e:
            logger.warning(f"Failed to check Docker: {e}")
            self._docker_available = False
            return False

    async def collect_before(self) -> bool:
        """
        Record timestamp before test starts.

        Returns:
            True if Docker is available, False otherwise
        """
        if not await self.check_docker_available():
            return False

        self.start_timestamp = datetime.utcnow()
        logger.info(f"Docker log collection started at {self.start_timestamp.isoformat()}")
        return True

    async def collect_after(self) -> Optional[DockerLogMetrics]:
        """
        Collect and parse logs after test completes.

        Returns:
            DockerLogMetrics if successful, None otherwise
        """
        if not await self.check_docker_available():
            return None

        if self.start_timestamp is None:
            logger.warning("collect_before() was not called, using last 5 minutes of logs")
            since_arg = "5m"
        else:
            since_arg = self.start_timestamp.strftime("%Y-%m-%dT%H:%M:%S")

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "logs", "--since", since_arg, self.container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            logs = stdout.decode("utf-8", errors="replace")

            end_time = datetime.utcnow()
            metrics = self._parse_logs(logs)
            metrics.log_start_time = self.start_timestamp
            metrics.log_end_time = end_time
            metrics.container_name = self.container_name

            logger.info(
                f"Docker logs collected: {metrics.total_log_lines} lines, "
                f"{metrics.http_200_count} HTTP 200, {metrics.http_error_count} errors"
            )
            return metrics

        except asyncio.TimeoutError:
            logger.warning(f"Docker logs collection timed out after {self.timeout}s")
            return None
        except Exception as e:
            logger.warning(f"Failed to collect Docker logs: {e}")
            return None

    def _parse_logs(self, logs: str) -> DockerLogMetrics:
        """Parse vLLM Docker logs and extract metrics."""
        metrics = DockerLogMetrics()
        lines = logs.splitlines()
        metrics.total_log_lines = len(lines)

        prompt_throughputs: list[float] = []
        generation_throughputs: list[float] = []
        running_reqs: list[int] = []
        waiting_reqs: list[int] = []
        kv_cache_usages: list[float] = []
        prefix_hit_rates: list[float] = []

        for line in lines:
            # Parse HTTP requests
            http_match = self.HTTP_REQUEST_PATTERN.search(line)
            if http_match:
                status_code = int(http_match.group(2))
                if 200 <= status_code < 300:
                    metrics.http_200_count += 1
                elif status_code >= 400:
                    metrics.http_error_count += 1

            # Parse Engine statistics
            engine_match = self.ENGINE_STATS_PATTERN.search(line)
            if engine_match:
                prompt_throughputs.append(float(engine_match.group(1)))
                generation_throughputs.append(float(engine_match.group(2)))
                running_reqs.append(int(engine_match.group(3)))
                waiting_reqs.append(int(engine_match.group(4)))
                kv_cache_usages.append(float(engine_match.group(5)))
                if engine_match.group(6):
                    prefix_hit_rates.append(float(engine_match.group(6)))

            # Parse ERROR logs
            if self.ERROR_PATTERN.search(line):
                metrics.error_messages.append(line.strip()[:500])

            # Parse WARNING logs
            if self.WARNING_PATTERN.search(line):
                metrics.warning_messages.append(line.strip()[:500])

        # Calculate averages
        if prompt_throughputs:
            metrics.avg_prompt_throughput = sum(prompt_throughputs) / len(prompt_throughputs)
        if generation_throughputs:
            metrics.avg_generation_throughput = sum(generation_throughputs) / len(generation_throughputs)
        if running_reqs:
            metrics.avg_running_reqs = sum(running_reqs) / len(running_reqs)
        if waiting_reqs:
            metrics.avg_waiting_reqs = sum(waiting_reqs) / len(waiting_reqs)
        if kv_cache_usages:
            metrics.peak_kv_cache_usage = max(kv_cache_usages)
        if prefix_hit_rates:
            metrics.prefix_cache_hit_rate = sum(prefix_hit_rates) / len(prefix_hit_rates)

        return metrics


def calc_diff_percent(client: float, server: float) -> float:
    """Calculate percentage difference."""
    if server == 0:
        return 0.0 if client == 0 else 100.0
    return abs(client - server) / server * 100


def is_within_tolerance(client: float, server: float, tolerance: float = 0.05) -> bool:
    """Check if values are within tolerance."""
    if server == 0:
        return client == 0
    diff_percent = abs(client - server) / server
    return diff_percent <= tolerance


def validate_docker_logs(
    client_requests: int,
    client_throughput: float,
    docker_metrics: DockerLogMetrics,
    request_tolerance: float = 0.05,
    throughput_tolerance: float = 0.10,
) -> DockerLogValidation:
    """
    Validate client metrics against Docker log metrics.

    Args:
        client_requests: Total requests from client
        client_throughput: Throughput measured by client (tokens/s)
        docker_metrics: Metrics parsed from Docker logs
        request_tolerance: Tolerance for request count (default 5%)
        throughput_tolerance: Tolerance for throughput (default 10%)

    Returns:
        DockerLogValidation result
    """
    comparisons: list[MetricComparison] = []
    warnings: list[str] = []

    # 1. HTTP request count comparison
    http_match = is_within_tolerance(
        client_requests,
        docker_metrics.http_200_count,
        tolerance=request_tolerance,
    )
    comparisons.append(MetricComparison(
        metric_name="HTTP 200 Count",
        client_value=float(client_requests),
        server_value=float(docker_metrics.http_200_count),
        difference_percent=calc_diff_percent(client_requests, docker_metrics.http_200_count),
        passed=http_match,
    ))

    if not http_match:
        diff = client_requests - docker_metrics.http_200_count
        warnings.append(
            f"Request count mismatch: client={client_requests}, server={docker_metrics.http_200_count} "
            f"(diff={diff})"
        )

    # 2. Throughput comparison (only if server has data)
    throughput_match = True
    if docker_metrics.avg_generation_throughput > 0:
        throughput_match = is_within_tolerance(
            client_throughput,
            docker_metrics.avg_generation_throughput,
            tolerance=throughput_tolerance,
        )
        comparisons.append(MetricComparison(
            metric_name="Avg Throughput (tokens/s)",
            client_value=client_throughput,
            server_value=docker_metrics.avg_generation_throughput,
            difference_percent=calc_diff_percent(
                client_throughput, docker_metrics.avg_generation_throughput
            ),
            passed=throughput_match,
        ))

        if not throughput_match:
            warnings.append(
                f"Throughput mismatch: client={client_throughput:.1f}, "
                f"server={docker_metrics.avg_generation_throughput:.1f} tokens/s"
            )

    # 3. HTTP errors check
    if docker_metrics.http_error_count > 0:
        comparisons.append(MetricComparison(
            metric_name="HTTP Errors",
            client_value=0.0,
            server_value=float(docker_metrics.http_error_count),
            difference_percent=100.0,
            passed=False,
        ))
        warnings.append(f"HTTP errors detected: {docker_metrics.http_error_count}")

    # 4. Server errors check
    has_errors = len(docker_metrics.error_messages) > 0
    comparisons.append(MetricComparison(
        metric_name="Server Errors",
        client_value=0.0,
        server_value=float(len(docker_metrics.error_messages)),
        difference_percent=0.0 if not has_errors else 100.0,
        passed=not has_errors,
    ))

    if has_errors:
        warnings.append(f"Server ERROR logs detected: {len(docker_metrics.error_messages)}")
        for msg in docker_metrics.error_messages[:3]:
            warnings.append(f"  - {msg[:200]}")

    # Add warning messages from logs
    warnings.extend([f"[LOG WARNING] {msg[:200]}" for msg in docker_metrics.warning_messages[:5]])

    return DockerLogValidation(
        passed=http_match and throughput_match and not has_errors,
        http_request_match=http_match,
        throughput_match=throughput_match,
        has_errors=has_errors,
        comparisons=comparisons,
        warnings=warnings,
        docker_metrics=docker_metrics,
    )


async def auto_detect_vllm_container(port: int = 8000) -> Optional[str]:
    """
    Auto-detect vLLM container by port mapping.

    Args:
        port: Port number to search for

    Returns:
        Container name if found, None otherwise
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "ps", "--format", "{{.Names}}\t{{.Ports}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)

        for line in stdout.decode().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                name, ports = parts[0], parts[1]
                if f":{port}->" in ports or f":{port}/" in ports:
                    logger.info(f"Auto-detected vLLM container: {name}")
                    return name

        logger.warning(f"No container found with port {port}")
        return None

    except Exception as e:
        logger.warning(f"Failed to auto-detect container: {e}")
        return None
