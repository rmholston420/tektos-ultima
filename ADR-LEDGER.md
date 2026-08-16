# ADR Ledger — Tektos-Ultima v1

## ADR-005: Nervous System — Event Bus + State Machine (2026-08-16)

**Status:** Implemented
**Date:** 2026-08-16
**Components:** `src/tektos/event_bus.py`, `src/tektos/state_machine.py`, `src/tektos/runtime/session.py`, `frontend/src/components/panels/NervousSystemPanel.tsx`

### Context
The audit identified a critical gap: the nervous system (signaling, control, state machine) was underdeveloped. The protocol envelope was thin — just a data shape with no event routing, no state machine, and no communication layer between VSM modules. S3 (Manager) had no visibility into system state, S4 (Planner) had no trigger mechanism, and the session lifecycle was managed by ad-hoc status field manipulation.

### Decision
Implement a two-component nervous system:

**Event Bus** (`event_bus.py`):
- Pub/sub event bus with type filter routing (exact, prefix `tool.*`, wildcard `*`)
- Synchronous in-process delivery for low latency
- Per-subscriber error isolation (one failing callback doesn't break others)
- Stats tracking (published count, dropped count, subscription count)
- Singleton pattern with `get_event_bus()` / `reset_event_bus()` for testing

**State Machine** (`state_machine.py`):
- Explicit FSM with defined transitions: `created → ready → running → ready|interrupted|failed`, `interrupted → ready`
- Invalid transitions raise `InvalidTransitionError`
- Transition history recorded per session for replay/debugging
- Events emitted to event bus on every transition (`session.state_change`)
- Stats tracking (transitions completed, invalid attempts, state distribution)

**SessionManager Integration**:
- Every lifecycle method (`create_session`, `add_ws_connection`, `interrupt_session`, `complete_session`, `archive_session`, `remove_ws_connection`) now calls `get_state_machine().transition()` alongside existing event store writes
- Health endpoint enriched with event bus + state machine stats

**Frontend NervousSystemPanel**:
- Live visualization of event bus stats (published, subscriptions, dropped)
- State machine stats (active sessions, transitions, invalid attempts, state distribution)
- VSM layer subscription diagram (S1→S5)
- Real-time state change feed via WebSocket
- Active session list with color-coded status badges

### Consequences
- ✅ Nervous system is now a first-class architecture layer
- ✅ S3 Manager can subscribe to state changes and intervene
- ✅ S4 Planner can trigger on specific events
- ✅ Invalid transitions are caught early (not silent corruption)
- ✅ Full transition history enables session replay and debugging
- ✅ Frontend panel gives real-time visibility into system health
- ⚠️ State machine uses a soft sync with SessionManager.status (transitions may diverge if status is modified outside FSM)
- ⚠️ Event bus is synchronous — for future distributed deployments, would need async queue + broker

### Vertical Slice: Nervous System — Event Bus + State Machine
- Started: 2026-08-16 11:30 UTC
- Completed: 2026-08-16 12:30 UTC
- Wallclock: ~60 minutes
- 28 backend tests (pytest), 1 frontend component (NervousSystemPanel), 1 dashboard tab (Nervous System)

---

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
