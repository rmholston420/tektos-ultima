# Porting Ledger — Tektos-Ultima v1

## New REST Endpoints

| Endpoint | Method | Description | Added |
|----------|--------|-------------|-------|
| `/api/telemetry` | GET | Real GPU/CPU/memory/disk telemetry from NVML + nvidia-smi + psutil | 2026-08-16 |

## New API Types (Frontend)

| Type | File | Description | Added |
|------|------|-------------|-------|
| `GPUTelemetryData` | `frontend/src/lib/api.ts` | GPU metrics shape from `/api/telemetry` | 2026-08-16 |
| `SystemMetricsData` | `frontend/src/lib/api.ts` | System metrics shape from `/api/telemetry` | 2026-08-16 |
| `TelemetryData` | `frontend/src/lib/api.ts` | Combined telemetry response | 2026-08-16 |

## New Components (Frontend)

| Component | File | Description | Added |
|-----------|------|-------------|-------|
| `TelemetryPanel` | `frontend/src/components/panels/TelemetryPanel.tsx` | Real-time GPU/CPU/VRAM/Power/RAM/Storage/Cooling metrics | 2026-08-16 |
| `SystemDashboard` | `frontend/src/components/panels/SystemDashboard.tsx` | System dashboard with real data (replaced simulation) | 2026-08-16 |

## New Tests

| Test File | Framework | Tests | Added |
|-----------|-----------|-------|-------|
| `tests/test_api_telemetry.py` | pytest | 15 (live nvidia-smi) | 2026-08-16 |
| `frontend/src/__tests__/telemetry-panel.test.tsx` | Jest | 28 (mock fetch) | 2026-08-16 |
| `frontend/tests/e2e-telemetry.spec.ts` | Playwright | 20 (live backend→frontend) | 2026-08-16 |

## Modified Components

| Component | Changes | Date |
|-----------|---------|------|
| `src/tektos/main.py` | Fixed `/api/telemetry` endpoint: replaced broken NVML usage with correct static method calls, split nvidia-smi query for compatibility | 2026-08-16 |
| `frontend/src/lib/api.ts` | Updated telemetry types to match new `/api/telemetry` response shape | 2026-08-16 |
| `frontend/src/components/panels/TelemetryPanel.tsx` | Rewired to fetch real data from `/api/telemetry`, removed simulation | 2026-08-16 |
| `frontend/src/components/panels/SystemDashboard.tsx` | Replaced simulation with real data from `/api/telemetry`, fixed `cpuTemp` reference bug | 2026-08-16 |
