"""Serving engine information collection (vLLM, TGI, etc.)."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


async def get_vllm_engine_info(server_url: str, timeout: float = 5.0) -> Optional[dict]:
    """Fetch vLLM engine configuration from standard endpoints.

    Collects information from:
    - /v1/models: Model name
    - /metrics: Prometheus metrics (if available)
    - /version: Engine version (if available)

    Args:
        server_url: vLLM server URL (e.g., http://localhost:8000)
        timeout: Request timeout in seconds

    Returns:
        Dictionary with engine info or None if failed.

    Example:
        >>> info = await get_vllm_engine_info("http://localhost:8000")
        >>> print(info)
        {
            'engine_type': 'vLLM',
            'engine_version': '0.4.2',
            'model_name': 'meta-llama/Llama-2-7b-hf',
            'quantization': None,
            'context_length': None,
            'max_num_seqs': None,
            'gpu_memory_utilization': None,
            'tensor_parallel_size': None
        }
    """
    info = {
        "engine_type": "vLLM",
        "engine_version": None,
        "model_name": None,
        "quantization": None,
        "context_length": None,
        "max_num_seqs": None,
        "max_num_batched_tokens": None,
        "gpu_memory_utilization": None,
        "tensor_parallel_size": None,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Try /v1/models for model info
            info = await _fetch_model_info(client, server_url, info)

            # Try /metrics for Prometheus metrics
            info = await _fetch_metrics_info(client, server_url, info)

            # Try /version if available
            info = await _fetch_version_info(client, server_url, info)

    except Exception as e:
        logger.warning(f"Failed to fetch vLLM engine info from {server_url}: {e}")

    # Only return if we got at least model name
    return info if info.get("model_name") else None


async def _fetch_model_info(client: httpx.AsyncClient, server_url: str, info: dict) -> dict:
    """Fetch model information from /v1/models endpoint."""
    try:
        resp = await client.get(f"{server_url}/v1/models")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data") and len(data["data"]) > 0:
                model_info = data["data"][0]
                info["model_name"] = model_info.get("id")

                # Some vLLM versions include additional info
                if "max_model_len" in model_info:
                    info["context_length"] = model_info["max_model_len"]
    except Exception as e:
        logger.debug(f"Failed to fetch /v1/models: {e}")

    return info


async def _fetch_metrics_info(client: httpx.AsyncClient, server_url: str, info: dict) -> dict:
    """Fetch configuration hints from Prometheus /metrics endpoint."""
    try:
        resp = await client.get(f"{server_url}/metrics")
        if resp.status_code == 200:
            metrics_text = resp.text
            info = _parse_prometheus_metrics(metrics_text, info)
    except Exception as e:
        logger.debug(f"Failed to fetch /metrics: {e}")

    return info


async def _fetch_version_info(client: httpx.AsyncClient, server_url: str, info: dict) -> dict:
    """Fetch version information from /version endpoint."""
    try:
        resp = await client.get(f"{server_url}/version")
        if resp.status_code == 200:
            data = resp.json()
            info["engine_version"] = data.get("version")
    except Exception as e:
        logger.debug(f"Failed to fetch /version: {e}")

    return info


def _parse_prometheus_metrics(metrics_text: str, info: dict) -> dict:
    """Parse Prometheus metrics for configuration hints.

    vLLM exposes various metrics that can hint at configuration:
    - vllm:num_requests_waiting{model_name="..."}
    - vllm:kv_cache_usage_perc{model_name="..."}
    - vllm:num_requests_running{model_name="..."}
    """
    lines = metrics_text.split("\n")

    for line in lines:
        # Skip comments and empty lines
        if line.startswith("#") or not line.strip():
            continue

        # Extract model_name from any metric label
        if 'model_name="' in line and not info.get("model_name"):
            try:
                start = line.find('model_name="') + len('model_name="')
                end = line.find('"', start)
                if end > start:
                    info["model_name"] = line[start:end]
            except Exception:
                pass

        # Look for tensor_parallel_size in metrics (some vLLM versions expose this)
        if "tensor_parallel_size" in line.lower():
            try:
                # Format: metric_name{...} value
                parts = line.split()
                if len(parts) >= 2:
                    value = int(float(parts[-1]))
                    info["tensor_parallel_size"] = value
            except Exception:
                pass

    return info


async def get_vllm_runtime_metrics(server_url: str, timeout: float = 5.0) -> Optional[dict]:
    """Fetch vLLM runtime metrics from /metrics endpoint.

    These metrics represent the actual vLLM load, independent of system-wide GPU metrics.

    Args:
        server_url: vLLM server URL
        timeout: Request timeout in seconds

    Returns:
        Dictionary with runtime metrics or None if failed.

    Example:
        >>> metrics = await get_vllm_runtime_metrics("http://localhost:8000")
        >>> print(metrics)
        {
            'kv_cache_usage_perc': 0.45,
            'num_requests_running': 5,
            'num_requests_waiting': 2,
            'prefix_cache_hit_rate': 0.87,
        }
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{server_url}/metrics")
            if resp.status_code != 200:
                return None

            metrics_text = resp.text
            return _parse_runtime_metrics(metrics_text)
    except Exception as e:
        logger.debug(f"Failed to fetch vLLM runtime metrics: {e}")
        return None


def _parse_runtime_metrics(metrics_text: str) -> dict:
    """Parse vLLM Prometheus metrics for runtime state."""
    metrics = {
        "kv_cache_usage_perc": None,
        "num_requests_running": None,
        "num_requests_waiting": None,
        "prefix_cache_hit_rate": None,
    }

    prefix_queries = 0
    prefix_hits = 0

    for line in metrics_text.split("\n"):
        if line.startswith("#") or not line.strip():
            continue

        try:
            # vllm:kv_cache_usage_perc{...} value
            if "vllm:kv_cache_usage_perc" in line:
                value = float(line.split()[-1])
                metrics["kv_cache_usage_perc"] = round(value * 100, 1)  # Convert to percentage

            # vllm:num_requests_running{...} value
            elif "vllm:num_requests_running" in line:
                metrics["num_requests_running"] = int(float(line.split()[-1]))

            # vllm:num_requests_waiting{...} value
            elif "vllm:num_requests_waiting" in line:
                metrics["num_requests_waiting"] = int(float(line.split()[-1]))

            # Prefix cache for hit rate calculation
            elif "vllm:prefix_cache_queries_total" in line and "_created" not in line:
                prefix_queries = float(line.split()[-1])

            elif "vllm:prefix_cache_hits_total" in line and "_created" not in line:
                prefix_hits = float(line.split()[-1])

        except (ValueError, IndexError):
            continue

    # Calculate prefix cache hit rate
    if prefix_queries > 0:
        metrics["prefix_cache_hit_rate"] = round((prefix_hits / prefix_queries) * 100, 1)

    return metrics


async def detect_serving_engine(server_url: str, timeout: float = 5.0) -> Optional[dict]:
    """Auto-detect serving engine type and collect information.

    Tries to identify the serving engine by probing various endpoints.

    Args:
        server_url: Server URL
        timeout: Request timeout in seconds

    Returns:
        Dictionary with engine info or None if detection failed.
    """
    # Try vLLM first (most common)
    info = await get_vllm_engine_info(server_url, timeout)
    if info:
        return info

    # Try TGI (Text Generation Inference)
    info = await _try_tgi_detection(server_url, timeout)
    if info:
        return info

    # Fallback: unknown engine
    return None


async def _try_tgi_detection(server_url: str, timeout: float) -> Optional[dict]:
    """Try to detect Hugging Face TGI server."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # TGI has /info endpoint
            resp = await client.get(f"{server_url}/info")
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "engine_type": "TGI",
                    "engine_version": data.get("version"),
                    "model_name": data.get("model_id"),
                    "quantization": data.get("quantization_config", {}).get("quant_method"),
                    "context_length": data.get("max_total_tokens"),
                    "max_num_seqs": data.get("max_concurrent_requests"),
                }
    except Exception:
        pass

    return None
