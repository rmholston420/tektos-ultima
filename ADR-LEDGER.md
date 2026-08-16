# ADR Ledger — Tektos-Ultima v1

## ADR-004: Metabolism Layer Architecture (2026-08-16)

**Status:** Implemented
**Date:** 2026-08-16
**Components:** `src/tektos/main.py` (`/api/telemetry`), `frontend/src/components/panels/TelemetryPanel.tsx`, `frontend/src/components/panels/SystemDashboard.tsx`

### Context
The telemetry endpoint had two bugs: (1) `TelemetryCollector` was called as an instance with methods (`init()`, `is_running()`) but only has static methods (`collect()`, `to_dict()`), and (2) the nvidia-smi fallback queried invalid fields (`clocks.graphics`, `clocks.memory`) causing RC=2 failures, silently returning zeros.

The frontend `TelemetryPanel` and `SystemDashboard` rendered simulated/sin-wave data because `/api/telemetry` returned errors.

### Decision
Replace the broken telemetry endpoint with a clean implementation that:
- **Primary path:** Uses `pynvml` (NVML library) for GPU metrics (temperature, utilization, VRAM, power draw, fan speed, clocks)
- **Fallback path:** Uses `nvidia-smi` CLI with separate queries for compatibility (temperature/utilization/power via `--query-gpu`, clocks/memory via `--query-compute-apps`)
- **System metrics:** Uses `psutil` for CPU utilization, RAM usage, disk usage (with graceful fallbacks if unavailable)
- **Response format:** `{ gpu: {temperature, utilization, memory_used, ...}, system: {cpu_util, mem_used_gb, ...}, timestamp }`

Frontend wiring:
- Updated `api.ts` types: `GPUTelemetryData`, `SystemMetricsData`, `TelemetryData`
- `TelemetryPanel.tsx`: Real-time GPU/CPU/VRAM/Power/RAM/Storage/Cooling metrics with color-coded thresholds, sparkline charts, gauge bars
- `SystemDashboard.tsx`: Replaced simulation (sin waves) with real `/api/telemetry` data, added VRAM card, CPU Util gauge, Disk gauge, thermal profile

### Consequences
- ✅ Backend endpoint now returns real hardware data on RTX 5090
- ✅ Both frontend panels show live data
- ✅ 15 backend tests (pytest), 28 frontend tests (Jest), 20 E2E tests (Playwright)
- ⚠️ `psutil` is a soft dependency — system metrics gracefully degrade if unavailable
- ⚠️ NVML errors are logged but don't crash — falls back to nvidia-smi

### Vertical Slice: Metabolism Layer + Real Telemetry
- Started: 2026-08-16 10:40 UTC
- Completed: 2026-08-16 11:30 UTC
- Wallclock: ~50 minutes
