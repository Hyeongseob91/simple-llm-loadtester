"""Validation module for cross-checking client metrics against server metrics."""

import asyncio
import logging
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import aiohttp

from .docker_logs import (
    DockerLogCollector,
    auto_detect_vllm_container,
    validate_docker_logs,
)
from .models import (
    DockerLogValidation,
    MetricComparison,
    PrometheusValidation,
    ValidationResult,
)

logger = logging.getLogger(__name__)


class VLLMMetricsSnapshot:
    """Snapshot of vLLM Prometheus metrics."""

    def __init__(self):
        self.request_success_total: int = 0
        self.generation_tokens_total: int = 0
        self.ttft_sum: float = 0.0
        self.ttft_count: int = 0
        self.timestamp: Optional[datetime] = None

    @property
    def avg_ttft_seconds(self) -> float:
        """Calculate average TTFT in seconds."""
        if self.ttft_count == 0:
            return 0.0
        return self.ttft_sum / self.ttft_count

    @property
    def avg_ttft_ms(self) -> float:
        """Calculate average TTFT in milliseconds."""
        return self.avg_ttft_seconds * 1000


class MetricsValidator:
    """Validates benchmark results against vLLM server metrics."""

    # Prometheus metric name patterns (supports different vLLM versions)
    # Updated to handle labels like {engine="0",model_name="..."}
    METRIC_PATTERNS = {
        "request_success": [
            # Match with labels: vllm:request_success_total{...} value
            r"vllm:request_success_total\{[^}]*\}\s+([\d.e+-]+)",
            r"vllm_request_success_total\{[^}]*\}\s+([\d.e+-]+)",
            # Fallback without labels
            r"vllm:request_success_total\s+(\d+)",
            r"vllm_request_success_total\s+(\d+)",
        ],
        "generation_tokens": [
            r"vllm:generation_tokens_total\{[^}]*\}\s+([\d.e+-]+)",
            r"vllm_generation_tokens_total\{[^}]*\}\s+([\d.e+-]+)",
            r"vllm:generation_tokens_total\s+(\d+)",
            r"vllm_generation_tokens_total\s+(\d+)",
        ],
        "ttft_sum": [
            r"vllm:time_to_first_token_seconds_sum\{[^}]*\}\s+([\d.e+-]+)",
            r"vllm_time_to_first_token_seconds_sum\{[^}]*\}\s+([\d.e+-]+)",
            r"vllm:time_to_first_token_seconds_sum\s+([\d.e+-]+)",
            r"vllm_time_to_first_token_seconds_sum\s+([\d.e+-]+)",
        ],
        "ttft_count": [
            r"vllm:time_to_first_token_seconds_count\{[^}]*\}\s+([\d.e+-]+)",
            r"vllm_time_to_first_token_seconds_count\{[^}]*\}\s+([\d.e+-]+)",
            r"vllm:time_to_first_token_seconds_count\s+(\d+)",
            r"vllm_time_to_first_token_seconds_count\s+(\d+)",
        ],
    }

    def __init__(
        self,
        server_url: str,
        docker_enabled: bool = True,
        container_name: Optional[str] = None,
        prometheus_timeout: float = 5.0,
        docker_timeout: float = 10.0,
        tolerance: float = 0.05,
        progress_callback: Optional[callable] = None,
    ):
        """
        Initialize the validator.

        Args:
            server_url: vLLM server URL (e.g., http://localhost:8000)
            docker_enabled: Whether Docker validation is enabled (False = Prometheus only)
            container_name: Docker container name (auto-detected if None)
            prometheus_timeout: Timeout for Prometheus metrics fetch
            docker_timeout: Timeout for Docker log collection
            tolerance: Default tolerance for metric comparison (5%)
            progress_callback: Callback for progress updates (step, message, status)
        """
        self.server_url = server_url.rstrip("/")
        self.docker_enabled = docker_enabled
        self.container_name = container_name
        self.prometheus_timeout = prometheus_timeout
        self.docker_timeout = docker_timeout
        self.tolerance = tolerance
        self.progress_callback = progress_callback

        # Snapshot storage
        self._before_prometheus: Optional[VLLMMetricsSnapshot] = None
        self._after_prometheus: Optional[VLLMMetricsSnapshot] = None

        # Docker log collector
        self._docker_collector: Optional[DockerLogCollector] = None
        self._docker_available: bool = False

    def _emit_progress(self, step: str, message: str, status: str = "running") -> None:
        """Emit progress update via callback."""
        if self.progress_callback:
            self.progress_callback(step, message, status)

    async def initialize(self) -> None:
        """Initialize the validator (auto-detect container if needed)."""
        self._emit_progress("init", "Initializing validator...", "running")

        # Skip Docker initialization if docker_enabled is False
        if not self.docker_enabled:
            self._emit_progress("init", "Docker validation disabled, Prometheus only", "running")
            logger.info("Docker validation disabled by user, using Prometheus only")
            return

        if self.container_name is None:
            self._emit_progress("init", "Auto-detecting vLLM container...", "running")
            parsed = urlparse(self.server_url)
            port = parsed.port or 8000
            self.container_name = await auto_detect_vllm_container(port)

        if self.container_name:
            self._emit_progress("init", f"Container found: {self.container_name}", "running")
            self._docker_collector = DockerLogCollector(
                self.container_name, timeout=self.docker_timeout
            )
            self._docker_available = await self._docker_collector.check_docker_available()
            if self._docker_available:
                self._emit_progress("init", "Docker log collection available", "running")
            else:
                self._emit_progress("init", "Docker log collection unavailable", "warning")
        else:
            self._emit_progress("init", "No vLLM container detected", "warning")

    async def collect_before(self) -> bool:
        """
        Collect metrics snapshot before benchmark.

        Returns:
            True if at least one source (Prometheus/Docker) is available
        """
        self._emit_progress("before", "Collecting baseline metrics...", "running")
        prometheus_ok = False
        docker_ok = False

        # Collect Prometheus metrics
        try:
            self._emit_progress("before", "Fetching Prometheus metrics (before)...", "running")
            self._before_prometheus = await self._fetch_prometheus_metrics()
            prometheus_ok = self._before_prometheus is not None
            if prometheus_ok:
                self._emit_progress("before", "Prometheus baseline collected", "running")
                logger.info("Prometheus metrics snapshot (before) collected")
            else:
                self._emit_progress("before", "Prometheus metrics unavailable", "warning")
        except Exception as e:
            self._emit_progress("before", f"Prometheus error: {str(e)[:50]}", "warning")
            logger.warning(f"Failed to collect Prometheus metrics: {e}")

        # Start Docker log collection
        if self._docker_collector:
            self._emit_progress("before", "Starting Docker log collection...", "running")
            docker_ok = await self._docker_collector.collect_before()
            if docker_ok:
                self._emit_progress("before", "Docker log collection started", "running")
                logger.info("Docker log collection started")
            else:
                self._emit_progress("before", "Docker log collection failed", "warning")

        return prometheus_ok or docker_ok

    async def collect_after(self) -> bool:
        """
        Collect metrics snapshot after benchmark.

        Returns:
            True if collection succeeded
        """
        self._emit_progress("after", "Collecting final metrics...", "running")
        prometheus_ok = False

        # Collect Prometheus metrics
        try:
            self._emit_progress("after", "Fetching Prometheus metrics (after)...", "running")
            self._after_prometheus = await self._fetch_prometheus_metrics()
            prometheus_ok = self._after_prometheus is not None
            if prometheus_ok:
                self._emit_progress("after", "Prometheus final snapshot collected", "running")
                logger.info("Prometheus metrics snapshot (after) collected")
            else:
                self._emit_progress("after", "Prometheus metrics unavailable", "warning")
        except Exception as e:
            self._emit_progress("after", f"Prometheus error: {str(e)[:50]}", "warning")
            logger.warning(f"Failed to collect Prometheus metrics: {e}")

        return prometheus_ok

    async def validate(
        self,
        client_total_requests: int,
        client_successful_requests: int,
        client_avg_ttft_ms: float,
        client_total_output_tokens: int,
        client_throughput: float,
    ) -> ValidationResult:
        """
        Validate client metrics against server metrics.

        Args:
            client_total_requests: Total requests sent by client
            client_successful_requests: Successful requests (for comparison)
            client_avg_ttft_ms: Average TTFT measured by client (ms)
            client_total_output_tokens: Total output tokens from client
            client_throughput: Throughput measured by client (tokens/s)

        Returns:
            ValidationResult with all comparisons
        """
        self._emit_progress("validate", "Starting validation...", "running")
        result = ValidationResult(
            overall_passed=True,
            tolerance=self.tolerance,
            validated_at=datetime.utcnow(),
        )

        # 1. Prometheus validation
        self._emit_progress("validate", "Validating Prometheus metrics...", "running")
        prometheus_validation = await self._validate_prometheus(
            client_successful_requests,
            client_avg_ttft_ms,
            client_total_output_tokens,
        )
        if prometheus_validation:
            result.prometheus_validation = prometheus_validation
            result.prometheus_available = True
            result.all_comparisons.extend(prometheus_validation.comparisons)
            result.all_warnings.extend(prometheus_validation.warnings)
            status = "running" if prometheus_validation.passed else "warning"
            self._emit_progress("validate", f"Prometheus: {'PASSED' if prometheus_validation.passed else 'FAILED'}", status)

        # 2. Docker log validation
        self._emit_progress("validate", "Validating Docker logs...", "running")
        docker_validation = await self._validate_docker_logs(
            client_successful_requests,
            client_throughput,
        )
        if docker_validation:
            result.docker_log_validation = docker_validation
            result.docker_available = True
            result.all_comparisons.extend(docker_validation.comparisons)
            result.all_warnings.extend(docker_validation.warnings)
            status = "running" if docker_validation.passed else "warning"
            self._emit_progress("validate", f"Docker logs: {'PASSED' if docker_validation.passed else 'FAILED'}", status)

        # 3. Calculate overall pass/fail
        all_passed = True
        if prometheus_validation:
            all_passed = all_passed and prometheus_validation.passed
        if docker_validation:
            all_passed = all_passed and docker_validation.passed

        result.overall_passed = all_passed

        # Emit final status
        final_status = "completed" if all_passed else "failed"
        self._emit_progress("complete", f"Validation {'PASSED' if all_passed else 'FAILED'}", final_status)

        return result

    async def _fetch_prometheus_metrics(self) -> Optional[VLLMMetricsSnapshot]:
        """Fetch and parse Prometheus metrics from vLLM server."""
        metrics_url = f"{self.server_url}/metrics"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    metrics_url, timeout=aiohttp.ClientTimeout(total=self.prometheus_timeout)
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Prometheus metrics returned {response.status}")
                        return None

                    text = await response.text()
                    return self._parse_prometheus_metrics(text)

        except aiohttp.ClientError as e:
            logger.warning(f"Failed to fetch Prometheus metrics: {e}")
            return None
        except asyncio.TimeoutError:
            logger.warning("Prometheus metrics fetch timed out")
            return None

    def _parse_prometheus_metrics(self, text: str) -> VLLMMetricsSnapshot:
        """Parse Prometheus metrics text into a snapshot.

        Note: request_success_total has multiple lines for different finished_reason
        (stop, length, abort, error), so we need to sum all of them.
        """
        snapshot = VLLMMetricsSnapshot()
        snapshot.timestamp = datetime.utcnow()

        for metric_name, patterns in self.METRIC_PATTERNS.items():
            # For request_success, we need to sum all matches (different finished_reason)
            if metric_name == "request_success":
                total = 0
                for pattern in patterns:
                    matches = re.findall(pattern, text)
                    if matches:
                        for value in matches:
                            total += int(float(value))
                        break  # Use first matching pattern format
                snapshot.request_success_total = total
            else:
                # For other metrics, take the first match
                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        value = match.group(1)
                        if metric_name == "generation_tokens":
                            snapshot.generation_tokens_total = int(float(value))
                        elif metric_name == "ttft_sum":
                            snapshot.ttft_sum = float(value)
                        elif metric_name == "ttft_count":
                            snapshot.ttft_count = int(float(value))
                        break

        return snapshot

    async def _validate_prometheus(
        self,
        client_requests: int,
        client_avg_ttft_ms: float,
        client_total_tokens: int,
    ) -> Optional[PrometheusValidation]:
        """Validate against Prometheus metrics."""
        if self._before_prometheus is None or self._after_prometheus is None:
            return None

        comparisons: list[MetricComparison] = []
        warnings: list[str] = []
        all_passed = True

        # Calculate deltas
        delta_requests = (
            self._after_prometheus.request_success_total
            - self._before_prometheus.request_success_total
        )
        delta_tokens = (
            self._after_prometheus.generation_tokens_total
            - self._before_prometheus.generation_tokens_total
        )

        # TTFT delta calculation
        ttft_sum_delta = self._after_prometheus.ttft_sum - self._before_prometheus.ttft_sum
        ttft_count_delta = self._after_prometheus.ttft_count - self._before_prometheus.ttft_count
        server_avg_ttft_ms = (
            (ttft_sum_delta / ttft_count_delta * 1000) if ttft_count_delta > 0 else 0.0
        )

        # 1. Request count comparison
        request_diff = abs(client_requests - delta_requests)
        request_passed = self._is_within_tolerance(client_requests, delta_requests)
        comparisons.append(MetricComparison(
            metric_name="Request Count",
            client_value=float(client_requests),
            server_value=float(delta_requests),
            difference_percent=self._calc_diff_percent(client_requests, delta_requests),
            passed=request_passed,
        ))
        if not request_passed:
            warnings.append(
                f"Request count mismatch: client={client_requests}, server={delta_requests}"
            )
            all_passed = False

        # 2. TTFT comparison (use 10% tolerance)
        ttft_passed = self._is_within_tolerance(client_avg_ttft_ms, server_avg_ttft_ms, tolerance=0.10)
        comparisons.append(MetricComparison(
            metric_name="Avg TTFT (ms)",
            client_value=client_avg_ttft_ms,
            server_value=server_avg_ttft_ms,
            difference_percent=self._calc_diff_percent(client_avg_ttft_ms, server_avg_ttft_ms),
            passed=ttft_passed,
        ))
        if not ttft_passed:
            warnings.append(
                f"TTFT mismatch: client={client_avg_ttft_ms:.1f}ms, server={server_avg_ttft_ms:.1f}ms"
            )
            all_passed = False

        # 3. Token count comparison
        token_passed = self._is_within_tolerance(client_total_tokens, delta_tokens)
        comparisons.append(MetricComparison(
            metric_name="Total Tokens",
            client_value=float(client_total_tokens),
            server_value=float(delta_tokens),
            difference_percent=self._calc_diff_percent(client_total_tokens, delta_tokens),
            passed=token_passed,
        ))
        if not token_passed:
            warnings.append(
                f"Token count mismatch: client={client_total_tokens}, server={delta_tokens}"
            )
            all_passed = False

        return PrometheusValidation(
            passed=all_passed,
            comparisons=comparisons,
            warnings=warnings,
        )

    async def _validate_docker_logs(
        self,
        client_requests: int,
        client_throughput: float,
    ) -> Optional[DockerLogValidation]:
        """Validate against Docker logs."""
        if self._docker_collector is None:
            return None

        docker_metrics = await self._docker_collector.collect_after()
        if docker_metrics is None:
            return None

        return validate_docker_logs(
            client_requests=client_requests,
            client_throughput=client_throughput,
            docker_metrics=docker_metrics,
            request_tolerance=self.tolerance,
            throughput_tolerance=0.10,  # 10% for throughput
        )

    def _is_within_tolerance(
        self, client: float, server: float, tolerance: Optional[float] = None
    ) -> bool:
        """Check if values are within tolerance."""
        tol = tolerance if tolerance is not None else self.tolerance
        if server == 0:
            return client == 0
        diff_percent = abs(client - server) / server
        return diff_percent <= tol

    def _calc_diff_percent(self, client: float, server: float) -> float:
        """Calculate percentage difference."""
        if server == 0:
            return 0.0 if client == 0 else 100.0
        return abs(client - server) / server * 100


def format_validation_result(result: ValidationResult) -> str:
    """Format validation result for console output."""
    lines = [
        "",
        "═" * 65,
        "                    Validation Results",
        "═" * 65,
    ]

    # Prometheus section
    if result.prometheus_available and result.prometheus_validation:
        lines.append("                   Prometheus Metrics")
        lines.append("─" * 65)
        lines.append(f"{'Metric':<20} {'Client':<12} {'Server':<12} {'Diff':<8} {'Status'}")
        lines.append("─" * 65)

        for comp in result.prometheus_validation.comparisons:
            status = "✓ PASS" if comp.passed else "✗ FAIL"
            lines.append(
                f"{comp.metric_name:<20} {comp.client_value:<12.1f} {comp.server_value:<12.1f} "
                f"{comp.difference_percent:<7.1f}% {status}"
            )

    # Docker log section
    if result.docker_available and result.docker_log_validation:
        lines.append("─" * 65)
        lines.append("                   Docker Log Validation")
        lines.append("─" * 65)

        for comp in result.docker_log_validation.comparisons:
            status = "✓ PASS" if comp.passed else "✗ FAIL"
            lines.append(
                f"{comp.metric_name:<20} {comp.client_value:<12.1f} {comp.server_value:<12.1f} "
                f"{comp.difference_percent:<7.1f}% {status}"
            )

        # Additional info
        if result.docker_log_validation.docker_metrics:
            dm = result.docker_log_validation.docker_metrics
            lines.append("─" * 65)
            lines.append("                   Additional Info")
            lines.append("─" * 65)
            lines.append(f"Peak KV Cache Usage: {dm.peak_kv_cache_usage:.1f}%")
            lines.append(f"Prefix Cache Hit:    {dm.prefix_cache_hit_rate:.1f}%")
            lines.append(f"Warnings:            {len(dm.warning_messages)}")

    # Overall result
    lines.append("═" * 65)
    prom_status = "✓" if result.prometheus_validation and result.prometheus_validation.passed else "✗"
    docker_status = "✓" if result.docker_log_validation and result.docker_log_validation.passed else "✗"

    status_parts = []
    if result.prometheus_available:
        status_parts.append(f"Prometheus {prom_status}")
    if result.docker_available:
        status_parts.append(f"Docker Log {docker_status}")

    overall = "PASSED" if result.overall_passed else "FAILED"
    lines.append(f"Overall: {overall} ({', '.join(status_parts)})")
    lines.append("")

    return "\n".join(lines)
