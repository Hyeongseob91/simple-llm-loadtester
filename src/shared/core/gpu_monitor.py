"""GPU monitoring utility using pynvml (NVIDIA Management Library)."""

import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import to avoid errors if pynvml is not installed
_pynvml = None


def _get_pynvml():
    """Lazy load pynvml module."""
    global _pynvml
    if _pynvml is None:
        try:
            import pynvml
            _pynvml = pynvml
        except ImportError:
            logger.warning(
                "pynvml not installed. GPU monitoring disabled. "
                "Install with: pip install nvidia-ml-py"
            )
            _pynvml = False
    return _pynvml


@dataclass
class GPUSample:
    """Single GPU sample measurement."""

    timestamp: float
    gpu_index: int
    device_name: str
    memory_used_gb: float
    memory_total_gb: float
    memory_util_percent: float
    gpu_util_percent: float
    temperature_celsius: Optional[float] = None
    power_draw_watts: Optional[float] = None
    power_limit_watts: Optional[float] = None


@dataclass
class GPUMetrics:
    """Aggregated GPU metrics from monitoring session."""

    device_name: str
    gpu_index: int
    # Memory
    memory_used_gb: float
    memory_total_gb: float
    memory_util_percent: float
    peak_memory_used_gb: float = 0.0
    avg_memory_used_gb: float = 0.0
    # Utilization
    gpu_util_percent: float = 0.0
    peak_gpu_util_percent: float = 0.0
    avg_gpu_util_percent: float = 0.0
    # Temperature & Power
    temperature_celsius: Optional[float] = None
    peak_temperature_celsius: Optional[float] = None
    power_draw_watts: Optional[float] = None
    peak_power_draw_watts: Optional[float] = None
    power_limit_watts: Optional[float] = None
    # Sampling info
    sample_count: int = 0
    duration_seconds: float = 0.0


@dataclass
class GPUMonitorResult:
    """Result from GPU monitoring session."""

    available: bool
    gpu_count: int = 0
    metrics: list[GPUMetrics] = field(default_factory=list)
    error: Optional[str] = None


class GPUMonitor:
    """Background GPU metrics collector.

    Usage:
        monitor = GPUMonitor(sample_interval=1.0)
        monitor.start()
        # ... run benchmark ...
        result = monitor.stop()
        for gpu in result.metrics:
            print(f"GPU {gpu.gpu_index}: Peak mem {gpu.peak_memory_used_gb:.1f} GB")
    """

    def __init__(
        self,
        sample_interval: float = 1.0,
        gpu_indices: Optional[list[int]] = None,
    ):
        """Initialize GPU monitor.

        Args:
            sample_interval: Time between samples in seconds.
            gpu_indices: List of GPU indices to monitor. None = all GPUs.
        """
        self.sample_interval = sample_interval
        self.gpu_indices = gpu_indices
        self.samples: list[GPUSample] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time: float = 0.0

    def start(self) -> bool:
        """Start background monitoring.

        Returns:
            True if monitoring started successfully, False otherwise.
        """
        pynvml = _get_pynvml()
        if not pynvml:
            logger.warning("GPU monitoring not available (pynvml not installed)")
            return False

        try:
            pynvml.nvmlInit()
            gpu_count = pynvml.nvmlDeviceGetCount()
            if gpu_count == 0:
                logger.warning("No NVIDIA GPUs detected")
                pynvml.nvmlShutdown()
                return False

            self.samples = []
            self._stop_event.clear()
            self._start_time = time.time()
            self._thread = threading.Thread(target=self._collect_loop, daemon=True)
            self._thread.start()
            logger.info(f"GPU monitoring started ({gpu_count} GPU(s) detected)")
            return True

        except Exception as e:
            logger.warning(f"Failed to start GPU monitoring: {e}")
            return False

    def stop(self) -> GPUMonitorResult:
        """Stop monitoring and return aggregated metrics.

        Returns:
            GPUMonitorResult with aggregated metrics.
        """
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        pynvml = _get_pynvml()
        if pynvml:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass

        return self._aggregate()

    def _collect_loop(self) -> None:
        """Collection loop running in background thread."""
        pynvml = _get_pynvml()
        if not pynvml:
            return

        try:
            gpu_count = pynvml.nvmlDeviceGetCount()

            # Determine which GPUs to monitor
            if self.gpu_indices:
                indices = [i for i in self.gpu_indices if i < gpu_count]
            else:
                indices = list(range(gpu_count))

            handles = []
            for idx in indices:
                handles.append((idx, pynvml.nvmlDeviceGetHandleByIndex(idx)))

            while not self._stop_event.is_set():
                for gpu_idx, handle in handles:
                    sample = self._collect_sample(gpu_idx, handle)
                    if sample:
                        self.samples.append(sample)

                self._stop_event.wait(self.sample_interval)

        except Exception as e:
            logger.error(f"Error in GPU monitoring loop: {e}")

    def _collect_sample(self, gpu_idx: int, handle) -> Optional[GPUSample]:
        """Collect a single GPU sample."""
        pynvml = _get_pynvml()
        if not pynvml:
            return None

        try:
            # Device name
            try:
                device_name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(device_name, bytes):
                    device_name = device_name.decode("utf-8")
            except Exception:
                device_name = f"GPU {gpu_idx}"

            # Memory
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            memory_used_gb = mem.used / (1024 ** 3)
            memory_total_gb = mem.total / (1024 ** 3)
            memory_util = (mem.used / mem.total) * 100 if mem.total > 0 else 0

            # GPU Utilization
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util = util.gpu
            except Exception:
                gpu_util = 0

            # Temperature
            try:
                temp = pynvml.nvmlDeviceGetTemperature(
                    handle, pynvml.NVML_TEMPERATURE_GPU
                )
            except Exception:
                temp = None

            # Power
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000  # mW to W
            except Exception:
                power = None

            try:
                power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000
            except Exception:
                power_limit = None

            return GPUSample(
                timestamp=time.time(),
                gpu_index=gpu_idx,
                device_name=device_name,
                memory_used_gb=memory_used_gb,
                memory_total_gb=memory_total_gb,
                memory_util_percent=memory_util,
                gpu_util_percent=gpu_util,
                temperature_celsius=temp,
                power_draw_watts=power,
                power_limit_watts=power_limit,
            )

        except Exception as e:
            logger.warning(f"Error collecting GPU {gpu_idx} sample: {e}")
            return None

    def _aggregate(self) -> GPUMonitorResult:
        """Aggregate samples into final metrics."""
        if not self.samples:
            pynvml = _get_pynvml()
            if not pynvml:
                return GPUMonitorResult(available=False, error="pynvml not installed")
            return GPUMonitorResult(available=False, error="No samples collected")

        # Group samples by GPU index
        gpu_samples: dict[int, list[GPUSample]] = {}
        for sample in self.samples:
            if sample.gpu_index not in gpu_samples:
                gpu_samples[sample.gpu_index] = []
            gpu_samples[sample.gpu_index].append(sample)

        duration = time.time() - self._start_time if self._start_time > 0 else 0

        metrics = []
        for gpu_idx in sorted(gpu_samples.keys()):
            samples = gpu_samples[gpu_idx]
            if not samples:
                continue

            last = samples[-1]

            # Memory stats
            mem_used_values = [s.memory_used_gb for s in samples]
            peak_mem = max(mem_used_values)
            avg_mem = sum(mem_used_values) / len(mem_used_values)

            # GPU utilization stats
            gpu_util_values = [s.gpu_util_percent for s in samples]
            peak_gpu_util = max(gpu_util_values)
            avg_gpu_util = sum(gpu_util_values) / len(gpu_util_values)

            # Temperature stats
            temp_values = [s.temperature_celsius for s in samples if s.temperature_celsius is not None]
            peak_temp = max(temp_values) if temp_values else None
            last_temp = last.temperature_celsius

            # Power stats
            power_values = [s.power_draw_watts for s in samples if s.power_draw_watts is not None]
            peak_power = max(power_values) if power_values else None
            last_power = last.power_draw_watts

            metrics.append(
                GPUMetrics(
                    device_name=last.device_name,
                    gpu_index=gpu_idx,
                    memory_used_gb=last.memory_used_gb,
                    memory_total_gb=last.memory_total_gb,
                    memory_util_percent=last.memory_util_percent,
                    peak_memory_used_gb=peak_mem,
                    avg_memory_used_gb=avg_mem,
                    gpu_util_percent=last.gpu_util_percent,
                    peak_gpu_util_percent=peak_gpu_util,
                    avg_gpu_util_percent=avg_gpu_util,
                    temperature_celsius=last_temp,
                    peak_temperature_celsius=peak_temp,
                    power_draw_watts=last_power,
                    peak_power_draw_watts=peak_power,
                    power_limit_watts=last.power_limit_watts,
                    sample_count=len(samples),
                    duration_seconds=duration,
                )
            )

        return GPUMonitorResult(
            available=True,
            gpu_count=len(metrics),
            metrics=metrics,
        )

    def get_current_sample(self) -> Optional[GPUSample]:
        """Get the most recent sample (for real-time display)."""
        if self.samples:
            return self.samples[-1]
        return None


def get_gpu_info() -> GPUMonitorResult:
    """Get current GPU information without continuous monitoring.

    Returns:
        GPUMonitorResult with current GPU state.
    """
    pynvml = _get_pynvml()
    if not pynvml:
        return GPUMonitorResult(available=False, error="pynvml not installed")

    try:
        pynvml.nvmlInit()
        gpu_count = pynvml.nvmlDeviceGetCount()

        if gpu_count == 0:
            pynvml.nvmlShutdown()
            return GPUMonitorResult(available=False, error="No NVIDIA GPUs detected")

        metrics = []
        for idx in range(gpu_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(idx)

            # Device name
            try:
                device_name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(device_name, bytes):
                    device_name = device_name.decode("utf-8")
            except Exception:
                device_name = f"GPU {idx}"

            # Memory
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            memory_used_gb = mem.used / (1024 ** 3)
            memory_total_gb = mem.total / (1024 ** 3)
            memory_util = (mem.used / mem.total) * 100 if mem.total > 0 else 0

            # GPU Utilization
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util = util.gpu
            except Exception:
                gpu_util = 0

            # Temperature
            try:
                temp = pynvml.nvmlDeviceGetTemperature(
                    handle, pynvml.NVML_TEMPERATURE_GPU
                )
            except Exception:
                temp = None

            # Power
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
            except Exception:
                power = None

            try:
                power_limit = pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000
            except Exception:
                power_limit = None

            metrics.append(
                GPUMetrics(
                    device_name=device_name,
                    gpu_index=idx,
                    memory_used_gb=memory_used_gb,
                    memory_total_gb=memory_total_gb,
                    memory_util_percent=memory_util,
                    peak_memory_used_gb=memory_used_gb,
                    avg_memory_used_gb=memory_used_gb,
                    gpu_util_percent=gpu_util,
                    peak_gpu_util_percent=gpu_util,
                    avg_gpu_util_percent=gpu_util,
                    temperature_celsius=temp,
                    power_draw_watts=power,
                    power_limit_watts=power_limit,
                    sample_count=1,
                    duration_seconds=0.0,
                )
            )

        pynvml.nvmlShutdown()
        return GPUMonitorResult(available=True, gpu_count=gpu_count, metrics=metrics)

    except Exception as e:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
        return GPUMonitorResult(available=False, error=str(e))


def get_gpu_static_info() -> Optional[dict]:
    """Get static GPU hardware information (driver, CUDA version, etc).

    Unlike get_gpu_info(), this focuses on hardware specs, not current utilization.
    Used for server infrastructure context in AI analysis reports.

    Returns:
        Dictionary with static GPU info or None if unavailable.

    Example:
        >>> info = get_gpu_static_info()
        >>> print(info)
        {
            'gpu_count': 2,
            'gpu_model': 'NVIDIA H100 80GB HBM3',
            'gpu_memory_total_gb': 80.0,
            'driver_version': '535.104.05',
            'cuda_version': '12.2',
            'mig_enabled': False,
            'gpu_details': [
                {'index': 0, 'name': 'NVIDIA H100 80GB HBM3', 'memory_total_gb': 80.0},
                {'index': 1, 'name': 'NVIDIA H100 80GB HBM3', 'memory_total_gb': 80.0}
            ]
        }
    """
    pynvml = _get_pynvml()
    if not pynvml:
        return None

    try:
        pynvml.nvmlInit()
        gpu_count = pynvml.nvmlDeviceGetCount()

        if gpu_count == 0:
            pynvml.nvmlShutdown()
            return None

        # Get driver version
        try:
            driver_version = pynvml.nvmlSystemGetDriverVersion()
            if isinstance(driver_version, bytes):
                driver_version = driver_version.decode("utf-8")
        except Exception:
            driver_version = None

        # Get CUDA version
        try:
            cuda_version_int = pynvml.nvmlSystemGetCudaDriverVersion_v2()
            cuda_major = cuda_version_int // 1000
            cuda_minor = (cuda_version_int % 1000) // 10
            cuda_version = f"{cuda_major}.{cuda_minor}"
        except Exception:
            cuda_version = None

        # Get first GPU details (assume homogeneous cluster)
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        # Device name
        try:
            device_name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(device_name, bytes):
                device_name = device_name.decode("utf-8")
        except Exception:
            device_name = "Unknown GPU"

        # Memory
        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            memory_total_gb = round(mem.total / (1024**3), 2)
        except Exception:
            memory_total_gb = 0.0

        # Check MIG mode
        mig_enabled = False
        try:
            mig_mode, _ = pynvml.nvmlDeviceGetMigMode(handle)
            mig_enabled = mig_mode == pynvml.NVML_DEVICE_MIG_ENABLE
        except Exception:
            # MIG not supported on this GPU
            pass

        # Collect all GPU details for multi-GPU systems
        gpu_details = []
        for idx in range(gpu_count):
            try:
                h = pynvml.nvmlDeviceGetHandleByIndex(idx)
                name = pynvml.nvmlDeviceGetName(h)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                m = pynvml.nvmlDeviceGetMemoryInfo(h)
                gpu_details.append({
                    "index": idx,
                    "name": name,
                    "memory_total_gb": round(m.total / (1024**3), 2),
                })
            except Exception:
                gpu_details.append({"index": idx, "name": f"GPU {idx}", "memory_total_gb": 0.0})

        pynvml.nvmlShutdown()

        return {
            "gpu_count": gpu_count,
            "gpu_model": device_name,
            "gpu_memory_total_gb": memory_total_gb,
            "driver_version": driver_version,
            "cuda_version": cuda_version,
            "mig_enabled": mig_enabled,
            "gpu_details": gpu_details,
        }

    except Exception as e:
        logger.warning(f"Failed to collect GPU static info: {e}")
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
        return None
