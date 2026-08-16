# Bug Log — Tektos-Ultima v1

## B-001: Telemetry endpoint returns 500 Internal Server Error
**Date Found:** 2026-08-16 10:40 UTC
**Date Fixed:** 2026-08-16 10:42 UTC
**Severity:** Critical
**Status:** ✅ Fixed
**File:** `src/tektos/main.py` (line ~911)
**Root Cause:** `/api/telemetry` endpoint called `TelemetryCollector()` as an instance with methods like `.init()`, `.is_running()`, `.to_dict()`, but the class only defines **static methods**: `collect()` and `to_dict()`. This raised `AttributeError` on every request.
**Fix:** Rewrote endpoint to use `TelemetryCollector.collect()` (static) and `TelemetryCollector.to_dict(result)` (static).

## B-002: nvidia-smi fallback returns all zeros
**Date Found:** 2026-08-16 10:42 UTC
**Date Fixed:** 2026-08-16 10:44 UTC
**Severity:** Critical
**Status:** ✅ Fixed
**File:** `src/tektos/main.py` (line ~925)
**Root Cause:** The nvidia-smi query included invalid fields for RTX 5090 / driver 570+: `clocks.graphics`, `clocks.memory`, `utilization.memory`. This caused RC=2 (invalid query), which failed the `result.returncode == 0` check, so the fallback silently returned zeros for all GPU metrics.
**Fix:** Split into two queries:
1. `--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,power.limit,fan.speed` (GPU info)
2. `--query-compute-apps=memory.used,utilization.gpu,clocks.graphics,clocks.memory` (compute apps)
Both use only valid field names.

## B-003: SystemDashboard crashes with `Cannot read properties of undefined (reading 'toFixed')`
**Date Found:** 2026-08-16 10:46 UTC
**Date Fixed:** 2026-08-16 10:48 UTC
**Severity:** High
**Status:** ✅ Fixed
**File:** `frontend/src/components/panels/SystemDashboard.tsx` (line 350)
**Root Cause:** `GaugeRing` component at line 350 referenced `latest.cpuTemp` which was removed from `TelemetryPoint` interface when simulation code was replaced with real data. The property doesn't exist → `undefined.toFixed(0)` crashes.
**Fix:** Replaced `latest.cpuTemp` gauge with `latest.cpuUtil` and `latest.diskPercent` gauges (both exist in `TelemetryPoint`).

## B-004: Jest `jest.spyOn(global, "fetch")` fails in jsdom
**Date Found:** 2026-08-16 10:48 UTC
**Date Fixed:** 2026-08-16 10:50 UTC
**Severity:** Medium
**Status:** ✅ Fixed
**File:** `frontend/src/__tests__/telemetry-panel.test.tsx` (line 50)
**Root Cause:** Jest's jsdom environment does not support `jest.spyOn(global, "fetch")` — `fetch` is not a property that can be spied on. This caused all 28 tests to fail with "Property `fetch` does not exist in the provided object".
**Fix:** Changed to `global.fetch = jest.fn()` pattern (matching existing test conventions in `api-client.test.ts`).

## B-005: `screen.getByText("GPU Temperature")` ambiguous match
**Date Found:** 2026-08-16 10:50 UTC
**Date Fixed:** 2026-08-16 10:51 UTC
**Severity:** Low
**Status:** ✅ Fixed
**File:** `frontend/src/__tests__/telemetry-panel.test.tsx`
**Root Cause:** "GPU Temperature" appears in both the metric card label AND the sparkline chart title. `getByText()` throws on multiple matches.
**Fix:** Changed to `screen.getAllByText(/GPU Temperature/i)[0]` to disambiguate.
