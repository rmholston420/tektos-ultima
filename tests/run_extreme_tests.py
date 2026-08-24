"""
Run the 5 Extremely Difficult tests one at a time with 120s timeout and extra debugging.
"""
import requests
import json
import os
import time
import sys

BACKEND = "http://localhost:8020"
TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"
TIMEOUT = 120
PROGRESS_INTERVAL = 30


def debug(msg):
    print(f"[DEBUG {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def create_session():
    debug("Creating session...")
    resp = requests.post(f"{BACKEND}/api/sessions", json={
        "model": "Qwen_Qwen3.6-35B-A3B-Q5_K_M",
        "cwd": TEST_DIR,
        "provider": "local",
        "permission_mode": "auto"
    })
    debug(f"Session response status: {resp.status_code}")
    data = resp.json()
    session_id = data.get("session_id") or data.get("id")
    debug(f"Session ID: {session_id}")
    return session_id


def send_prompt(session_id, prompt, timeout=120):
    debug(f"Sending prompt to session {session_id} (timeout={timeout}s)...")
    debug(f"Prompt length: {len(prompt)} chars")
    
    start = time.time()
    resp = requests.post(
        f"{BACKEND}/api/prompt/sse",
        json={"prompt": prompt, "session_id": session_id},
        stream=True,
        timeout=timeout
    )
    debug(f"Response status: {resp.status_code} (took {time.time()-start:.1f}s)")
    
    events = []
    current_event = "unknown"
    event_counts = {}
    
    for line in resp.iter_lines():
        if not line:
            continue
        if line.startswith(b"event: "):
            current_event = line[7:].decode()
            event_counts[current_event] = event_counts.get(current_event, 0) + 1
        elif line.startswith(b"data: "):
            data = json.loads(line[6:].decode())
            events.append({"type": current_event, "data": data})
    
    elapsed = time.time() - start
    debug(f"Received {len(events)} events in {elapsed:.1f}s")
    debug(f"Event types: {json.dumps(event_counts, indent=2)}")
    
    # Show last few events for debugging
    if events:
        debug(f"Last event type: {events[-1]['type']}")
        if events[-1]['type'] == 'assistant':
            content = events[-1]['data'].get('content', '')
            debug(f"Assistant content length: {len(content)} chars")
            if content:
                debug(f"Assistant content preview: {content[:200]}...")
    
    return events


def check_file_exists(filepath, timeout=120):
    start = time.time()
    last_progress = start
    
    while time.time() - start < timeout:
        if os.path.exists(filepath):
            return True
        now = time.time()
        if now - last_progress >= PROGRESS_INTERVAL:
            elapsed = int(now - start)
            remaining = int(timeout - elapsed)
            debug(f"Waiting for file {filepath}... {elapsed}s elapsed, {remaining}s remaining")
            last_progress = now
        time.sleep(5)
    return False


def verify_file(filepath, checks, test_name):
    debug(f"Verifying file: {filepath}")
    if not check_file_exists(filepath, timeout=TIMEOUT):
        print(f"❌ {test_name}: File not created within {TIMEOUT}s")
        return False
    
    content = open(filepath, 'r').read()
    content_lower = content.lower()
    debug(f"File created ({len(content)} bytes)")
    
    all_passed = True
    for keyword, name in checks:
        if keyword.lower() in content_lower:
            debug(f"  ✅ {name} found")
        else:
            debug(f"  ❌ {name} NOT found")
            all_passed = False
    
    return all_passed


# ─── Extremely Difficult Tests ─────────────────────────────────────────────────

def test_quantum_computing():
    debug("=" * 60)
    debug("Extremely Difficult 1: Quantum Computing Enterprise Readiness Plan")
    debug("=" * 60)
    session_id = create_session()
    
    prompt = """Write a quantum computing enterprise readiness plan at /tmp/quantum_computing.md.

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
    return verify_file("/tmp/quantum_computing.md", [
        ("NISQ", "NISQ era assessment"),
        ("post-quantum cryptography", "post-quantum cryptography"),
        ("quantum advantage", "quantum advantage timeline"),
        ("Qiskit", "Qiskit toolchain"),
        ("hybrid", "hybrid classical-quantum"),
        ("patent", "intellectual property"),
    ], "Extremely Difficult 1: Quantum Computing Enterprise Readiness Plan")


def test_megacity():
    debug("=" * 60)
    debug("Extremely Difficult 2: Megacity Smart Infrastructure Plan")
    debug("=" * 60)
    session_id = create_session()
    
    prompt = """Write a megacity smart infrastructure plan at /tmp/megacity_smart.md.

Requirements:
1. Smart city architecture (IoT sensor network, edge computing, cloud platform, data lake)
2. Transportation and mobility (smart traffic, autonomous vehicles, public transit optimization)
3. Energy and utilities (smart grid, demand response, renewable integration, microgrids)
4. Public safety and emergency response (video analytics, gunshot detection, disaster management)
5. Environmental monitoring (air quality, water quality, noise pollution, waste management)
6. Data governance and privacy (data ownership, anonymization, consent management, GDPR)
7. Cybersecurity (critical infrastructure protection, zero trust, incident response)
8. Funding and financing (public-private partnerships, green bonds, impact investing)

Write the plan as a markdown document. You MUST include the exact words "edge computing", "zero trust", and "public-private partnerships" in the content."""
    
    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    return verify_file("/tmp/megacity_smart.md", [
        ("edge computing", "edge computing architecture"),
        ("zero trust", "zero trust security"),
        ("public-private partnerships", "public-private partnerships"),
        ("IoT", "IoT sensor network"),
        ("smart grid", "smart grid energy"),
        ("GDPR", "GDPR data governance"),
    ], "Extremely Difficult 2: Megacity Smart Infrastructure Plan")


def test_data_mesh():
    debug("=" * 60)
    debug("Extremely Difficult 3: Enterprise Data Mesh Implementation Plan")
    debug("=" * 60)
    session_id = create_session()
    
    prompt = """Write an enterprise data mesh implementation plan at /tmp/data_mesh.md.

Requirements:
1. Data mesh principles (domain ownership, data as a product, self-serve platform, federated governance)
2. Domain decomposition (bounded contexts, domain teams, data product ownership)
3. Data product design (schema design, SLA definition, documentation, discoverability)
4. Self-serve data platform (infrastructure, tooling, CI/CD for data, quality gates)
5. Federated computational governance (interoperability standards, security policies, quality metrics)
6. Data quality and observability (data profiling, lineage tracking, anomaly detection, SLA monitoring)
7. Security and access control (RBAC, ABAC, data classification, encryption, audit trails)
8. Organizational transformation (data literacy, domain team empowerment, platform team role)

Write the plan as a markdown document. You MUST include the exact words "data as a product", "federated governance", and "self-serve" in the content."""
    
    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    return verify_file("/tmp/data_mesh.md", [
        ("data as a product", "data as a product principle"),
        ("federated governance", "federated computational governance"),
        ("self-serve", "self-serve data platform"),
        ("domain ownership", "domain decomposition"),
        ("lineage", "lineage tracking"),
        ("ABAC", "ABAC access control"),
    ], "Extremely Difficult 3: Enterprise Data Mesh Implementation Plan")


def test_ma_integration():
    debug("=" * 60)
    debug("Extremely Difficult 4: M&A Technology Integration Plan")
    debug("=" * 60)
    session_id = create_session()
    
    prompt = """Write a merger and acquisition technology integration plan at /tmp/ma_integration.md.

Requirements:
1. Pre-close technology assessment (due diligence, system landscape, integration complexity)
2. Integration strategy (harmonization, best-of-breed, keep separate, phased consolidation)
3. Application portfolio rationalization (duplicate systems, feature overlap, sunset plan)
4. Data migration and consolidation (master data, historical data, data quality, reconciliation)
5. Infrastructure consolidation (data center rationalization, cloud migration, network integration)
6. Security and compliance (access control harmonization, compliance gap analysis, audit alignment)
7. Integration governance (steering committee, workstreams, milestone tracking, risk management)
8. Day-1 readiness (critical systems, communication, support, rollback procedures)

Write the plan as a markdown document. You MUST include the exact words "due diligence", "application portfolio rationalization", and "Day-1" in the content."""
    
    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    return verify_file("/tmp/ma_integration.md", [
        ("due diligence", "pre-close due diligence"),
        ("application portfolio rationalization", "application portfolio rationalization"),
        ("Day-1", "Day-1 readiness"),
        ("master data", "master data migration"),
        ("access control", "access control harmonization"),
        ("steering committee", "integration governance"),
    ], "Extremely Difficult 4: M&A Technology Integration Plan")


def test_fintech():
    debug("=" * 60)
    debug("Extremely Difficult 5: Global Fintech Platform Architecture Plan")
    debug("=" * 60)
    session_id = create_session()
    
    prompt = """Write a global fintech platform architecture plan at /tmp/fintech_platform.md.

Requirements:
1. Platform architecture (microservices, event-driven, API gateway, service mesh)
2. Payment processing (card networks, ACH, wire transfers, real-time payments, crypto)
3. Identity and verification (KYC, AML, biometric authentication, device fingerprinting)
4. Fraud detection and prevention (ML models, rule engines, transaction monitoring, chargeback)
5. Regulatory compliance (PCI DSS, PSD2, Open Banking, local payment regulations)
6. Ledger and accounting (double-entry ledger, reconciliation, audit trail, financial reporting)
7. Scalability and performance (transaction throughput, latency requirements, peak load handling)
8. Disaster recovery and business continuity (multi-region, RTO/RPO, failover testing)

Write the plan as a markdown document. You MUST include the exact words "PCI DSS", "double-entry ledger", and "service mesh" in the content."""
    
    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    return verify_file("/tmp/fintech_platform.md", [
        ("PCI DSS", "PCI DSS compliance"),
        ("double-entry ledger", "double-entry ledger"),
        ("service mesh", "service mesh architecture"),
        ("KYC", "KYC verification"),
        ("fraud detection", "fraud detection"),
        ("multi-region", "multi-region disaster recovery"),
    ], "Extremely Difficult 5: Global Fintech Platform Architecture Plan")


def main():
    print("=" * 60)
    print("Running 5 Extremely Difficult Tests (120s timeout each)")
    print("=" * 60)
    
    # Check backend
    try:
        resp = requests.get(f"{BACKEND}/health", timeout=5)
        resp.raise_for_status()
        health = resp.json()
        print(f"✅ Backend running: LLM={health['llm_url']}, Model={health['llm_model']}")
        print(f"   Active sessions: {health['active_sessions']}")
    except Exception as e:
        print(f"❌ Backend not running: {e}")
        sys.exit(1)
    
    tests = [
        ("Extremely Difficult 1: Quantum Computing", test_quantum_computing),
        ("Extremely Difficult 2: Megacity Smart Infrastructure", test_megacity),
        ("Extremely Difficult 3: Enterprise Data Mesh", test_data_mesh),
        ("Extremely Difficult 4: M&A Technology Integration", test_ma_integration),
        ("Extremely Difficult 5: Global Fintech Platform", test_fintech),
    ]
    
    results = []
    for name, test_func in tests:
        start = time.time()
        try:
            passed = test_func()
            elapsed = time.time() - start
            results.append((name, passed, elapsed))
            print(f"\n{'✅ PASS' if passed else '❌ FAIL'} — {name} ({elapsed:.0f}s)")
        except Exception as e:
            elapsed = time.time() - start
            print(f"\n❌ Test '{name}' raised exception ({elapsed:.0f}s): {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False, elapsed))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    
    for name, result_passed, elapsed in results:
        status = "✅ PASS" if result_passed else "❌ FAIL"
        print(f"  {status} — {name} ({elapsed:.0f}s)")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All extremely difficult tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
