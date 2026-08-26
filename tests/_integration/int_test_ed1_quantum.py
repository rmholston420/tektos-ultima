"""Run ED1: Quantum Computing Enterprise Readiness Plan."""

import requests, json, os, time, sys

if __name__ == "__main__":
    BACKEND = "http://localhost:8020"
    TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"
    TIMEOUT = 1800

    def create_session():
    print("  [1/4] Creating session...")
    resp = requests.post(f"{BACKEND}/api/sessions", json={
    "model": "Qwen_Qwen3.6-35B-A3B-Q5_K_M",
    "cwd": TEST_DIR,
    "provider": "local",
    "permission_mode": "auto"
    }, timeout=10)
    print(f"    Session response: {resp.status_code}")
    data = resp.json()
    print(f"    Session data keys: {list(data.keys())}")
    session_id = data.get("session_id") or data.get("id")
    print(f"    Session ID: {session_id}")
    return session_id

    def send_prompt(session_id, prompt, timeout=1800):
    print(f"  [2/4] Sending prompt to session {session_id[:8]}...")
    print(f"    Prompt length: {len(prompt)} chars")
    start = time.time()
    resp = requests.post(
    f"{BACKEND}/api/prompt/sse",
    json={"prompt": prompt, "session_id": session_id},
    stream=True,
    timeout=timeout
    )
    elapsed = time.time() - start
    print(f"    Response status: {resp.status_code} (after {elapsed:.1f}s)")
    
    events = []
    event_count = 0
    last_event_time = time.time()
    current_event = "unknown"
    session_failed = False
    
    for line in resp.iter_lines():
    if not line:
    continue
    if line.startswith(b"event: "):
    current_event = line[7:].decode()
    elif line.startswith(b"data: "):
    data = json.loads(line[6:].decode())
    events.append({"type": current_event, "data": data})
    event_count += 1
    now = time.time()
            
    # Log progress every 10 seconds
    if now - last_event_time >= 10:
    print(f"    Progress: {event_count} events, {now - start:.0f}s elapsed")
    last_event_time = now
            
    # Log key events
    if current_event in ("assistant_completed", "session_failed", "session_ready"):
    print(f"    Event: {current_event}")
    if current_event == "session_failed":
    print(f"    Error: {json.dumps(data, indent=2)[:200]}")
    session_failed = True
    break  # Stop reading on failure
    
    elapsed = time.time() - start
    print(f"  [3/4] Received {event_count} events in {elapsed:.1f}s")
    if session_failed:
    print("  ⚠️ Session failed — stopping test")
    sys.exit(1)
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

    print("🔵 Extremely Difficult 1: Quantum Computing Enterprise Readiness Plan")
    print(f"  Backend: {BACKEND}")
    print(f"  Test dir: {TEST_DIR}")

    session_id = create_session()
    if not session_id:
    print("FAIL: No session ID returned")
    sys.exit(1)

    prompt = """Write a quantum computing enterprise readiness plan at quantum_computing.md.

    Requirements:
    1. Quantum computing landscape assessment (NISQ era, fault-tolerant timeline, vendor landscape)
    2. Use case identification and prioritization (optimization, simulation, machine learning, cryptography)
    3. Hybrid classical-quantum architecture (quantum-classical workflow, API integration, cloud access)
    4. Workforce development (quantum literacy programs, quantum developer training, academic partnerships)
    5. Security implications (post-quantum cryptography, quantum-safe migration, Y2Q timeline)
    6. Infrastructure strategy (cloud quantum access, on-premise quantum systems, hybrid deployment)
    7. ROI and value realization (quantum advantage timeline, use case ROI, pilot-to-production)

    Write the plan as a markdown document. You MUST include the exact words "NISQ", "post-quantum cryptography", and "quantum advantage" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  [4/4] Checking for file...")

    filepath = "quantum_computing.md"
    if not check_file_exists(filepath, timeout=TIMEOUT):
    print(f"FAIL: File not created within {TIMEOUT}s")
    sys.exit(1)

    content = open(filepath).read()
    content_lower = content.lower()
    print(f"PASS: File created ({len(content)} bytes)")

    all_passed = True
    checks = [
    ("NISQ", "NISQ era assessment"),
    ("post-quantum cryptography", "post-quantum cryptography"),
    ("quantum advantage", "quantum advantage timeline"),
    ("Qiskit", "Qiskit toolchain"),
    ("hybrid", "hybrid classical-quantum"),
    ("patent", "intellectual property"),
    ]
    for keyword, name in checks:
    if keyword.lower() in content_lower:
    print(f"  ✅ {name} found")
    else:
    print(f"  ❌ {name} NOT found")
    all_passed = False

    print(f"Result: {'PASS' if all_passed else 'FAIL'}")
