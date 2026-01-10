"""GPU command - Show GPU status."""


def gpu_command() -> None:
    """Show current GPU status."""
    try:
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()

        print(f"[llm-loadtest] Found {device_count} GPU(s)")
        print("─" * 50)

        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)

            # Device name
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            # Memory info
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            mem_used_gb = mem.used / (1024**3)
            mem_total_gb = mem.total / (1024**3)
            mem_util = mem.used / mem.total * 100

            # GPU utilization
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_util = util.gpu
            except Exception:
                gpu_util = 0

            # Temperature
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                temp = None

            # Power
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000  # mW to W
            except Exception:
                power = None

            print(f"  GPU {i}: {name}")
            print(f"    Memory: {mem_used_gb:.1f}/{mem_total_gb:.1f} GB ({mem_util:.1f}%)")
            print(f"    GPU Util: {gpu_util}%")
            if temp is not None:
                print(f"    Temperature: {temp}°C")
            if power is not None:
                print(f"    Power: {power:.1f}W")
            print()

        pynvml.nvmlShutdown()

    except ImportError:
        print("[llm-loadtest] Error: pynvml not installed")
        print("[llm-loadtest] Install with: pip install nvidia-ml-py")
    except Exception as e:
        print(f"[llm-loadtest] Error: {e}")
