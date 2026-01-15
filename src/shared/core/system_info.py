"""System information collection utilities using psutil."""

import logging
import platform
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import to avoid startup errors if psutil is not installed
_psutil = None


def _get_psutil():
    """Lazy load psutil module."""
    global _psutil
    if _psutil is None:
        try:
            import psutil

            _psutil = psutil
        except ImportError:
            logger.warning("psutil not installed. System info collection disabled.")
            _psutil = False
    return _psutil if _psutil else None


def get_system_info() -> Optional[dict]:
    """Collect system hardware information (CPU, RAM).

    Returns:
        Dictionary with system info or None if unavailable.

    Example:
        >>> info = get_system_info()
        >>> print(info)
        {
            'cpu_model': 'AMD EPYC 7763 64-Core Processor',
            'cpu_cores_physical': 64,
            'cpu_cores_logical': 128,
            'cpu_frequency_mhz': 2450.0,
            'numa_nodes': 2,
            'ram_total_gb': 512.0,
            'ram_available_gb': 256.5
        }
    """
    psutil = _get_psutil()
    if not psutil:
        return None

    try:
        cpu_freq = psutil.cpu_freq()
        mem = psutil.virtual_memory()

        # Get CPU model name
        cpu_model = _get_cpu_model_name()

        # Detect NUMA nodes (Linux specific)
        numa_nodes = _get_numa_node_count()

        return {
            "cpu_model": cpu_model,
            "cpu_cores_physical": psutil.cpu_count(logical=False) or 0,
            "cpu_cores_logical": psutil.cpu_count(logical=True) or 0,
            "cpu_frequency_mhz": round(cpu_freq.current, 1) if cpu_freq else None,
            "numa_nodes": numa_nodes,
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_available_gb": round(mem.available / (1024**3), 2),
        }
    except Exception as e:
        logger.warning(f"Failed to collect system info: {e}")
        return None


def _get_cpu_model_name() -> str:
    """Get CPU model name from various sources."""
    # Try platform.processor() first
    cpu_model = platform.processor()
    if cpu_model and cpu_model.strip():
        return cpu_model.strip()

    # Linux: Try /proc/cpuinfo
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":")[1].strip()
    except (FileNotFoundError, PermissionError):
        pass

    # Fallback
    return platform.machine() or "Unknown"


def _get_numa_node_count() -> int:
    """Get NUMA node count (Linux specific)."""
    try:
        import os

        numa_path = "/sys/devices/system/node/"
        if os.path.exists(numa_path):
            nodes = [d for d in os.listdir(numa_path) if d.startswith("node")]
            return len(nodes)
    except Exception:
        pass
    return 1
