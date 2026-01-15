"""Info command - Show system information."""

import sys


def info_command() -> None:
    """Show system and dependency information."""
    print("[llm-loadtest] System Information")
    print("─" * 40)

    # Python version
    print(f"  Python: {sys.version.split()[0]}")

    # llm-loadtest version
    try:
        from llm_loadtest import __version__
        print(f"  llm-loadtest: {__version__}")
    except ImportError:
        print("  llm-loadtest: Unknown")

    # Check httpx
    try:
        import httpx
        print(f"  httpx: {httpx.__version__}")
    except ImportError:
        print("  httpx: Not installed")

    # Check numpy
    try:
        import numpy
        print(f"  numpy: {numpy.__version__}")
    except ImportError:
        print("  numpy: Not installed")

    # Check pydantic
    try:
        import pydantic
        print(f"  pydantic: {pydantic.__version__}")
    except ImportError:
        print("  pydantic: Not installed")

    # GPU info
    try:
        import pynvml
        pynvml.nvmlInit()
        driver_version = pynvml.nvmlSystemGetDriverVersion()
        device_count = pynvml.nvmlDeviceGetCount()

        print(f"  NVIDIA Driver: {driver_version}")
        print(f"  GPU Count: {device_count}")

        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            mem_gb = mem.total / (1024**3)
            print(f"  GPU {i}: {name} ({mem_gb:.0f}GB)")

        pynvml.nvmlShutdown()
    except ImportError:
        print("  GPU: pynvml not installed")
    except Exception as e:
        print(f"  GPU: Not available ({e})")

    print("─" * 40)
