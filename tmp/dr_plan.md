# Multi-Region Disaster Recovery Plan

**Version:** 1.0  
**Last Updated:** 2026-08-21  
**Owner:** Platform Engineering  
**Classification:** Internal — Confidential

---

## 1. Service Tiers & RTO/RPO Definitions

| Tier | Criteria | RTO | RPO | Examples |
|------|----------|-----|-----|----------|
| **Critical** | Revenue-generating, core user-facing services, compliance-bound | ≤ 15 min | ≤ 5 min | API Gateway, Auth Service, Payment Processing |
| **Important** | Business-essential, moderate user impact if down | ≤ 1 hour | ≤ 15 min | User Profile Service, Notification Service, Search Index |
| **Standard** | Internal tools, batch jobs, non-urgent analytics | ≤ 4 hours | ≤ 1 hour | Reporting Dashboard, Log Aggregator, Batch Processors |

> **RTO (Recovery Time Objective):** Maximum acceptable downtime.  
> **RPO (Recovery Point Objective):** Maximum acceptable data loss.

---

## 2. Current Architecture Analysis

### 2.1 Deployment Model
- **Single-region deployment** in `us-east-1`
- All production workloads run in one Availability Zone cluster
- No active second region; `eu-west-1` exists as a read-only analytics copy

### 2.2 Key Dependencies
| Dependency | Current State | Risk |
|------------|---------------|------|
| DNS (Route 53) | Single hosted zone in `us-east-1` | Single point of failure for traffic routing |
| Database (RDS PostgreSQL) | Primary in `us-east-1a`, read replicas in `us-east-1b/c` | No cross-region replica; failover limited to AZ |
| S3 | `us-east-1` | No cross-region replication configured |
| Cache (ElastiCache Redis) | `us-east-1` cluster | No cross-region replication |
| CDN (CloudFront) | Edge-only; origin in `us-east-1` | Serves stale data if origin is unreachable |
| Message Queue (SQS/SNS) | `us-east-1` | No cross-region queue sync |
| Secrets (Secrets Manager) | `us-east-1` | No cross-region replication |

### 2.3 Current Data Replication
- **Database:** Intra-AZ read replicas only — no cross-region data copy
- **S3:** No cross-region replication
- **Backups:** Nightly snapshots to `us-east-1`; 7-day retention
- **No DR automation** — manual recovery documented but never tested

### 2.4 Identified Gaps
- Zero cross-region redundancy for tier-1 services
- No automated failover mechanism
- RTO estimates based on manual recovery (~4–8 hours) exceed all tier targets
- No documented, tested failback process

---

## 3. Target Architecture

### 3.1 Model: Active-Passive with Hot Standby

```
                    ┌──────────────────────────────────┐
                    │         DNS (Route 53)            │
                    │   Health-check based routing      │
                    └──────┬───────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
    ┌──────────────────┐    ┌──────────────────┐
    │   PRIMARY        │    │   SECONDARY      │
    │   us-east-1      │    │   us-west-2      │
    │   (Active)       │    │   (Hot Standby)  │
    │                  │    │                  │
    │  API Gateway     │    │  API Gateway     │
    │  App Servers     │    │  App Servers     │
    │  RDS Primary     │    │  RDS Replica     │
    │  S3 + CRR        │    │  S3 (synced)     │
    │  ElastiCache     │    │  ElastiCache     │
    │  SQS/SNS         │    │  SQS/SNS         │
    └──────────────────┘    └──────────────────┘
```

### 3.2 Key Design Decisions
- **Active-Passive** chosen over Active-Active to simplify data consistency and avoid split-brain scenarios
- **Hot standby:** Secondary region runs all services in idle/replica mode with warm connections
- **DNS failover:** Route 53 health checks drive traffic routing (TTL ≤ 60s)
- **Secondary is production-grade:** Same instance types, same configurations — just not receiving live traffic

---

## 4. Data Replication Strategy

### 4.1 Database Replication

| Database | Strategy | Direction | Notes |
|----------|----------|-----------|-------|
| RDS PostgreSQL | Cross-region read replica | `us-east-1` → `us-west-2` | Async replication (~1–5s lag) |
| Aurora | Global Database | `us-east-1` → `us-west-2` | Async, ~1s lag, promotes in <1 min |
| DynamoDB | Global Tables | Bi-directional | Multi-master, eventual consistency |
| ElastiCache Redis | Global Datastore | `us-east-1` → `us-west-2` | Async, warm standby |

**RPO Impact:**
- Critical tier: Aurora Global Database (~1s lag) meets ≤5 min RPO
- Important tier: RDS cross-region replica (~1–5s lag) meets ≤15 min RPO
- Standard tier: Nightly cross-region snapshot + WAL archiving meets ≤1 hour RPO

### 4.2 Object Storage (S3)
- **Cross-Region Replication (CRR)** enabled on all production buckets
- Replicates to `us-west-2` with versioning
- Replication time: typically < 15 seconds

### 4.3 Message Queues
- **SQS:** Duplicate queues in `us-west-2`; producer duplicates messages to both regions
- **SNS:** Topic replication via cross-region subscription

### 4.4 Secrets & Configuration
- **Secrets Manager:** Replicate critical secrets to `us-west-2`
- **SSM Parameter Store:** Cross-region read access for secondary
- **Infrastructure as Code:** All resources defined in Terraform; secondary region is a `tf apply` away

---

## 5. Failover Procedures

### 5.1 Automated Triggers

| Trigger | Source | Action |
|---------|--------|--------|
| Region health check fails | Route 53 (3 consecutive failures over 60s) | Initiate DNS failover |
| Database primary unreachable | CloudWatch alarm (DBStatusCheckFailed ≥ 3 min) | Promote secondary replica |
| API Gateway circuit breaker trips | App-level health endpoint (3 failures) | Route to secondary |
| Load balancer unhealthy | ELB health checks (5 consecutive failures) | De-register, failover DNS |

### 5.2 Failover Runbook (Automated + Manual)

```
Phase 1 — Detection & Decision (0–5 min)
├─ CloudWatch alarms fire → PagerDuty incident created
├─ SRE on-call acknowledges within 5 min
├─ If automated failover configured → proceed to Phase 2
└─ If manual → On-call leads incident bridge, declares failover

Phase 2 — Database Failover (5–10 min)
├─ Promote Aurora/RDS read replica in us-west-2 to primary
├─ Verify promotion: check replica lag, run SELECT 1
├─ Update connection strings via SSM/Secrets Manager
└─ Confirm app servers reconnect to new primary

Phase 3 — Traffic Cutover (10–15 min)
├─ Update Route 53 record sets: primary → us-west-2
├─ Set TTL to 60s for rapid propagation
├─ Monitor CloudFront invalidation (purge stale cache)
└─ Verify DNS propagation (dig, nslookup from multiple locations)

Phase 4 — Validation (15–30 min)
├─ Smoke tests: health endpoints, login, payment flow
├─ Check error rates (target: < 1% within 5 min of cutover)
├─ Verify data integrity: row counts, checksums on critical tables
├─ Notify stakeholders (status page, Slack #incident)
└─ Declare failover complete
```

### 5.3 Manual Override
- **Pre-approved:** On-call SRE can bypass automation via runbook
- **Safeguards:** Require two-person verification for database promotion
- **Rollback button:** Route 53 record can be reverted to primary at any time
- **Escalation:** If automated failover fails to complete within 15 min, escalate to VP of Engineering

---

## 6. Failback Procedures

### 6.1 Prerequisites for Failback
- Original primary region (`us-east-1`) is fully operational
- All root causes of the original failure are resolved
- Post-incident review completed
- Change window approved (prefer off-peak hours)

### 6.2 Failback Runbook

```
Phase 1 — Preparation (Day of decision)
├─ Stand up full secondary environment in us-east-1 (promoted from old secondary)
├─ Verify all services running and healthy
├─ Begin data synchronization from new primary (us-west-2) → us-east-1
│   └─ For databases: create new cross-region read replica in us-east-1
│   └─ For S3: enable CRR from us-west-2 to us-east-1
├─ Monitor replication lag (target: < 5 min before cutover)

Phase 2 — Data Sync Verification (12–24 hours)
├─ Run reconciliation checks: row counts, checksums, spot-check data
├─ Verify application can read from new primary with acceptable latency
├─ Keep us-west-2 as primary; us-east-1 as warm standby for failback

Phase 3 — Traffic Cutover (Scheduled window)
├─ Update Route 53: traffic → us-east-1
├─ Set TTL to 60s
├─ Monitor DNS propagation and error rates
├─ Validate: smoke tests, user-facing flows, data writes
└─ If issues detected → revert DNS to us-west-2 immediately

Phase 4 — Post-Failback Verification (24–48 hours)
├─ Monitor error rates, latency, and throughput vs. baseline
├─ Verify all integrations (payments, auth, third-party APIs) working
├─ Re-establish replication: us-east-1 → us-west-2 for next DR
├─ Update runbooks and architecture diagrams
└─ Conduct post-failback review
```

### 6.3 Data Consistency Safeguards
- **Dual-write mode:** During transition, apps write to both regions for 24 hours
- **Reconciliation script:** Automated daily check comparing key metrics between regions
- **Rollback window:** Can revert to secondary within 48 hours if issues arise

---

## 7. Testing Schedule

### 7.1 Quarterly DR Drills

| Quarter | Drill Type | Scope | Success Criteria |
|---------|-----------|-------|------------------|
| Q1 | Tabletop exercise | Critical tier only | All stakeholders participate; gaps identified and tracked |
| Q2 | Automated failover test | Critical + Important tiers | RTO met, RPO within bounds, zero data corruption |
| Q3 | Full failover + failback | All tiers end-to-end | Complete cycle within 2× target RTO |
| Q4 | Surprise drill | Critical tier, unannounced | Detection < 5 min, failover < RTO |

### 7.2 Monthly Checks
- Verify cross-region replication health (lag, errors)
- Run DNS failover simulation (without actual cutover)
- Validate backup integrity (restore from snapshot in secondary region)
- Review and update runbooks

### 7.3 Annual Review
- Reassess service tier classifications
- Update RTO/RPO targets based on business changes
- Review and update architecture diagrams
- Full budget review for DR infrastructure costs
- Compliance audit (SOC 2, ISO 27001 if applicable)

### 7.4 Testing Governance
- All drills documented with timestamps and results
- Failed drills tracked in Jira with remediation deadlines
- Results shared with leadership quarterly
- Lessons learned incorporated into next quarter's plan

---

## 8. Appendices

### A. Contact Roster
| Role | Primary | Secondary |
|------|---------|-----------|
| SRE On-Call | @sre-oncall | pagerduty-escalation |
| DBA On-Call | @dba-oncall | pagerduty-escalation |
| VP Engineering | [name] | [name] |
| CTO | [name] | [name] |

### B. Key Metrics to Monitor
- Cross-region replication lag (database, S3)
- Route 53 health check status
- Secondary region service health (CPU, memory, connections)
- DNS propagation time during failover
- End-to-end latency post-failover

### C. Glossary
- **RTO:** Recovery Time Objective — max acceptable downtime
- **RPO:** Recovery Point Objective — max acceptable data loss
- **CRR:** Cross-Region Replication (S3)
- **Active-Passive:** One region handles traffic; other is standby
- **Hot Standby:** Secondary region services are running but not receiving live traffic

---

*This is a living document. Review and update after every DR event, quarterly drill, or significant architecture change.*
