# Porting Ledger — Tektos-Ultima v1

## New REST Endpoints

| Endpoint | Method | Description | Added |
|----------|--------|-------------|-------|
| `/api/telemetry` | GET | Real GPU/CPU/memory/disk telemetry from NVML + nvidia-smi + psutil | 2026-08-16 (VS1) |
| `/health` (enriched) | GET | Added event_bus.stats and state_machine.stats | 2026-08-16 (VS2) |

## New API Types (Frontend)

| Type | File | Description | Added |
|------|------|-------------|-------|
| `GPUTelemetryData` | `frontend/src/lib/api.ts` | GPU metrics shape from `/api/telemetry` | 2026-08-16 (VS1) |
| `SystemMetricsData` | `frontend/src/lib/api.ts` | System metrics shape from `/api/telemetry` | 2026-08-16 (VS1) |
| `TelemetryData` | `frontend/src/lib/api.ts` | Combined telemetry response | 2026-08-16 (VS1) |

## New Modules (Backend)

| Module | File | Description | Added |
|--------|------|-------------|-------|
| EventBus | `src/tektos/event_bus.py` | Pub/sub event bus with type filter routing | 2026-08-16 (VS2) |
| StateMachine | `src/tektos/state_machine.py` | FSM for session lifecycle | 2026-08-16 (VS2) |

## New Components (Frontend)

| Component | File | Description | Added |
|-----------|------|-------------|-------|
| `TelemetryPanel` | `frontend/src/components/panels/TelemetryPanel.tsx` | Real-time GPU/CPU/VRAM/Power/RAM/Storage/Cooling metrics | 2026-08-16 (VS1) |
| `SystemDashboard` | `frontend/src/components/panels/SystemDashboard.tsx` | System dashboard with real data (replaced simulation) | 2026-08-16 (VS1) |
| `NervousSystemPanel` | `frontend/src/components/panels/NervousSystemPanel.tsx` | Live event bus + state machine visualization | 2026-08-16 (VS2) |

## New Tests

| Test File | Framework | Tests | Added |
|-----------|-----------|-------|-------|
| `tests/test_api_telemetry.py` | pytest | 15 (live nvidia-smi) | 2026-08-16 (VS1) |
| `frontend/src/__tests__/telemetry-panel.test.tsx` | Jest | 28 (mock fetch) | 2026-08-16 (VS1) |
| `frontend/tests/e2e-telemetry.spec.ts` | Playwright | 20 (live backend→frontend) | 2026-08-16 (VS1) |
| `tests/test_nervous_system.py` | pytest | 28 (event bus + state machine + integration) | 2026-08-16 (VS2) |

## Modified Components

| Component | Changes | Date |
|-----------|---------|------|
| `src/tektos/main.py` | Fixed `/api/telemetry` endpoint; wired event bus + state machine init; enriched `/health` | 2026-08-16 (VS1 + VS2) |
| `src/tektos/runtime/session.py` | Wired all lifecycle methods to state machine transitions | 2026-08-16 (VS2) |
| `frontend/src/lib/api.ts` | Updated telemetry types to match new `/api/telemetry` response shape | 2026-08-16 (VS1) |
| `frontend/src/app/page.tsx` | Added NervousSystemPanel tab to dashboard | 2026-08-16 (VS2) |
