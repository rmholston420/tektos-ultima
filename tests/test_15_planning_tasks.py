"""
Tektos-Ultima v1 — 15 Planning Tasks (5 Easy, 5 Medium, 5 Hard)

Planning tasks test Tektos's ability to reason about projects, strategies,
and documentation rather than generate executable code.
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


# ─── 5 Easy Planning Tasks ─────────────────────────────────────────────────────

def test_daily_standup_plan():
    """Easy 1: Daily standup meeting plan."""
    print("\n🟢 Easy 1: Daily Standup Plan")
    session_id = create_session()
    
    prompt = """Write a daily standup meeting plan at /tmp/standup_plan.md.

Requirements:
1. Include a section explicitly titled "Yesterday" with the heading "Yesterday"
2. Include a section explicitly titled "Today" with the heading "Today"
3. Include a section explicitly titled "Blockers" with the heading "Blockers"
4. Add time allocations for each section
5. Include a template for team members to fill out
6. Add tips for keeping standups under 15 minutes
7. Keep it concise and practical

Write the plan as a markdown document. You MUST include the exact words "Yesterday", "Today", and "Blockers" as section headings."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/standup_plan.md", [
        ("yesterday", "yesterday section"),
        ("today", "today section"),
        ("blocker", "blockers section"),
        ("15", "time limit reference"),
        ("template", "team template"),
    ], "Easy 1: Daily Standup Plan")


def test_onboarding_checklist():
    """Easy 2: New developer onboarding checklist."""
    print("\n🟢 Easy 2: Developer Onboarding Checklist")
    session_id = create_session()
    
    prompt = """Write a new developer onboarding checklist at /tmp/onboarding.md.

Requirements:
1. Day 1 tasks (setup, introductions, environment)
2. Week 1 tasks (repo access, first PR, documentation)
3. Month 1 goals (independent work, code review participation)
4. Include a mentor assignment section
5. Keep it concise and practical

Write the checklist as a markdown document."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/onboarding.md", [
        ("Day 1", "Day 1 tasks"),
        ("Week 1", "Week 1 tasks"),
        ("Month 1", "Month 1 goals"),
        ("mentor", "mentor assignment"),
        ("PR", "pull request reference"),
    ], "Easy 2: Developer Onboarding Checklist")


def test_release_checklist():
    """Easy 3: Software release checklist."""
    print("\n🟢 Easy 3: Release Checklist")
    session_id = create_session()
    
    prompt = """Write a software release checklist at /tmp/release_checklist.md.

Requirements:
1. Pre-release steps (code freeze, testing, documentation)
2. Release day steps (deployment, monitoring, rollback plan)
3. Post-release steps (verification, communication, retrospective)
4. Include a rollback procedure
5. Keep it concise and practical

Write the checklist as a markdown document. You MUST include the exact word "monitoring" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/release_checklist.md", [
        ("pre-release", "pre-release steps"),
        ("deployment", "deployment steps"),
        ("rollback", "rollback procedure"),
        ("monitoring", "monitoring steps"),
        ("post-release", "post-release steps"),
    ], "Easy 3: Release Checklist")


def test_git_branching_strategy():
    """Easy 4: Git branching strategy document."""
    print("\n🟢 Easy 4: Git Branching Strategy")
    session_id = create_session()
    
    prompt = """Write a Git branching strategy document at /tmp/git_strategy.md.

Requirements:
1. Define branch types (main, develop, feature, hotfix, release)
2. Explain when to create each branch type
3. Describe merge workflow (PR, review, squash)
4. Include naming conventions for branches
5. Keep it concise and practical

Write the document as a markdown file."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/git_strategy.md", [
        ("main", "main branch"),
        ("develop", "develop branch"),
        ("feature", "feature branch"),
        ("hotfix", "hotfix branch"),
        ("PR", "pull request workflow"),
    ], "Easy 4: Git Branching Strategy")


def test_code_review_guidelines():
    """Easy 5: Code review guidelines."""
    print("\n🟢 Easy 5: Code Review Guidelines")
    session_id = create_session()
    
    prompt = """Write code review guidelines at /tmp/code_review.md.

Requirements:
1. Include a reviewer checklist covering functionality, style, security, and performance
2. Include reviewer etiquette guidelines (constructive feedback, timely responses)
3. Include author responsibilities (self-review, documentation, tests)
4. Include a sample review comment format
5. Keep it concise and practical

Write the guidelines as a markdown document. You MUST include the exact words "checklist" and "etiquette" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/code_review.md", [
        ("checklist", "reviewer checklist"),
        ("functionality", "functionality review"),
        ("security", "security review"),
        ("etiquette", "reviewer etiquette"),
        ("author", "author responsibilities"),
    ], "Easy 5: Code Review Guidelines")


# ─── 5 Medium Planning Tasks ───────────────────────────────────────────────────

def test_api_migration_plan():
    """Medium 1: API version migration plan."""
    print("\n🟡 Medium 1: API Migration Plan")
    session_id = create_session()
    
    prompt = """Write an API version migration plan at /tmp/api_migration.md.

Requirements:
1. Include a "Current State Analysis" section analyzing v1 endpoints, dependencies, and usage stats
2. Include a "Parallel Run" strategy with feature flags and gradual rollout
3. Include a deprecation timeline (announcement, sunset dates, support period)
4. Include a client communication plan (changelog, migration guide, support)
5. Include rollback procedures and risk mitigation
6. Keep it concise and practical

Write the plan as a markdown document. You MUST include the exact phrases "current state" and "parallel" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/api_migration.md", [
        ("current state", "current state analysis"),
        ("parallel", "parallel run strategy"),
        ("deprecation", "deprecation timeline"),
        ("changelog", "changelog/migration guide"),
        ("rollback", "rollback procedures"),
    ], "Medium 1: API Migration Plan")


def test_database_migration_plan():
    """Medium 2: Database schema migration plan."""
    print("\n🟡 Medium 2: Database Migration Plan")
    session_id = create_session()
    
    prompt = """Write a database schema migration plan at /tmp/db_migration.md.

Requirements:
1. Include a schema changes overview (new tables, column changes, indexes)
2. Include a "Zero-Downtime" migration approach with backward-compatible changes
3. Include ETL data migration steps with validation and rollback data
4. Include a testing strategy (staging, canary, production validation)
5. Include a rollback plan and monitoring procedures
6. Keep it concise and practical

Write the plan as a markdown document. You MUST include the exact phrases "zero-downtime" and "ETL" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/db_migration.md", [
        ("schema", "schema changes"),
        ("zero-downtime", "zero-downtime approach"),
        ("ETL", "data migration"),
        ("staging", "staging testing"),
        ("rollback", "rollback plan"),
    ], "Medium 2: Database Migration Plan")


def test_incident_response_plan():
    """Medium 3: Incident response plan."""
    print("\n🟡 Medium 3: Incident Response Plan")
    session_id = create_session()
    
    prompt = """Write an incident response plan at /tmp/incident_response.md.

Requirements:
1. Define severity levels (P0-P3) with definitions and response times
2. Define roles including an "Incident Commander" role with responsibilities
3. Include escalation procedures and contact list
4. Include communication templates (status page, internal updates, customer emails)
5. Include a post-incident retrospective process with action items
6. Keep it concise and practical

Write the plan as a markdown document. You MUST include the exact words "commander", "escalation", and "retrospective" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/incident_response.md", [
        ("P0", "severity levels"),
        ("commander", "incident commander"),
        ("escalation", "escalation procedures"),
        ("status page", "status page communication"),
        ("retrospective", "post-incident review"),
    ], "Medium 3: Incident Response Plan")


def test_microservice_decomposition_plan():
    """Medium 4: Monolith to microservices decomposition plan."""
    print("\n🟡 Medium 4: Microservice Decomposition Plan")
    session_id = create_session()
    
    prompt = """Write a monolith-to-microservices decomposition plan at /tmp/microservices.md.

Requirements:
1. Include a current monolith analysis (modules, dependencies, data flows)
2. Define service boundaries using domain-driven design and bounded contexts
3. Include a "Strangler Fig" migration strategy with incremental extraction
4. Define inter-service communication (API gateway, message queue, events)
5. Include data migration strategy (database per service, eventual consistency)
6. Keep it concise and practical

Write the plan as a markdown document. You MUST include the exact words "strangler", "API gateway", and "database per service" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/microservices.md", [
        ("monolith", "monolith analysis"),
        ("bounded context", "service boundaries"),
        ("strangler", "strangler fig pattern"),
        ("API gateway", "API gateway"),
        ("database per service", "data migration"),
    ], "Medium 4: Microservice Decomposition Plan")


def test_security_audit_plan():
    """Medium 5: Security audit plan."""
    print("\n🟡 Medium 5: Security Audit Plan")
    session_id = create_session()
    
    prompt = """Write a security audit plan at /tmp/security_audit.md.

Requirements:
1. Define scope (applications, infrastructure, data, third-party)
2. Include assessment methodology (OWASP Top 10, penetration testing, code review)
3. Define vulnerability categories (authentication, authorization, data protection)
4. Define remediation priorities (CVSS scoring, business impact)
5. Define reporting format and stakeholder communication
6. Keep it concise and practical

Write the plan as a markdown document. You MUST include the exact word "penetration" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/security_audit.md", [
        ("scope", "scope definition"),
        ("OWASP", "OWASP methodology"),
        ("penetration", "penetration testing"),
        ("CVSS", "vulnerability scoring"),
        ("remediation", "remediation priorities"),
    ], "Medium 5: Security Audit Plan")


# ─── 5 Hard Planning Tasks ─────────────────────────────────────────────────────

def test_cloud_migration_plan():
    """Hard 1: On-premise to cloud migration plan."""
    print("\n🔴 Hard 1: Cloud Migration Plan")
    session_id = create_session()
    
    prompt = """Write a comprehensive on-premise to cloud migration plan at /tmp/cloud_migration.md.

Requirements:
1. Assessment phase (inventory, dependency mapping, cost analysis, TCO comparison)
2. Migration strategy (6 Rs: rehost, replatform, refactor, rebuild, replace, retain)
3. Phased rollout plan (non-production, staging, production by service)
4. Data migration (databases, file storage, backup/restore procedures)
5. Security and compliance (IAM, encryption, audit logging, compliance frameworks)
6. Cost optimization (reserved instances, auto-scaling, monitoring)
7. Rollback procedures and risk mitigation
8. Keep it concise and practical

Write the plan as a markdown document."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/cloud_migration.md", [
        ("assessment", "assessment phase"),
        ("6 Rs", "migration strategies"),
        ("phased", "phased rollout"),
        ("IAM", "security/IAM"),
        ("cost", "cost optimization"),
        ("rollback", "rollback procedures"),
    ], "Hard 1: Cloud Migration Plan")


def test_platform_engineering_plan():
    """Hard 2: Internal developer platform (IDP) plan."""
    print("\n🔴 Hard 2: Internal Developer Platform Plan")
    session_id = create_session()
    
    prompt = """Write an internal developer platform (IDP) plan at /tmp/idp_plan.md.

Requirements:
1. Define platform vision and goals (developer experience, self-service, standardization)
2. Define core services (CI/CD, service catalog, golden paths, infrastructure provisioning)
3. Define architecture (backstage-style portal, API-first, plugin ecosystem)
4. Define implementation phases (MVP, beta, general availability)
5. Define adoption strategy (training, documentation, feedback loops, metrics)
6. Define governance (standards, compliance, cost management, security)
7. Keep it concise and practical

Write the plan as a markdown document. You MUST include the exact words "phases" and "governance" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/idp_plan.md", [
        ("vision", "platform vision"),
        ("CI/CD", "CI/CD services"),
        ("catalog", "service catalog"),
        ("phases", "implementation phases"),
        ("adoption", "adoption strategy"),
        ("governance", "governance"),
    ], "Hard 2: Internal Developer Platform Plan")


def test_disaster_recovery_plan():
    """Hard 3: Multi-region disaster recovery plan."""
    print("\n🔴 Hard 3: Disaster Recovery Plan")
    session_id = create_session()
    
    prompt = """Write a multi-region disaster recovery plan at /tmp/dr_plan.md.

Requirements:
1. RTO/RPO definitions per service tier (critical, important, standard)
2. Current architecture analysis (single region, dependencies, data replication)
3. Target architecture (active-passive or active-active, DNS failover)
4. Data replication strategy (synchronous vs asynchronous, cross-region)
5. Failover procedures (automated triggers, manual override, validation)
6. Failback procedures (data sync, traffic cutover, verification)
7. Testing schedule (quarterly drills, tabletop exercises)
8. Keep it concise and practical

Write the plan as a markdown document."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/dr_plan.md", [
        ("RTO", "RTO/RPO definitions"),
        ("failover", "failover procedures"),
        ("failback", "failback procedures"),
        ("replication", "data replication"),
        ("drill", "testing schedule"),
        ("active", "active-passive/active-active"),
    ], "Hard 3: Disaster Recovery Plan")


def test_observability_implementation_plan():
    """Hard 4: Observability platform implementation plan."""
    print("\n🔴 Hard 4: Observability Implementation Plan")
    session_id = create_session()
    
    prompt = """Write an observability platform implementation plan at /tmp/observability.md.

Requirements:
1. Current state assessment (logging, metrics, tracing gaps)
2. Three pillars implementation (logs: structured logging, metrics: Prometheus, traces: Jaeger)
3. Alerting strategy (SLOs, error budgets, alert rules, notification channels)
4. Dashboard design (executive, operational, service-level views)
5. Data retention and cost management (hot/warm/cold storage, aggregation)
6. Integration plan (existing tools, custom exporters, log agents)
7. Keep it concise and practical

Write the plan as a markdown document."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/observability.md", [
        ("logs", "logging implementation"),
        ("metrics", "metrics/Prometheus"),
        ("traces", "tracing/Jaeger"),
        ("SLO", "SLOs/alerting"),
        ("dashboard", "dashboard design"),
        ("retention", "data retention"),
    ], "Hard 4: Observability Implementation Plan")


def test_ai_integration_plan():
    """Hard 5: AI/ML feature integration plan."""
    print("\n🔴 Hard 5: AI/ML Integration Plan")
    session_id = create_session()
    
    prompt = """Write an AI/ML feature integration plan at /tmp/ai_integration.md.

Requirements:
1. Include use case identification (recommendations, classification, generation, prediction)
2. Include model selection criteria (accuracy, latency, cost, interpretability, licensing)
3. Include a data pipeline (collection, labeling, training, validation, versioning)
4. Include a serving architecture (batch vs real-time, model registry, A/B testing)
5. Include monitoring for data drift, concept drift, performance degradation, feedback loops
6. Include ethical considerations (bias detection, fairness, privacy, human oversight)
7. Include a rollout strategy (canary, feature flags, gradual expansion)
8. Keep it concise and practical

Write the plan as a markdown document. You MUST include the exact words "use case", "serving", and "ethical" in the content."""

    events = send_prompt(session_id, prompt, timeout=TIMEOUT)
    print(f"  ℹ️  Received {len(events)} events")
    
    return verify_file("/tmp/ai_integration.md", [
        ("use case", "use case identification"),
        ("model", "model selection"),
        ("pipeline", "data pipeline"),
        ("serving", "serving architecture"),
        ("drift", "monitoring/data drift"),
        ("ethical", "ethical considerations"),
        ("rollout", "rollout strategy"),
    ], "Hard 5: AI/ML Integration Plan")


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Tektos-Ultima v1 — 15 Planning Tasks")
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
        # Easy (5)
        ("Easy 1: Daily Standup Plan", test_daily_standup_plan),
        ("Easy 2: Developer Onboarding Checklist", test_onboarding_checklist),
        ("Easy 3: Release Checklist", test_release_checklist),
        ("Easy 4: Git Branching Strategy", test_git_branching_strategy),
        ("Easy 5: Code Review Guidelines", test_code_review_guidelines),
        # Medium (5)
        ("Medium 1: API Migration Plan", test_api_migration_plan),
        ("Medium 2: Database Migration Plan", test_database_migration_plan),
        ("Medium 3: Incident Response Plan", test_incident_response_plan),
        ("Medium 4: Microservice Decomposition Plan", test_microservice_decomposition_plan),
        ("Medium 5: Security Audit Plan", test_security_audit_plan),
        # Hard (5)
        ("Hard 1: Cloud Migration Plan", test_cloud_migration_plan),
        ("Hard 2: Internal Developer Platform Plan", test_platform_engineering_plan),
        ("Hard 3: Disaster Recovery Plan", test_disaster_recovery_plan),
        ("Hard 4: Observability Implementation Plan", test_observability_implementation_plan),
        ("Hard 5: AI/ML Integration Plan", test_ai_integration_plan),
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
    
    easy = sum(1 for n, p in results[:5] if p)
    medium = sum(1 for n, p in results[5:10] if p)
    hard = sum(1 for n, p in results[10:] if p)
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\n  Easy:   {easy}/5")
    print(f"  Medium: {medium}/5")
    print(f"  Hard:   {hard}/5")
    print(f"\n  Total: {passed}/{total} tests passed")
    
    for name, result_passed in results:
        status = "✅ PASS" if result_passed else "❌ FAIL"
        print(f"  {status} — {name}")
    
    if passed == total:
        print("\n🎉 All planning tasks passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
