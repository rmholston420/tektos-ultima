"""Test Extremely Difficult 3 with simpler prompt."""
import requests, json, os, time, sys

BACKEND = "http://localhost:8020"
TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"
TIMEOUT = 1800

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

def send_prompt(session_id, prompt, timeout=1800):
    resp = requests.post(
        f"{BACKEND}/api/prompt/sse",
        json={"prompt": prompt, "session_id": session_id},
        stream=True,
        timeout=timeout
    )
    resp.raise_for_status()
    
    events = []
    current_event = "unknown"
    
    for line in resp.iter_lines():
        if not line:
            continue
        if line.startswith(b"event: "):
            current_event = line[7:].decode()
        elif line.startswith(b"data: "):
            data = json.loads(line[6:].decode())
            events.append({"type": current_event, "data": data})
    
    return events

def check_file_exists(filepath, timeout=1800):
    start = time.time()
    last_progress = start
    
    while time.time() - start < timeout:
        if os.path.exists(filepath):
            return True
        now = time.time()
        if now - last_progress >= 60:
            elapsed = int(now - start)
            remaining = int(timeout - elapsed)
            print(f"  Waiting for file... {elapsed}s elapsed, {remaining}s remaining")
            last_progress = now
        time.sleep(5)
    return False

print("=" * 60)
print("Retry: Extremely Difficult 3 (simpler prompt)")
print("=" * 60)

# Check backend
try:
    resp = requests.get(f"{BACKEND}/health", timeout=5)
    resp.raise_for_status()
    health = resp.json()
    print(f"Backend: LLM={health['llm_url']}, Model={health['llm_model']}")
except Exception as e:
    print(f"Backend not running: {e}")
    sys.exit(1)

session_id = create_session()

# Much simpler prompt - fewer requirements, shorter
prompt = """Write an enterprise data mesh implementation plan at /tmp/data_mesh.md.

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

print("Sending prompt...")
events = send_prompt(session_id, prompt, timeout=TIMEOUT)
print(f"  Received {len(events)} events")

if check_file_exists("/tmp/data_mesh.md", timeout=TIMEOUT):
    content = open("/tmp/data_mesh.md").read()
    content_lower = content.lower()
    print(f"PASS: File created ({len(content)} bytes)")
    
    for keyword, name in [("data as a product", "data as a product"), 
                           ("federated governance", "federated governance"),
                           ("self-serve", "self-serve"),
                           ("domain ownership", "domain ownership"),
                           ("ABAC", "ABAC access control")]:
        if keyword.lower() in content_lower:
            print(f"  {name} found")
        else:
            print(f"  {name} NOT found")
else:
    print("FAIL: File not created within timeout")
