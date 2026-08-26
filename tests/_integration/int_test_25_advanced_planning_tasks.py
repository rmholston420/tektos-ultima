"""
if __name__ == "__main__":
    Tektos-Ultima v1 — 25 Advanced Planning Tasks (5 Very Difficult, 5 Extremely Difficult)

    Very Difficult: Complex multi-phase planning with cross-domain considerations,
    risk analysis, stakeholder management, and compliance requirements.

    Extremely Difficult: Multi-year strategic planning, organizational transformation,
    technical debt remediation at scale, and complex system architecture planning.
    """

    import requests
    import json
    import os
    import time
    import sys

    BACKEND = "http://localhost:8020"
    TEST_DIR = "/home/rmholston/dev/tektos-ultima-v1"
    TIMEOUT = 900
    PROGRESS_INTERVAL = 60


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


    def send_prompt(session_id, prompt, timeout=900):
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


    def check_file_exists(filepath, timeout=900):
    start = time.time()
    last_progress = start
    
    while time.time() - start < timeout:
    if os.path.exists(filepath):
    return True
    now = time.time()
    if now - last_progress >= PROGRESS_INTERVAL:
    elapsed = int(now - start)
    remaining = int(timeout - elapsed)
    print(f"  ⏳ Waiting for file... {elapsed}s elapsed, {remaining}s remaining")
    last_progress = now
    time.sleep(5)
    return False


    def read_file_content(filepath):
    with open(filepath, 'r') as f:
    return f.read()


    def verify_file(filepath, checks, test_name):
    if not check_file_exists(filepath, timeout=TIMEOUT):
    print(f"❌ {test_name}: File not created within {TIMEOUT}s")
    return False
    
    content = read_file_content(filepath)
    content_lower = content.lower()
    print(f"✅ {test_name}: File created ({len(content)} bytes)")
    
    all_passed = True
    for keyword, name in checks:
    if keyword.lower() in content_lower:
    print(f"  ✅ {name} found")
    else:
    print(f"  ❌ {name} NOT found")
    all_passed = False
    
    return all_passed


    # ─── 5 Very Difficult Planning Tasks ─────────────────────────────────────────────






    def test_multi_tenant_saas_architecture_plan():
    """Very Difficult 1: Multi-tenant SaaS architecture and rollout plan."""
    print("\n🟣 Very Difficult 1: Multi-Tenant SaaS Architecture Plan")
    session_id = create_session()
    
    prompt = """Write a comprehensive multi-tenant SaaS architecture and rollout plan at /tmp/multi_tenant_saas.md.

    Requirements:
    1. Tenant isolation strategy (database-per-tenant, schema-per-tenant, or shared schema with row-level security)
    2. Data residency and compliance (GDPR, CCPA, HIPAA, data sovereignty requirements)
    3. Multi-region deployment architecture (active-active, latency optimization, failover)
    4. Billing and subscription management (tiered pricing, usage-based billing, proration)
    5. Tenant onboarding and offboarding lifecycle (provisioning, deprovisioning, data export)
    6. Security model (RBAC, ABAC, SSO/SAML/OIDC integration, audit logging)
    7. Performance isolation guarantees (resource quotas, rate limiting, noisy neighbor prevention)
    8. Rollout strategy (beta tenants, gradual rollout, feature flags per tenant)
    9. Cost model and unit economics (infrastructure cost per tenant, margin analysis)
    10. Keep it concise and practical

    Write the plan as a markdown document. You MUST include the exact words "tenant isolation", "data residency", and "billing" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/multi_tenant_saas.md", [
    ("tenant isolation", "tenant isolation strategy"),
    ("data residency", "data residency compliance"),
    ("billing", "billing management"),
    ("gdpr", "GDPR compliance"),
    ("rbac", "RBAC security model"),
    ("rate limiting", "performance isolation"),
    ], "Very Difficult 1: Multi-Tenant SaaS Architecture Plan")









    def test_enterprise_digital_transformation_plan():
    """Very Difficult 2: Enterprise digital transformation plan."""
    print("\n🟣 Very Difficult 2: Enterprise Digital Transformation Plan")
    session_id = create_session()
    
    prompt = """Write an enterprise digital transformation plan at /tmp/digital_transformation.md.

    Requirements:
    1. Current state assessment (legacy systems, manual processes, organizational silos)
    2. Target operating model (digital-first, data-driven, customer-centric)
    3. Technology modernization (cloud migration, API-first, microservices adoption)
    4. Change management (stakeholder engagement, training programs, resistance mitigation)
    5. Skills gap analysis and workforce transformation (upskilling, reskilling, hiring)
    6. Data and analytics transformation (data lake, self-service BI, advanced analytics)
    7. Customer experience transformation (omnichannel, personalization, journey mapping)
    8. Governance and operating model (decision rights, agile at scale, DevOps culture)
    9. Phased implementation roadmap (quick wins, foundational, transformational)
    10. ROI and value realization framework (KPIs, benefits tracking, continuous improvement)
    11. Keep it concise and practical

    Write the plan as a markdown document. You MUST include the exact words "change management", "skills gap", and "ROI" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/digital_transformation.md", [
    ("legacy systems", "current state assessment"),
    ("change management", "change management"),
    ("skills gap", "skills gap analysis"),
    ("ROI", "ROI and value realization"),
    ("agile", "agile at scale"),
    ("omnichannel", "customer experience"),
    ], "Very Difficult 2: Enterprise Digital Transformation Plan")









    def test_financial_services_regulatory_compliance_plan():
    """Very Difficult 3: Financial services regulatory compliance plan."""
    print("\n🟣 Very Difficult 3: Financial Services Regulatory Compliance Plan")
    session_id = create_session()
    
    prompt = """Write a financial services regulatory compliance plan at /tmp/financial_compliance.md.

    Requirements:
    1. Regulatory landscape mapping (Basel III, Dodd-Frank, MiFID II, PSD2, AML/KYC)
    2. Compliance risk assessment (regulatory risk, operational risk, model risk)
    3. Governance framework (board oversight, compliance committee, three lines of defense)
    4. Policy and procedure development (policy lifecycle, version control, approval workflows)
    5. Monitoring and reporting (regulatory reporting, exception reporting, trend analysis)
    6. Audit management (internal audit, external audit, regulatory examination readiness)
    7. Training and awareness (role-based training, annual certification, phishing simulations)
    8. Technology enablement (regtech solutions, automated monitoring, workflow automation)
    9. Incident response and breach notification (regulatory timelines, communication plans)
    10. Cross-border compliance (jurisdictional mapping, data transfer restrictions)
    11. Keep it concise and practical

    Write the plan as a markdown document. You MUST include the exact words "AML", "three lines of defense", and "regtech" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/financial_compliance.md", [
    ("AML", "AML/KYC compliance"),
    ("three lines of defense", "governance framework"),
    ("regtech", "technology enablement"),
    ("Basel", "regulatory landscape"),
    ("audit", "audit management"),
    ("breach notification", "incident response"),
    ], "Very Difficult 3: Financial Services Regulatory Compliance Plan")









    def test_healthcare_interoperability_plan():
    """Very Difficult 4: Healthcare interoperability and data exchange plan."""
    print("\n🟣 Very Difficult 4: Healthcare Interoperability Plan")
    session_id = create_session()
    
    prompt = """Write a healthcare interoperability and data exchange plan at /tmp/healthcare_interop.md.

    Requirements:
    1. Standards adoption (HL7 FHIR, DICOM, ICD-10, SNOMED CT, LOINC)
    2. Data exchange architecture (APIs, message brokers, event-driven integration)
    3. Patient identity management (master patient index, matching algorithms, deduplication)
    4. Consent and privacy management (patient consent, HIPAA, state-specific regulations)
    5. Clinical data integration (EHR, lab systems, imaging, pharmacy, billing)
    6. Interoperability testing (conformance testing, certification, interoperability labs)
    7. Provider network onboarding (credentialing, directory management, network connectivity)
    8. Patient portal and engagement (patient access, API access, mobile apps)
    9. Analytics and population health (data warehousing, risk stratification, care coordination)
    10. Vendor management and ecosystem (vendor assessment, SLA management, ecosystem governance)
    11. Keep it concise and practical

    Write the plan as a markdown document. You MUST include the exact words "FHIR", "HIPAA", and "master patient index" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/healthcare_interop.md", [
    ("FHIR", "HL7 FHIR standards"),
    ("HIPAA", "HIPAA privacy"),
    ("master patient index", "patient identity management"),
    ("DICOM", "DICOM imaging"),
    ("SNOMED", "SNOMED CT terminology"),
    ("conformance testing", "interoperability testing"),
    ], "Very Difficult 4: Healthcare Interoperability Plan")









    def test_global_supply_chain_resilience_plan():
    """Very Difficult 5: Global supply chain resilience and optimization plan."""
    print("\n🟣 Very Difficult 5: Global Supply Chain Resilience Plan")
    session_id = create_session()
    
    prompt = """Write a global supply chain resilience and optimization plan at /tmp/supply_chain.md.

    Requirements:
    1. Supply chain mapping and visibility (tier 1-3 supplier mapping, risk heat maps)
    2. Demand forecasting and planning (predictive analytics, scenario planning, bullwhip mitigation)
    3. Inventory optimization (safety stock, dynamic reorder points, multi-echelon optimization)
    4. Supplier risk management (financial health monitoring, geopolitical risk, single-source mitigation)
    5. Logistics and transportation optimization (route optimization, carrier management, last-mile)
    6. Manufacturing and production resilience (dual sourcing, nearshoring, flexible capacity)
    7. Technology enablement (IoT tracking, blockchain traceability, digital twin simulation)
    8. Sustainability and ESG (carbon footprint, circular economy, ethical sourcing)
    9. Crisis response and business continuity (disruption scenarios, response playbooks, recovery)
    10. Performance measurement (OTIF, cash-to-cash cycle, supply chain resilience index)
    11. Keep it concise and practical

    Write the plan as a markdown document. You MUST include the exact words "bullwhip", "nearshoring", and "digital twin" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/supply_chain.md", [
    ("bullwhip", "bullwhip effect mitigation"),
    ("nearshoring", "nearshoring strategy"),
    ("digital twin", "digital twin simulation"),
    ("IoT", "IoT tracking"),
    ("blockchain", "blockchain traceability"),
    ("OTIF", "OTIF performance"),
    ], "Very Difficult 5: Global Supply Chain Resilience Plan")


    # ─── 5 Extremely Difficult Planning Tasks ─────────────────────────────────────────






    def test_quantum_computing_enterprise_readiness_plan():
    """Extremely Difficult 1: Quantum computing enterprise readiness and integration plan."""
    print("\n🔵 Extremely Difficult 1: Quantum Computing Enterprise Readiness Plan")
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
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/quantum_computing.md", [
    ("NISQ", "NISQ era assessment"),
    ("post-quantum cryptography", "post-quantum cryptography"),
    ("quantum advantage", "quantum advantage timeline"),
    ("Qiskit", "Qiskit toolchain"),
    ("hybrid", "hybrid classical-quantum"),
    ("patent", "intellectual property"),
    ], "Extremely Difficult 1: Quantum Computing Enterprise Readiness Plan")









    def test_megacity_smart_infrastructure_plan():
    """Extremely Difficult 2: Megacity smart infrastructure and IoT integration plan."""
    print("\n🔵 Extremely Difficult 2: Megacity Smart Infrastructure Plan")
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
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/megacity_smart.md", [
    ("edge computing", "edge computing architecture"),
    ("zero trust", "zero trust security"),
    ("public-private partnerships", "public-private partnerships"),
    ("IoT", "IoT sensor network"),
    ("smart grid", "smart grid energy"),
    ("GDPR", "GDPR data governance"),
    ], "Extremely Difficult 2: Megacity Smart Infrastructure Plan")









    def test_enterprise_data_mesh_implementation_plan():
    """Extremely Difficult 3: Enterprise data mesh implementation and governance plan."""
    print("\n🔵 Extremely Difficult 3: Enterprise Data Mesh Implementation Plan")
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
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/data_mesh.md", [
    ("data as a product", "data as a product principle"),
    ("federated governance", "federated computational governance"),
    ("self-serve", "self-serve data platform"),
    ("domain ownership", "domain decomposition"),
    ("lineage", "lineage tracking"),
    ("ABAC", "ABAC access control"),
    ], "Extremely Difficult 3: Enterprise Data Mesh Implementation Plan")









    def test_merger_acquisition_technology_integration_plan():
    """Extremely Difficult 4: Merger and acquisition technology integration plan."""
    print("\n🔵 Extremely Difficult 4: M&A Technology Integration Plan")
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
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/ma_integration.md", [
    ("due diligence", "pre-close due diligence"),
    ("application portfolio rationalization", "application portfolio rationalization"),
    ("Day-1", "Day-1 readiness"),
    ("master data", "master data migration"),
    ("access control", "access control harmonization"),
    ("steering committee", "integration governance"),
    ], "Extremely Difficult 4: M&A Technology Integration Plan")









    def test_global_fintech_platform_architecture_plan():
    """Extremely Difficult 5: Global fintech platform architecture and compliance plan."""
    print("\n🔵 Extremely Difficult 5: Global Fintech Platform Architecture Plan")
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
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/fintech_platform.md", [
    ("PCI DSS", "PCI DSS compliance"),
    ("double-entry ledger", "double-entry ledger"),
    ("service mesh", "service mesh architecture"),
    ("KYC", "KYC verification"),
    ("fraud detection", "fraud detection"),
    ("multi-region", "multi-region disaster recovery"),
    ], "Extremely Difficult 5: Global Fintech Platform Architecture Plan")


    # ─── Main ──────────────────────────────────────────────────────────────────────

    def main():
    print("=" * 60)
    print("Tektos-Ultima v1 — 25 Advanced Planning Tasks")
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
    # Very Difficult (5)
    ("Very Difficult 1: Multi-Tenant SaaS Architecture", test_multi_tenant_saas_architecture_plan),
    ("Very Difficult 2: Enterprise Digital Transformation", test_enterprise_digital_transformation_plan),
    ("Very Difficult 3: Financial Services Regulatory Compliance", test_financial_services_regulatory_compliance_plan),
    ("Very Difficult 4: Healthcare Interoperability", test_healthcare_interoperability_plan),
    ("Very Difficult 5: Global Supply Chain Resilience", test_global_supply_chain_resilience_plan),
    # Extremely Difficult (5)
    ("Extremely Difficult 1: Quantum Computing Readiness", test_quantum_computing_enterprise_readiness_plan),
    ("Extremely Difficult 2: Megacity Smart Infrastructure", test_megacity_smart_infrastructure_plan),
    ("Extremely Difficult 3: Enterprise Data Mesh", test_enterprise_data_mesh_implementation_plan),
    ("Extremely Difficult 4: M&A Technology Integration", test_merger_acquisition_technology_integration_plan),
    ("Extremely Difficult 5: Global Fintech Platform", test_global_fintech_platform_architecture_plan),
    ]
    
    results = []
    for name, test_func in tests:
    try:
    passed = test_func()
    results.append((name, passed))
    except Exception as e:
    print(f"❌ Test '{name}' raised exception: {e}")
    import traceback
    traceback.print_exc()
    results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    very_difficult = sum(1 for n, p in results[:5] if p)
    extremely_difficult = sum(1 for n, p in results[5:] if p)
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\n  Very Difficult:   {very_difficult}/5")
    print(f"  Extremely Difficult: {extremely_difficult}/5")
    print(f"\n  Total: {passed}/{total} tests passed")
    
    for name, result_passed in results:
    status = "✅ PASS" if result_passed else "❌ FAIL"
    print(f"  {status} — {name}")
    
    if passed == total:
    print("\n🎉 All advanced planning tasks passed!")
    else:
    print(f"\n⚠️  {total - passed} test(s) failed")
    
    return passed == total


    success = main()
    sys.exit(0 if success else 1)
