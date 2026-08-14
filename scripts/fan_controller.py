#!/usr/bin/env python3
"""GPU Fan Controller — pynvml-driven, no sudo required.

Replaces BIOS fan curve with NVML-driven software control.
Uses pynvml directly (no subprocess, no sudo) for fan speed control.
Monitors GPU temperature and adjusts fan speed to maintain thermal equilibrium.

Operational thresholds:
  - Yellow zone:  < 51°C  — fans run minimum
  - Target zone:  51–70°C — gradual fan ramp
  - Warning zone: 70–80°C — aggressive cooling
  - Red zone:     80–88°C — maximum cooling, alert user
  - Critical:     > 88°C  — emergency response, halt workloads
"""

import pynvml
import time
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

# ── Configuration ───────────────────────────────────────────────────────────

GPU_INDEX: int = 0
SLEEP_INTERVAL: int = 15  # seconds between checks
MIN_FAN: int = 30         # minimum fan speed (NVIDIA hardware limit)
MAX_FAN: int = 100        # maximum fan speed

# Thresholds (°C) — match Tektos S3 guardrail config
YELLOW: int = 51          # operational ceiling target
WARNING: int = 70         # start ramping harder
CAP: int = 80             # user's max sustained limit
RED: int = 88             # emergency threshold

# Fan speed targets per zone
FAN_MIN: int = 30
FAN_YELLOW: int = 50
FAN_WARNING: int = 65
FAN_CAP: int = 80
FAN_RED: int = 100


# ── Fan Curve ───────────────────────────────────────────────────────────────

@dataclass
class FanCurve:
    temp_min: int
    temp_max: int
    fan_speed: int

    def __post_init__(self):
        self.fan_speed = max(MIN_FAN, min(MAX_FAN, self.fan_speed))

    @property
    def temp_mid(self) -> int:
        return (self.temp_min + self.temp_max) // 2


FAN_CURVE: list[FanCurve] = [
    FanCurve(30, YELLOW - 5, FAN_MIN),        # well below yellow
    FanCurve(YELLOW - 5, YELLOW, FAN_YELLOW), # approaching yellow target
    FanCurve(YELLOW, WARNING, FAN_WARNING),    # yellow to warning — ramp
    FanCurve(WARNING, CAP, FAN_CAP),          # warning to cap — aggressive
    FanCurve(CAP, RED, FAN_RED),              # cap to red — max effort
]


def interpolate_fan_speed(temp: float) -> int:
    if temp <= FAN_CURVE[0].temp_min:
        return FAN_CURVE[0].fan_speed
    if temp >= FAN_CURVE[-1].temp_max:
        return FAN_CURVE[-1].fan_speed
    for i in range(len(FAN_CURVE) - 1):
        seg = FAN_CURVE[i]
        next_seg = FAN_CURVE[i + 1]
        if seg.temp_min <= temp <= next_seg.temp_max:
            t = (temp - seg.temp_min) / (next_seg.temp_max - seg.temp_min)
            speed = seg.fan_speed + t * (next_seg.fan_speed - seg.fan_speed)
            return int(round(speed))
    return FAN_CURVE[-1].fan_speed


def get_zone(temp: float) -> str:
    if temp < YELLOW:
        return "🟢 idle"
    elif temp < WARNING:
        return "🟡 yellow"
    elif temp < CAP:
        return "🟠 warning"
    elif temp < RED:
        return "🔴 red"
    else:
        return "🚨 critical"


def get_temperature() -> float:
    handle = pynvml.nvmlDeviceGetHandleByIndex(GPU_INDEX)
    return float(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))


def set_fan_speed_nvml(speed: int) -> bool:
    """Set fan speed directly via NVML — no sudo, no X11."""
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(GPU_INDEX)
        # First ensure software fan control is enabled
        try:
            pynvml.nvmlDeviceSetDefaultFanSpeed_v2(handle, GPU_INDEX)
        except pynvml.NVMLError:
            pass
        pynvml.nvmlDeviceSetFanSpeed_v2(handle, GPU_INDEX, speed)
        return True
    except pynvml.NVMLError as e:
        print(f"NVML fan set error: {e}")
        return False


def run_controller() -> None:
    pynvml.nvmlInit()
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(GPU_INDEX)

        # Verify software fan control is active
        current_state = pynvml.nvmlDeviceGetFanSpeed(handle)
        print(f"NVML fan controller starting — GPU {GPU_INDEX}")
        print(f"Current fan speed: {current_state}%")
        print(f"Thresholds: yellow={YELLOW}°C, warning={WARNING}°C, cap={CAP}°C, red={RED}°C")
        print(f"Fan curve: {len(FAN_CURVE)} points, range {MIN_FAN}–{MAX_FAN}%")
        print(f"{'-'*70}")

        current_fan = None

        while True:
            temp = get_temperature()
            zone = get_zone(temp)
            target_fan = interpolate_fan_speed(temp)

            if target_fan != current_fan:
                ok = set_fan_speed_nvml(target_fan)
                if ok:
                    current_fan = target_fan
                else:
                    print(f"ERROR: Failed to set fan speed to {target_fan}%")

            ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
            print(f"[{ts}] {zone:>12} | {temp:>5.1f}°C | fan: {current_fan}%")

            if "warning" in zone or "red" in zone:
                print(f"  ⚠️  GPU in {zone} zone — consider reducing workload")
            if "critical" in zone:
                print(f"  🚨 CRITICAL: GPU at {temp:.1f}°C — emergency response needed")

            time.sleep(SLEEP_INTERVAL)
    finally:
        pynvml.nvmlShutdown()


if __name__ == "__main__":
    run_controller()
