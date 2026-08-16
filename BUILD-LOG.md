# Build Log — Tektos-Ultima v1

## 2026-08-16: Vertical Slice 1 — Metabolism Layer + Real Telemetry

**Started:** 2026-08-16 10:40 UTC
**Completed:** 2026-08-16 11:30 UTC
**Wallclock:** ~50 minutes

### Changes
| Component | Files Changed | Lines Added | Lines Removed |
|-----------|--------------|-------------|---------------|
| Backend: `/api/telemetry` | `src/tektos/main.py` | +45 | -20 |
| Frontend: API types | `frontend/src/lib/api.ts` | +30 | -10 |
| Frontend: TelemetryPanel | `frontend/src/components/panels/TelemetryPanel.tsx` | ~346 | ~346 (rewrite) |
| Frontend: SystemDashboard | `frontend/src/components/panels/SystemDashboard.tsx` | ~453 | ~453 (rewrite) |
| Tests: Backend | `tests/test_api_telemetry.py` | +217 | 0 (new) |
| Tests: Frontend | `frontend/src/__tests__/telemetry-panel.test.tsx` | +360 | 0 (new) |
| Tests: E2E | `frontend/tests/e2e-telemetry.spec.ts` | +370 | 0 (new) |
| Docs | `ADR-LEDGER.md`, `PORTING_LEDGER.md`, `BUILD-LOG.md`, `BUG-LOG.md` | ~200 | 0 (new) |
| **Total** | **8 files** | **~1,671** | **~66** |

### Test Results

| Framework | File | Tests | Passed | Failed |
|-----------|------|-------|--------|--------|
| pytest | `tests/test_api_telemetry.py` | 15 | 15 | 0 |
| Jest | `frontend/src/__tests__/telemetry-panel.test.tsx` | 28 | 28 | 0 |
| Playwright | `frontend/tests/e2e-telemetry.spec.ts` | 20 | pending (live) | pending |

### Bugs Fixed
| Bug | File | Root Cause | Fix |
|-----|------|------------|-----|
| Telemetry endpoint returns 500 | `src/tektos/main.py` | `TelemetryCollector()` called as instance, but only has static methods | Rewrite to use `TelemetryCollector.collect()` static method |
| nvidia-smi fallback returns zeros | `src/tektos/main.py` | Invalid query fields (`clocks.graphics`, `clocks.memory`) cause RC=2 | Split into two queries: GPU info + compute apps |
| `latest.cpuTemp` undefined | `frontend/src/components/panels/SystemDashboard.tsx` | `TelemetryPoint` interface missing `cpuTemp` field | Replaced with `latest.cpuUtil` and `latest.diskPercent` |
| `global.fetch` not spiable in Jest jsdom | `frontend/src/__tests__/telemetry-panel.test.tsx` | Jest jsdom env doesn't support `jest.spyOn(global, "fetch")` | Use `global.fetch = jest.fn()` instead |

### Live Hardware Data (at 2026-08-16 10:45 UTC)
| Metric | Value |
|--------|-------|
| GPU | RTX 5090 (32GB VRAM) |
| GPU Temp | 55°C |
| GPU Util | 2% |
| VRAM Used | 27179 / 32607 MB (83.3%) |
| Power Draw | 77.8W |
| Power Limit | 400W |
| Fan Speed | 0 RPM |
| Clocks Graphics | 2632 MHz |
| Clocks Memory | 13801 MHz |

### Git
Commit: pending
