"""Thermal Regulation System — configuration constants.

Operational target: 72°C GPU at 100% sustained load.
All values tuned for RTX 5090 (32 GB VRAM).

Verified optimal configuration:
    GPU power limit: 400W
    GPU clock speed: 2000–2500 MHz
    Fan speed:       TBD (fan control unavailable — power/clock only)

CPU thermal target: safe operating range (no fan control available).
"""

from __future__ import annotations

# ── GPU Target ──────────────────────────────────────────────────────────────

TARGET_TEMP: float = 72.0  # °C — the GPU temperature we regulate to

# ── Verified optimal GPU configuration ──────────────────────────────────────

OPTIMAL_POWER_LIMIT: int = 400   # watts — keeps GPU in safe zone
OPTIMAL_CLOCK_MHZ: int = 2250    # MHz — midpoint of 2000–2500 range

# ── GPU Power limits (watts) ────────────────────────────────────────────────

MAX_POWER_LIMIT: int = 600       # factory max — never exceed
MIN_POWER_LIMIT: int = 200       # floor — below this inference degrades too much

# ── GPU Clock offsets (MHz) ─────────────────────────────────────────────────

MAX_CLOCK_OFFSET: int = -300     # max negative offset from base clock

# ── Fan ─────────────────────────────────────────────────────────────────────
# NOTE: Fan control is currently unavailable. These values are reserved for
# future use when NVML fan control is restored.

FAN_MIN: int = 30                # NVIDIA hardware minimum (reserved)
FAN_MAX: int = 100               # full blast (reserved)
FAN_TARGET_SPEED: int = 70       # baseline (reserved)

# ── CPU Target ──────────────────────────────────────────────────────────────

CPU_TARGET_TEMP: float = 75.0    # °C — CPU safe operating target
CPU_MAX_TEMP: float = 90.0       # °C — CPU hard limit (throttle hard)

# ── Regulation timing ───────────────────────────────────────────────────────

REGULATION_INTERVAL: int = 10    # seconds between regulation cycles

# ── PID controller gains ────────────────────────────────────────────────────

PID_KP: float = 2.0            # proportional gain
PID_KI: float = 0.1            # integral gain
PID_KD: float = 0.5            # derivative gain
PID_INTEGRAL_LIMIT: float = 50.0  # anti-windup cap
PID_DERIVATIVE_LIMIT: float = 10.0  # derivative spike filter

# ── Step sizes (per cycle) ──────────────────────────────────────────────────

POWER_STEP: int = 25           # watts per power adjustment step
CLOCK_STEP: int = 50           # MHz per clock adjustment step
FAN_STEP: int = 5              # percent per fan adjustment step (reserved)
