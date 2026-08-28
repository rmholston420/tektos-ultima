#!/usr/bin/env python3
"""Comprehensive feature test for Tektos — tests all major subsystems via REST API."""

import json
import sys
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8020"
results = []


def api(method, path, data=None, label=""):
    """Make an API call and return (ok, response_dict_or_str)."""
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            try:
                result = json.loads(resp.read().decode())
            except json.JSONDecodeError:
                result = resp.read().decode()[:500]
            ok = resp.status == 200
            results.append({"label": label or path, "ok": ok, "status": resp.status, "preview": str(result)[:200]})
            return ok, result
    except urllib.error.HTTPError as e:
        try:
            result = json.loads(e.read().decode())
        except json.JSONDecodeError:
            result = e.read().decode()[:500]
        results.append({"label": label or path, "ok": False, "status": e.code, "preview": str(result)[:200]})
        return False, result
    except Exception as e:
        results.append({"label": label or path, "ok": False, "status": 0, "preview": str(e)[:200]})
        return False, str(e)


def test_health():
    """Test 1: Health endpoint."""
    ok, data = api("GET", "/health", label="Health")
    print(f"{'✓' if ok else '✗'} Health: {data}")
    return ok


def test_sessions():
    """Test 2: Session CRUD."""
    ok, data = api("POST", "/api/sessions", {
        "model": "Qwen3.6-35B-A3B-Q4_K_M",
        "cwd": ".",
        "permission_mode": "auto",
    }, label="Create session")
    if not ok:
        print(f"  ✗ Session creation failed: {data}")
        return False
    sid = data.get("session_id", data.get("id", ""))
    if not sid:
        print(f"  ✗ No session_id in response: {data}")
        return False

    # Get session
    ok2, data2 = api("GET", f"/api/sessions/{sid}", label="Get session")
    print(f"  {'✓' if ok2 else '✗'} Get session: {data2}")

    # List sessions
    ok3, data3 = api("GET", "/api/sessions", label="List sessions")
    print(f"  {'✓' if ok3 else '✗'} List sessions: {len(data3) if isinstance(data3, list) else data3}")

    # Interrupt
    ok4, data4 = api("POST", f"/api/sessions/{sid}/interrupt", label="Interrupt session")
    print(f"  {'✓' if ok4 else '✗'} Interrupt: {data4}")

    # Delete
    ok5, data5 = api("DELETE", f"/api/sessions/{sid}", label="Delete session")
    print(f"  {'✓' if ok5 else '✗'} Delete: {data5}")

    return ok and ok2 and ok3


def test_skills():
    """Test 3: Skill system."""
    ok, data = api("GET", "/api/skills", label="List skills")
    print(f"  {'✓' if ok else '✗'} List skills: {data}")

    ok2, data2 = api("GET", "/api/skills/stats", label="Skills stats")
    print(f"  {'✓' if ok2 else '✗'} Skills stats: {data2}")

    ok3, data3 = api("GET", "/api/skills/search", label="Skills search")
    print(f"  {'✓' if ok3 else '✗'} Skills search: {data3}")

    return ok and ok2


def test_tools():
    """Test 4: Tool registry."""
    ok, data = api("GET", "/api/tools", label="List tools")
    print(f"  {'✓' if ok else '✗'} List tools: {data}")

    ok2, data2 = api("GET", "/api/tools/schema", label="Tool schema")
    print(f"  {'✓' if ok2 else '✗'} Tool schema: {data2}")

    return ok


def test_memory():
    """Test 5: Memory system."""
    ok, data = api("GET", "/api/memory", label="Memory")
    print(f"  {'✓' if ok else '✗'} Memory: {data}")

    ok2, data2 = api("GET", "/api/memory/stats", label="Memory stats")
    print(f"  {'✓' if ok2 else '✗'} Memory stats: {data2}")

    return ok


def test_immune():
    """Test 6: Immune system."""
    ok, data = api("GET", "/api/immune/health", label="Immune health")
    print(f"  {'✓' if ok else '✗'} Immune health: {data}")

    ok2, data2 = api("GET", "/api/immune/threats", label="Immune threats")
    print(f"  {'✓' if ok2 else '✗'} Immune threats: {data2}")

    ok3, data3 = api("GET", "/api/immune/memory", label="Immune memory")
    print(f"  {'✓' if ok3 else '✗'} Immune memory: {data3}")

    ok4, data4 = api("GET", "/api/immune/detectors", label="Immune detectors")
    print(f"  {'✓' if ok4 else '✗'} Immune detectors: {data4}")

    return ok


def test_schema():
    """Test 7: Schema evolution."""
    ok, data = api("GET", "/api/schema", label="Schema")
    print(f"  {'✓' if ok else '✗'} Schema: {data}")

    ok2, data2 = api("GET", "/api/schema/patterns", label="Schema patterns")
    print(f"  {'✓' if ok2 else '✗'} Schema patterns: {data2}")

    return ok


def test_db():
    """Test 8: Database management."""
    ok, data = api("GET", "/api/db", label="DB info")
    print(f"  {'✓' if ok else '✗'} DB info: {data}")

    ok2, data2 = api("GET", "/api/db/schema", label="DB schema")
    print(f"  {'✓' if ok2 else '✗'} DB schema: {data2}")

    return ok


def test_thermal():
    """Test 9: Thermal monitoring."""
    ok, data = api("GET", "/api/thermal/status", label="Thermal status")
    print(f"  {'✓' if ok else '✗'} Thermal: {data}")

    ok2, data2 = api("GET", "/api/thermal/health", label="Thermal health")
    print(f"  {'✓' if ok2 else '✗'} Thermal health: {data2}")

    return ok


def test_metabolism():
    """Test 10: Metabolism engine."""
    ok, data = api("GET", "/api/metabolism", label="Metabolism")
    print(f"  {'✓' if ok else '✗'} Metabolism: {data}")

    ok2, data2 = api("GET", "/api/metabolism/context", label="Metabolism context")
    print(f"  {'✓' if ok2 else '✗'} Metabolism context: {data2}")

    return ok


def test_self_improvement():
    """Test 11: Self-improvement."""
    ok, data = api("GET", "/api/self_improvement/metrics", label="Self-improvement metrics")
    print(f"  {'✓' if ok else '✗'} Self-improvement metrics: {data}")

    ok2, data2 = api("GET", "/api/self_improvement/experiences", label="Self-improvement experiences")
    print(f"  {'✓' if ok2 else '✗'} Self-improvement experiences: {data2}")

    ok3, data3 = api("GET", "/api/self_improvement/report", label="Self-improvement report")
    print(f"  {'✓' if ok3 else '✗'} Self-improvement report: {data3}")

    return ok


def test_self_repair():
    """Test 12: Self-repair."""
    ok, data = api("GET", "/api/self_repair/status", label="Self-repair status")
    print(f"  {'✓' if ok else '✗'} Self-repair status: {data}")

    ok2, data2 = api("GET", "/api/self_repair/history", label="Self-repair history")
    print(f"  {'✓' if ok2 else '✗'} Self-repair history: {data2}")

    return ok


def test_planner():
    """Test 13: Planner."""
    ok, data = api("GET", "/api/planner/templates", label="Planner templates")
    print(f"  {'✓' if ok else '✗'} Planner templates: {data}")

    ok2, data2 = api("GET", "/api/planner/language-games", label="Planner language games")
    print(f"  {'✓' if ok2 else '✗'} Planner language games: {data2}")

    return ok


def test_dreamtime():
    """Test 14: Dreamtime (reflection/synthesis)."""
    ok, data = api("GET", "/api/dreamtime/summary", label="Dreamtime summary")
    print(f"  {'✓' if ok else '✗'} Dreamtime summary: {data}")

    ok2, data2 = api("GET", "/api/dreamtime/history", label="Dreamtime history")
    print(f"  {'✓' if ok2 else '✗'} Dreamtime history: {data2}")

    return ok


def test_axioms():
    """Test 15: Axioms."""
    ok, data = api("GET", "/api/axioms", label="Axioms")
    print(f"  {'✓' if ok else '✗'} Axioms: {data}")

    return ok


def test_state():
    """Test 16: Session state."""
    ok, data = api("GET", "/api/state/test-state", label="Session state")
    print(f"  {'✓' if ok else '✗'} Session state: {data}")

    return ok


def test_telemetry():
    """Test 17: Telemetry."""
    ok, data = api("GET", "/api/telemetry", label="Telemetry")
    print(f"  {'✓' if ok else '✗'} Telemetry: {data}")

    return ok


def test_hooks():
    """Test 18: Hooks system."""
    ok, data = api("GET", "/api/hooks", label="Hooks")
    print(f"  {'✓' if ok else '✗'} Hooks: {data}")

    return ok


def test_models():
    """Test 19: Models."""
    ok, data = api("GET", "/api/models", label="Models")
    print(f"  {'✓' if ok else '✗'} Models: {data}")

    return ok


def test_status_endpoints():
    """Test 20: Status endpoints for optional subsystems."""
    endpoints = [
        "/api/embedder/status",
        "/api/evaluation/status",
        "/api/inference/status",
        "/api/rag/status",
        "/api/repoMap/status",
        "/api/toolRouter/status",
        "/api/observability/status",
        "/api/multi-agent-orchestrator/status",
        "/api/nervous-system/status",
        "/api/context/status",
        "/api/plugins",
        "/api/mcp/status",
    ]
    ok_count = 0
    for ep in endpoints:
        ok, data = api("GET", ep, label=ep)
        status = "✓" if ok else "✗"
        preview = str(data)[:100]
        print(f"  {status} {ep}: {preview}")
        if ok:
            ok_count += 1
    return ok_count


def test_voice():
    """Test 21: Voice system."""
    ok, data = api("GET", "/api/voice/state", label="Voice state")
    print(f"  {'✓' if ok else '✗'} Voice state: {data}")
    return ok


def test_search():
    """Test 22: Search."""
    ok, data = api("GET", "/api/search", label="Search")
    print(f"  {'✓' if ok else '✗'} Search: {data}")
    return ok


def test_archive():
    """Test 23: Archive."""
    ok, data = api("GET", "/api/archive/sessions", label="Archive sessions")
    print(f"  {'✓' if ok else '✗'} Archive sessions: {data}")
    return ok


def test_logs():
    """Test 24: Logs."""
    ok, data = api("GET", "/api/logs", label="Logs")
    print(f"  {'✓' if ok else '✗'} Logs: {data}")
    return ok


def main():
    print("=" * 60)
    print("TEKTOS COMPREHENSIVE FEATURE TEST")
    print("=" * 60)

    tests = [
        ("Health", test_health),
        ("Sessions", test_sessions),
        ("Skills", test_skills),
        ("Tools", test_tools),
        ("Memory", test_memory),
        ("Immune System", test_immune),
        ("Schema Evolution", test_schema),
        ("Database", test_db),
        ("Thermal", test_thermal),
        ("Metabolism", test_metabolism),
        ("Self-Improvement", test_self_improvement),
        ("Self-Repair", test_self_repair),
        ("Planner", test_planner),
        ("Dreamtime", test_dreamtime),
        ("Axioms", test_axioms),
        ("Session State", test_state),
        ("Telemetry", test_telemetry),
        ("Hooks", test_hooks),
        ("Models", test_models),
        ("Status Endpoints", test_status_endpoints),
        ("Voice", test_voice),
        ("Search", test_search),
        ("Archive", test_archive),
        ("Logs", test_logs),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        print(f"\n--- {name} ---")
        try:
            result = test_fn()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ EXCEPTION: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)

    # Print all API results
    print("\n--- ALL API CALLS ---")
    for r in results:
        status = "✓" if r["ok"] else "✗"
        print(f"  {status} {r['label']}: {r['preview']}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
