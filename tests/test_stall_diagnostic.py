"""Diagnostic test to understand the stall pattern.

Tests:
1. Does the LLM call file_write tool? Or just generate text?
2. Does the agent loop get stuck in a repetition pattern?
3. Does context window pressure cause stalls?
4. What happens with a very simple prompt that MUST use file_write?
"""
import requests, json, os, time, sys

BACKEND = "http://localhost:8020"
TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"

def create_session():
    resp = requests.post(f"{BACKEND}/api/sessions", json={
        "model": "Qwen_Qwen3.6-35B-A3B-Q5_K_M",
        "cwd": TEST_DIR,
        "provider": "local",
        "permission_mode": "auto"
    })
    resp.raise_for_status()
    data = resp.json()
    return data.get("session_id") or data.get("id")

def send_prompt_detailed(session_id, prompt, timeout=900):
    """Send prompt and track ALL events in detail."""
    resp = requests.post(
        f"{BACKEND}/api/prompt/sse",
        json={"prompt": prompt, "session_id": session_id},
        stream=True,
        timeout=timeout
    )
    resp.raise_for_status()
    
    events = []
    current_event = "unknown"
    tool_starts = 0
    tool_completes = 0
    tool_names = []
    assistant_deltas = 0
    assistant_completed = 0
    loop_warnings = 0
    session_failed = 0
    
    for line in resp.iter_lines():
        if not line:
            continue
        if line.startswith(b"event: "):
            current_event = line[7:].decode()
        elif line.startswith(b"data: "):
            data = json.loads(line[6:].decode())
            events.append({"type": current_event, "data": data})
            
            if current_event in ("tool_started", "tool.started"):
                tool_starts += 1
                tool_names.append(data.get("tool_name", "unknown"))
            elif current_event in ("tool_completed", "tool.completed"):
                tool_completes += 1
            elif current_event in ("assistant_delta", "assistant.delta"):
                assistant_deltas += 1
            elif current_event in ("assistant_completed", "assistant.completed"):
                assistant_completed += 1
            elif current_event in ("loop_safety_warning", "loop_safety.warning"):
                loop_warnings += 1
            elif current_event in ("session_failed", "session.failed"):
                session_failed += 1
    
    return {
        "total_events": len(events),
        "tool_starts": tool_starts,
        "tool_completes": tool_completes,
        "tool_names": tool_names,
        "assistant_deltas": assistant_deltas,
        "assistant_completed": assistant_completed,
        "loop_warnings": loop_warnings,
        "session_failed": session_failed,
        "events": events,
    }

def check_file_exists(filepath, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(filepath):
            return True
        time.sleep(2)
    return False

# Check backend
try:
    resp = requests.get(f"{BACKEND}/health", timeout=5)
    resp.raise_for_status()
    health = resp.json()
    print(f"Backend: LLM={health['llm_url']}, Model={health['llm_model']}")
except Exception as e:
    print(f"Backend not running: {e}")
    sys.exit(1)

print("=" * 60)
print("DIAGNOSTIC: Understanding the Stall Pattern")
print("=" * 60)

# Test 1: Simple prompt that MUST use file_write
print("\n--- Test 1: Simple file_write prompt ---")
session_id = create_session()
prompt1 = """Write the text 'Hello World' to /tmp/test_simple.md using the file_write tool.
You MUST call the file_write tool with path='/tmp/test_simple.md' and content='Hello World'."""

result1 = send_prompt_detailed(session_id, prompt1, timeout=300)
print(f"  Events: {result1['total_events']}")
print(f"  Tool calls: {result1['tool_starts']} starts, {result1['tool_completes']} completes")
print(f"  Tool names: {result1['tool_names']}")
print(f"  Assistant deltas: {result1['assistant_deltas']}")
print(f"  Assistant completed: {result1['assistant_completed']}")
print(f"  Loop warnings: {result1['loop_warnings']}")
print(f"  Session failed: {result1['session_failed']}")

if check_file_exists("/tmp/test_simple.md", timeout=60):
    content = open("/tmp/test_simple.md").read()
    print(f"  ✅ File created: {len(content)} bytes: {content[:50]}")
else:
    print(f"  ❌ File NOT created")

# Test 2: Planning prompt (same as Very Difficult 1)
print("\n--- Test 2: Planning prompt (Very Difficult 1 pattern) ---")
session_id = create_session()
prompt2 = """Write a multi-tenant SaaS architecture plan at /tmp/test_saaS.md.

Requirements:
1. Architecture overview (microservices, multi-tenant database, API gateway)
2. Tenant isolation (database schema, data partitioning, access control)
3. Scalability (horizontal scaling, load balancing, caching)
4. Security (authentication, authorization, encryption, audit logging)
5. Monitoring and observability (metrics, logging, tracing, alerting)
6. Deployment strategy (CI/CD, blue-green, canary releases)
7. Cost optimization (resource allocation, auto-scaling, spot instances)
8. Compliance (GDPR, SOC 2, data residency, backup and recovery)

Write the plan as a markdown document. You MUST include the exact words microservices, tenant isolation, and CI/CD in the content."""

result2 = send_prompt_detailed(session_id, prompt2, timeout=900)
print(f"  Events: {result2['total_events']}")
print(f"  Tool calls: {result2['tool_starts']} starts, {result2['tool_completes']} completes")
print(f"  Tool names: {result2['tool_names']}")
print(f"  Assistant deltas: {result2['assistant_deltas']}")
print(f"  Assistant completed: {result2['assistant_completed']}")
print(f"  Loop warnings: {result2['loop_warnings']}")
print(f"  Session failed: {result2['session_failed']}")

if check_file_exists("/tmp/test_saaS.md", timeout=60):
    content = open("/tmp/test_saaS.md").read()
    print(f"  ✅ File created: {len(content)} bytes")
else:
    print(f"  ❌ File NOT created")

# Test 3: Extremely Difficult prompt (the one that stalls)
print("\n--- Test 3: Extremely Difficult prompt (Data Mesh pattern) ---")
session_id = create_session()
prompt3 = """Write an enterprise data mesh implementation plan at /tmp/test_data_mesh.md.

Requirements:
1. Data mesh principles (domain ownership, data as a product, self-serve platform)
2. Domain decomposition (bounded contexts, domain teams)
3. Data product design (schema design, SLA definition)
4. Self-serve data platform (infrastructure, tooling)
5. Federated governance (interoperability standards, security policies)
6. Data quality (data profiling, lineage tracking)
7. Security (RBAC, ABAC, encryption)
8. Organizational transformation (data literacy)

Write the plan as a markdown document. You MUST include the exact words data as a product, federated governance, and self-serve in the content."""

result3 = send_prompt_detailed(session_id, prompt3, timeout=900)
print(f"  Events: {result3['total_events']}")
print(f"  Tool calls: {result3['tool_starts']} starts, {result3['tool_completes']} completes")
print(f"  Tool names: {result3['tool_names']}")
print(f"  Assistant deltas: {result3['assistant_deltas']}")
print(f"  Assistant completed: {result3['assistant_completed']}")
print(f"  Loop warnings: {result3['loop_warnings']}")
print(f"  Session failed: {result3['session_failed']}")

if check_file_exists("/tmp/test_data_mesh.md", timeout=60):
    content = open("/tmp/test_data_mesh.md").read()
    print(f"  ✅ File created: {len(content)} bytes")
else:
    print(f"  ❌ File NOT created")

# Test 4: Prompt that explicitly requires file_write tool
print("\n--- Test 4: Explicit file_write requirement ---")
session_id = create_session()
prompt4 = """Write an enterprise data mesh implementation plan.

Requirements:
1. Data mesh principles (domain ownership, data as a product)
2. Domain decomposition (bounded contexts)
3. Data product design (schema design)
4. Self-serve platform (infrastructure)
5. Federated governance (interoperability)
6. Data quality (profiling, lineage)
7. Security (RBAC, encryption)
8. Organizational transformation (data literacy)

IMPORTANT: You MUST use the file_write tool to write the plan to /tmp/test_explicit.md.
Do NOT just output the text. You MUST call file_write with:
  path: "/tmp/test_explicit.md"
  content: [the full markdown plan]

The plan must include: data as a product, federated governance, self-serve."""

result4 = send_prompt_detailed(session_id, prompt4, timeout=900)
print(f"  Events: {result4['total_events']}")
print(f"  Tool calls: {result4['tool_starts']} starts, {result4['tool_completes']} completes")
print(f"  Tool names: {result4['tool_names']}")
print(f"  Assistant deltas: {result4['assistant_deltas']}")
print(f"  Assistant completed: {result4['assistant_completed']}")
print(f"  Loop warnings: {result4['loop_warnings']}")
print(f"  Session failed: {result4['session_failed']}")

if check_file_exists("/tmp/test_explicit.md", timeout=60):
    content = open("/tmp/test_explicit.md").read()
    print(f"  ✅ File created: {len(content)} bytes")
else:
    print(f"  ❌ File NOT created")

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
tests = [
    ("Simple file_write", result1),
    ("Planning (SaaS)", result2),
    ("Extremely Difficult (Data Mesh)", result3),
    ("Explicit file_write", result4),
]
for name, r in tests:
    print(f"\n  {name}:")
    print(f"    Events: {r['total_events']}")
    print(f"    Tool calls: {r['tool_starts']} starts, {r['tool_completes']} completes")
    print(f"    Tools used: {r['tool_names']}")
    print(f"    Assistant completed: {r['assistant_completed']}")
    print(f"    Loop warnings: {r['loop_warnings']}")
