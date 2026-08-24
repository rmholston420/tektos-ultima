"""Run ED4: M&A Technology Integration Plan."""
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

print("🔵 Extremely Difficult 4: M&A Technology Integration Plan")
session_id = create_session()

prompt = """Write a merger and acquisition technology integration plan at /tmp/ma_integration.md.

Requirements:
1. Pre-close technology assessment (due diligence, system landscape, integration complexity)
2. Integration strategy (harmonization, best-of-breed, keep separate, phased consolidation)
3. Application portfolio rationalization (duplicate systems, feature overlap, sunset plan)
4. Data migration and consolidation (master data, historical data, data quality)
5. Infrastructure consolidation (data center rationalization, cloud migration)
6. Security and compliance (access control harmonization, compliance gap analysis)
7. Integration governance (steering committee, workstreams, milestone tracking)
8. Day-1 readiness (critical systems, communication, support, rollback procedures)

Write the plan as a markdown document. You MUST include the exact words due diligence, application portfolio rationalization, and Day-1 in the content."""

events = send_prompt(session_id, prompt, timeout=TIMEOUT)
print(f"  Received {len(events)} events")

filepath = "/tmp/ma_integration.md"
if not check_file_exists(filepath, timeout=TIMEOUT):
    print(f"FAIL: File not created within {TIMEOUT}s")
    sys.exit(1)

content = open(filepath).read()
content_lower = content.lower()
print(f"PASS: File created ({len(content)} bytes)")

all_passed = True
checks = [
    ("due diligence", "pre-close due diligence"),
    ("application portfolio rationalization", "application portfolio rationalization"),
    ("Day-1", "Day-1 readiness"),
    ("master data", "master data migration"),
    ("access control", "access control harmonization"),
    ("steering committee", "integration governance"),
]
for keyword, name in checks:
    if keyword.lower() in content_lower:
        print(f"  ✅ {name} found")
    else:
        print(f"  ❌ {name} NOT found")
        all_passed = False

print(f"Result: {'PASS' if all_passed else 'FAIL'}")
