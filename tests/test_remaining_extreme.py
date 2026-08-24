"""Run remaining 4 Extremely Difficult planning tests with longer timeout and simplified prompts."""
import requests, json, os, time, sys

BACKEND = "http://localhost:8020"
TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"
TIMEOUT = 1800  # 30 minutes

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

def verify_file(filepath, checks, test_name):
    if not check_file_exists(filepath, timeout=TIMEOUT):
        print(f"FAIL {test_name}: File not created within {TIMEOUT}s")
        return False
    
    content = open(filepath).read()
    content_lower = content.lower()
    print(f"PASS {test_name}: File created ({len(content)} bytes)")
    
    all_passed = True
    for keyword, name in checks:
        if keyword.lower() in content_lower:
            print(f"  {name} found")
        else:
            print(f"  {name} NOT found")
            all_passed = False
    
    return all_passed

# Extremely Difficult 2: Megacity Smart Infrastructure (simplified)
def test_megacity():
    print("\n🔵 Extremely Difficult 2: Megacity Smart Infrastructure Plan")
    session_id = create_session()
    
    prompt = """Write a megacity smart infrastructure plan at /tmp/megacity_smart.md.

Requirements:
1. Smart city architecture (IoT sensor network, edge computing, cloud platform)
2. Transportation and mobility (smart traffic, autonomous vehicles, public transit)
3. Energy and utilities (smart grid, demand response, renewable integration)
4. Public safety and emergency response (video analytics, disaster management)
5. Environmental monitoring (air quality, water quality, waste management)
6. Data governance and privacy (data ownership, anonymization, GDPR)
7. Cybersecurity (critical infrastructure protection, zero trust)
8. Funding and financing (public-private partnerships, green bonds)

Write the plan as a markdown document. You MUST include the exact words edge computing, zero trust, and public-private partnerships in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  Received {len(events)} events")
    
    return verify_file("/tmp/megacity_smart.md", [
        ("edge computing", "edge computing architecture"),
        ("zero trust", "zero trust security"),
        ("public-private partnerships", "public-private partnerships"),
        ("IoT", "IoT sensor network"),
        ("smart grid", "smart grid energy"),
        ("GDPR", "GDPR data governance"),
    ], "Extremely Difficult 2: Megacity Smart Infrastructure Plan")

# Extremely Difficult 3: Enterprise Data Mesh (simplified)
def test_data_mesh():
    print("\n🔵 Extremely Difficult 3: Enterprise Data Mesh Implementation Plan")
    session_id = create_session()
    
    prompt = """Write an enterprise data mesh implementation plan at /tmp/data_mesh.md.

Requirements:
1. Data mesh principles (domain ownership, data as a product, self-serve platform)
2. Domain decomposition (bounded contexts, domain teams, data product ownership)
3. Data product design (schema design, SLA definition, documentation)
4. Self-serve data platform (infrastructure, tooling, CI/CD for data)
5. Federated computational governance (interoperability standards, security policies)
6. Data quality and observability (data profiling, lineage tracking, SLA monitoring)
7. Security and access control (RBAC, ABAC, data classification, encryption)
8. Organizational transformation (data literacy, domain team empowerment)

Write the plan as a markdown document. You MUST include the exact words data as a product, federated governance, and self-serve in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  Received {len(events)} events")
    
    return verify_file("/tmp/data_mesh.md", [
        ("data as a product", "data as a product principle"),
        ("federated governance", "federated computational governance"),
        ("self-serve", "self-serve data platform"),
        ("domain ownership", "domain decomposition"),
        ("lineage", "lineage tracking"),
        ("ABAC", "ABAC access control"),
    ], "Extremely Difficult 3: Enterprise Data Mesh Implementation Plan")

# Extremely Difficult 4: M&A Technology Integration (simplified)
def test_ma_integration():
    print("\n🔵 Extremely Difficult 4: M&A Technology Integration Plan")
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
    
    return verify_file("/tmp/ma_integration.md", [
        ("due diligence", "pre-close due diligence"),
        ("application portfolio rationalization", "application portfolio rationalization"),
        ("Day-1", "Day-1 readiness"),
        ("master data", "master data migration"),
        ("access control", "access control harmonization"),
        ("steering committee", "integration governance"),
    ], "Extremely Difficult 4: M&A Technology Integration Plan")

# Extremely Difficult 5: Global Fintech Platform (simplified)
def test_fintech():
    print("\n🔵 Extremely Difficult 5: Global Fintech Platform Architecture Plan")
    session_id = create_session()
    
    prompt = """Write a global fintech platform architecture plan at /tmp/fintech_platform.md.

Requirements:
1. Platform architecture (microservices, event-driven, API gateway, service mesh)
2. Payment processing (card networks, ACH, wire transfers, real-time payments)
3. Identity and verification (KYC, AML, biometric authentication, device fingerprinting)
4. Fraud detection and prevention (ML models, rule engines, transaction monitoring)
5. Regulatory compliance (PCI DSS, PSD2, Open Banking, local payment regulations)
6. Ledger and accounting (double-entry ledger, reconciliation, audit trail)
7. Scalability and performance (transaction throughput, latency requirements)
8. Disaster recovery and business continuity (multi-region, RTO/RPO, failover testing)

Write the plan as a markdown document. You MUST include the exact words PCI DSS, double-entry ledger, and service mesh in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  Received {len(events)} events")
    
    return verify_file("/tmp/fintech_platform.md", [
        ("PCI DSS", "PCI DSS compliance"),
        ("double-entry ledger", "double-entry ledger"),
        ("service mesh", "service mesh architecture"),
        ("KYC", "KYC verification"),
        ("fraud detection", "fraud detection"),
        ("multi-region", "multi-region disaster recovery"),
    ], "Extremely Difficult 5: Global Fintech Platform Architecture Plan")

# Main
print("=" * 60)
print("Tektos-Ultima v1 — Remaining 4 Extremely Difficult Planning Tests")
print("Timeout: 1800s (30 minutes)")
print("=" * 60)

# Check backend
try:
    resp = requests.get(f"{BACKEND}/health", timeout=5)
    resp.raise_for_status()
    health = resp.json()
    print(f"Backend running: LLM={health['llm_url']}, Model={health['llm_model']}")
except Exception as e:
    print(f"Backend not running: {e}")
    sys.exit(1)

tests = [
    ("Extremely Difficult 2: Megacity Smart Infrastructure", test_megacity),
    ("Extremely Difficult 3: Enterprise Data Mesh", test_data_mesh),
    ("Extremely Difficult 4: M&A Technology Integration", test_ma_integration),
    ("Extremely Difficult 5: Global Fintech Platform", test_fintech),
]

results = []
for name, test_func in tests:
    try:
        passed = test_func()
        results.append((name, passed))
    except Exception as e:
        print(f"FAIL Test '{name}' raised exception: {e}")
        import traceback
        traceback.print_exc()
        results.append((name, False))

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

passed = sum(1 for _, p in results if p)
total = len(results)

print(f"\n  Total: {passed}/{total} tests passed")

for name, result_passed in results:
    status = "PASS" if result_passed else "FAIL"
    print(f"  {status} — {name}")

if passed == total:
    print("\nAll remaining Extremely Difficult tests passed!")
else:
    print(f"\n{total - passed} test(s) failed")
