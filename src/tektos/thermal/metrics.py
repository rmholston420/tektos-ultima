"""Thermal Regulation System — metrics collection.

Gathers all GPU and CPU telemetry via NVML and psutil.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pynvml

logger = logging.getLogger(__name__)

# ── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class GPUTelemetry:
    """Snapshot of GPU hardware state."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    temperature_gpu: float = 0.0
    power_draw: float = 0.0
    power_limit: float = 0.0
    utilization: float = 0.0
    fan_speed: int = 0
    clocks_graphics: int = 0
    clocks_memory: int = 0
    memory_used: int = 0
    memory_total: int = 0
    memory_temperature: float = 0.0
    power_state: str = ""
    clocks_event_reasons: dict[str, bool] = field(default_factory=dict)


@dataclass
class CPUTelemetry:
    """Snapshot of CPU thermal state."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    temperature_cpu: float = 0.0
    utilization: float = 0.0
    power_draw: float = 0.0
    core_temps: list[float] = field(default_factory=list)
    frequency_mhz: float = 0.0


@dataclass
class ThermalSnapshot:
    """Combined GPU + CPU telemetry snapshot."""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    gpu: GPUTelemetry = field(default_factory=GPUTelemetry)
    cpu: CPUTelemetry = field(default_factory=CPUTelemetry)


# ── NVML GPU Collector ──────────────────────────────────────────────────────

class NVMLCollector:
    """Collect GPU metrics via pynvml."""

    _initialized: bool = False
    GPU_INDEX: int = 0

    @classmethod
    def _ensure_init(cls) -> None:
        if not cls._initialized:
            try:
                pynvml.nvmlInit()
                cls._initialized = True
            except pynvml.NVMLError as e:
                logger.error(f"NVML init failed: {e}")
                raise

    @classmethod
    def collect_gpu(cls) -> GPUTelemetry:
        """Gather all available GPU metrics."""
        cls._ensure_init()
        handle = pynvml.nvmlDeviceGetHandleByIndex(cls.GPU_INDEX)

        try:
            return GPUTelemetry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                temperature_gpu=float(pynvml.nvmlDeviceGetTemperature(
                    handle, pynvml.NVML_TEMPERATURE_GPU)),
                power_draw=float(pynvml.nvmlDeviceGetPowerUsage(handle)) / 1000.0,
                power_limit=float(pynvml.nvmlDeviceGetPowerManagementLimit(handle)) / 1000.0,
                utilization=float(pynvml.nvmlDeviceGetUtilizationRates(handle).gpu),
                fan_speed=int(pynvml.nvmlDeviceGetFanSpeed(handle)),
                clocks_graphics=pynvml.nvmlDeviceGetClockInfo(
                    handle, pynvml.NVML_CLOCK_GRAPHICS),
                clocks_memory=pynvml.nvmlDeviceGetClockInfo(
                    handle, pynvml.NVML_CLOCK_MEM),
                memory_used=int(pynvml.nvmlDeviceGetMemoryInfo(handle).used) // (1024 ** 2),
                memory_total=int(pynvml.nvmlDeviceGetMemoryInfo(handle).total) // (1024 ** 2),
                memory_temperature=0.0,  # NVML_TEMPERATURE_MEMORY not available on all GPUs
                power_state=f"P{pynvml.nvmlDeviceGetPerformanceState(handle)}",
                clocks_event_reasons={
                    "sw_power_cap": False,
                    "hw_thermal_slowdown": False,
                },
            )
        except pynvml.NVMLError as e:
            logger.error(f"NVML GPU collection failed: {e}")
            return GPUTelemetry()

    @classmethod
    def shutdown(cls) -> None:
        if cls._initialized:
            pynvml.nvmlShutdown()
            cls._initialized = False


# ── CPU Collector ────────────────────────────────────────────────────────────

class CPUCollector:
    """Collect CPU thermal metrics via /sys/class/thermal and psutil."""

    @staticmethod
    def collect_cpu() -> CPUTelemetry:
        """Gather CPU temperature, utilization, and frequency."""
        try:
            # Try reading from /sys/class/thermal (standard on Linux)
            core_temps = CPUCollector._read_thermal_zones()
            temp_cpu = max(core_temps) if core_temps else 0.0

            # CPU utilization via psutil
            try:
                import psutil
                util = psutil.cpu_percent(interval=0.5)
                freq = psutil.cpu_freq()
                freq_mhz = freq.current if freq else 0.0
                power_draw = CPUCollector._read_power_draw()
            except ImportError:
                util = CPUCollector._cpu_percent_via_load()
                freq_mhz = 0.0
                power_draw = 0.0

            return CPUTelemetry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                temperature_cpu=temp_cpu,
                utilization=util,
                power_draw=power_draw,
                core_temps=core_temps,
                frequency_mhz=freq_mhz,
            )
        except Exception as e:
            logger.error(f"CPU collection failed: {e}")
            return CPUTelemetry()

    @staticmethod
    def _read_thermal_zones() -> list[float]:
        """Read all CPU thermal zones from /sys/class/thermal."""
        temps: list[float] = []
        try:
            import os
            thermal_dir = "/sys/class/thermal"
            if not os.path.isdir(thermal_dir):
                return temps
            for entry in os.listdir(thermal_dir):
                if entry.startswith("thermal_zone"):
                    zone_path = os.path.join(thermal_dir, entry, "temp")
                    try:
                        with open(zone_path, "r") as f:
                            raw = f.read().strip()
                            # Thermal zones report in millidegrees
                            temp = int(raw) / 1000.0
                            temps.append(temp)
                    except (IOError, ValueError):
                        continue
        except Exception:
            pass
        return temps

    @staticmethod
    def _read_power_draw() -> float:
        """Read CPU power draw from /sys/class/powercap/intel-rapl."""
        try:
            import os
            rapl_path = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
            if os.path.exists(rapl_path):
                with open(rapl_path, "r") as f:
                    return float(f.read().strip()) / 1e6  # convert uJ to J
        except Exception:
            pass
        return 0.0

    @staticmethod
    def _cpu_percent_via_load() -> float:
        """Fallback CPU utilization via /proc/loadavg."""
        try:
            import os
            with open("/proc/loadavg", "r") as f:
                load_1min = float(f.read().split()[0])
            # Estimate: load / num_cores * 100
            import multiprocessing
            cores = multiprocessing.cpu_count() or 1
            return min(load_1min / cores * 100.0, 100.0)
        except Exception:
            return 0.0


# ── Unified Collector ────────────────────────────────────────────────────────

class MetricsCollector:
    """Unified collector for GPU + CPU telemetry."""

    @staticmethod
    def collect() -> ThermalSnapshot:
        """Gather all GPU and CPU metrics."""
        gpu = NVMLCollector.collect_gpu()
        cpu = CPUCollector.collect_cpu()
        return ThermalSnapshot(gpu=gpu, cpu=cpu)

    @staticmethod
    def to_dict(snapshot: ThermalSnapshot) -> dict[str, Any]:
        """Convert snapshot to serializable dict."""
        return {
            "timestamp": snapshot.timestamp,
            "gpu": {
                "temperature_gpu": snapshot.gpu.temperature_gpu,
                "power_draw": snapshot.gpu.power_draw,
                "power_limit": snapshot.gpu.power_limit,
                "utilization": snapshot.gpu.utilization,
                "fan_speed": snapshot.gpu.fan_speed,
                "clocks_graphics_mhz": snapshot.gpu.clocks_graphics,
                "clocks_memory_mhz": snapshot.gpu.clocks_memory,
                "memory_used_mb": snapshot.gpu.memory_used,
                "memory_total_mb": snapshot.gpu.memory_total,
                "memory_temperature": snapshot.gpu.memory_temperature,
                "power_state": snapshot.gpu.power_state,
            },
            "cpu": {
                "temperature_cpu": snapshot.cpu.temperature_cpu,
                "utilization": snapshot.cpu.utilization,
                "power_draw": snapshot.cpu.power_draw,
                "core_temps": snapshot.cpu.core_temps,
                "frequency_mhz": snapshot.cpu.frequency_mhz,
            },
        }
