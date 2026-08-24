# Multi-Region Disaster Recovery Plan

**Document Status:** Active  
**Last Updated:** 2026-08-21  
**Owner:** Platform Engineering  
**Review Cycle:** Quarterly

---

## 1. RTO / RPO Definitions by Service Tier

| Tier | Description | RTO | RPO | Examples |
|------|-------------|-----|-----|----------|
| **Critical** | Revenue-impacting, customer-facing core services | ≤ 15 min | ≤ 5 min | API Gateway, Auth Service, Payment Processing, Primary DB |
| **Important** | Business-enabling services with moderate user impact | ≤ 1 hour | ≤ 15 min | Search, Notifications, Analytics Pipeline, CDN |
| **Standard** | Internal or background services with minimal user impact | ≤ 4 hours | ≤ 1 hour | Logging, Batch Jobs, Reporting, Dev/Test Environments |

**Notes:**
- RTO = Recovery Time Objective (max acceptable downtime)
- RPO = Recovery Point Objective (max acceptable data loss)
- All SLA commitments are measured from the moment a DR event is declared.

---

## 2. Current Architecture Analysis

### 2.1 Deployment Model
- **Single-region deployment** in `us-east-1`.
- All production workloads run in one availability zone group.
- No cross-region redundancy for any tier.

### 2.2 Key Dependencies
| Dependency | Type | Single Point of Failure? |
|------------|------|--------------------------|
| Primary RDS (PostgreSQL) | Database | Yes |
| ElastiCache (Redis) | Cache | Yes |
| S3 (asset storage) | Object storage | No (multi-AZ) |
| Route 53 | DNS | No (global) |
| ELB / ALB | Load balancing | Yes |
| ECS / Fargate | Compute | Yes |
| CloudFront | CDN | No (global edge) |
| Secrets Manager | Secrets | Yes |

### 2.3 Data Replication (Current)
- RDS Multi-AZ replication (within `us-east-1` only).
- S3 cross-region replication not enabled for all buckets.
- No database-level cross-region replication.
- Backup snapshots stored in same region.

### 2.4 Risk Summary
| Risk | Likelihood | Impact |
|------|-----------|--------|
| Regional outage | Low | **Critical** |
| Multi-AZ failure | Medium | High |
| Data corruption | Low | High |
| Configuration drift | Medium | Medium |

---

## 3. Target Architecture

### 3.1 Model: Active-Passive with Warm Standby

```
                    ┌─────────────────────────┐
                    │        Route 53           │
                    │  (Health-Checked Failover)│
                    └──────┬────────────┬──────┘
                           │            │
                    ┌──────▼──────┐ ┌──▼──────────┐
                    │  ACTIVE      │ │  STANDBY     │
                    │  us-east-1   │ │  us-west-2   │
                    │  (Production)│ │  (Warm)      │
                    └──────┬──────┘ └──┬──────────┘
                           │           │
                    ┌──────▼──────┐ ┌──▼──────────┐
                    │  Primary     │ │  Replica     │
                    │  Databases   │ │  Databases   │
                    └─────────────┘ └─────────────┘
```

### 3.2 Component Mapping

| Component | Active Region | Standby Region | Failover Mechanism |
|-----------|--------------|----------------|-------------------|
| DNS / Traffic | us-east-1 | us-west-2 | Route 53 latency-based + health checks |
| Compute (ECS/Fargate) | us-east-1 | us-west-2 | Pre-warmed task definitions, minimal capacity |
| Databases | RDS Multi-AZ | RDS Read Replica (cross-region) | Promote replica |
| Cache | ElastiCache cluster | Warm standby cluster | Connection failover |
| Object Storage | S3 bucket | S3 cross-region replication | Automatic |
| Secrets | Secrets Manager | Secrets Manager replication | Manual rotation on failover |

### 3.3 DNS Failover Strategy
- Route 53 **latency-based routing** to active region endpoint.
- Health checks probe all critical service endpoints every **10 seconds**.
- Automatic failover triggered after **3 consecutive failures** (~30 seconds).
- TTL set to **60 seconds** for fast propagation.

---

## 4. Data Replication Strategy

### 4.1 Database Replication

| Database | Strategy | Direction | Sync Mode |
|----------|----------|-----------|-----------|
| PostgreSQL (Primary) | RDS Read Replica | us-east-1 → us-west-2 | Asynchronous |
| Redis (Cache) | Snapshot + log replication | us-east-1 → us-west-2 | Near-real-time |
| S3 (Assets) | Cross-Region Replication (CRR) | us-east-1 → us-west-2 | Asynchronous |

### 4.2 Synchronous vs Asynchronous Trade-offs

| Approach | RPO | Latency Impact | Use Case |
|----------|-----|----------------|----------|
| **Synchronous** | Near-zero | High (+50-100ms) | Financial transactions, only for Critical tier if latency budget allows |
| **Asynchronous** | Minutes | Minimal | Default for all tiers; acceptable for Important and Standard |

**Decision:** Use **asynchronous replication** for all tiers.
- Critical database RPO is met via frequent snapshots (every 5 min) + WAL archiving.
- Synchronous replication is reserved only if a specific service's compliance requires it.

### 4.3 Backup Strategy
| Tier | Backup Frequency | Retention | Cross-Region Backup? |
|------|-----------------|-----------|---------------------|
| Critical | Every 5 min (WAL) + daily snapshot | 35 days | Yes |
| Important | Every 15 min + daily snapshot | 30 days | Yes |
| Standard | Daily snapshot | 14 days | No |

---

## 5. Failover Procedures

### 5.1 Automated Triggers

| Trigger | Action | Threshold |
|---------|--------|-----------|
| Route 53 health check fails 3× | DNS failover initiated | 30 seconds |
| ALB target group unhealthy | Scale down active, scale up standby | 60 seconds |
| Database endpoint unreachable | Promote standby replica | 2 minutes |
| CloudWatch alarm: regional degradation | Alert on-call; auto-failover approved | 15 minutes |

### 5.2 Automated Failover Runbook

```
1. Health check detects failure → Route 53 updates DNS
2. Lambda function triggers:
   a. Promote RDS read replica to standalone
   b. Start standby ECS task definitions (min 2 instances per service)
   c. Redirect ALB target group to standby targets
   d. Update DNS A/AAAA records (TTL=60s)
3. Notify on-call via PagerDuty / Slack
4. Verify service health in standby region
5. Begin investigation in active region
```

### 5.3 Manual Override

When automated failover is **not** desired (e.g., partial outage, planned maintenance):

1. **Escalation:** On-call engineer → Service Owner → VP Engineering.
2. **Approval:** Two-person rule for manual failover.
3. **Execution:**
   ```bash
   # Example: Promote RDS replica
   aws rds promote-db-cluster \
       --db-cluster-identifier arn:aws:rds:us-west-2:...:cluster/standby-cluster

   # Example: Update Route 53 record
   aws route53 change-resource-record-sets \
       --hosted-zone-id ZONE_ID \
       --change-batch file://failover.json
   ```
4. **Documentation:** Log all manual actions in incident tracker.

### 5.4 Post-Failover Validation

| Check | Method | Owner |
|-------|--------|-------|
| DNS resolution | `dig +short app.example.com` | On-call |
| HTTPS certificate | `curl -v https://app.example.com` | On-call |
| Database connectivity | Connection test to promoted DB | DBA |
| Service health | Health endpoint `/health` returns 200 | On-call |
| Data integrity | Compare record counts vs known-good snapshot | DBA |
| Application logs | Verify no error spikes | SRE |

---

## 6. Failback Procedures

### 6.1 Pre-Failback Checklist
- [ ] Active region is fully operational and stable for ≥ 24 hours
- [ ] Root cause of outage is identified and resolved
- [ ] Data divergence between regions is quantified
- [ ] Business approval obtained for failback window

### 6.2 Data Synchronization

| Step | Action | Duration Estimate |
|------|--------|-------------------|
| 1 | Create standby read replica in original region | 30 min |
| 2 | Sync full dataset (snapshot restore + WAL replay) | 1-4 hours |
| 3 | Verify data consistency | 30 min |
| 4 | Enable bidirectional sync (if supported) or set to "replica only" | 15 min |

### 6.3 Traffic Cutover

```
1. Set Route 53 health checks to probe BOTH regions
2. Gradually shift traffic using weighted routing:
   - Phase 1: 90% standby / 10% active  (observe for 1 hour)
   - Phase 2: 75% standby / 25% active  (observe for 2 hours)
   - Phase 3: 50% / 50%                  (observe for 4 hours)
   - Phase 4: 0% standby / 100% active  (return to normal)
3. Monitor error rates, latency, and resource utilization throughout
4. Cancel and revert if error rate exceeds 0.1%
```

### 6.4 Failback Verification

| Check | Method |
|-------|--------|
| All services healthy | Automated health checks pass |
| Data integrity | Record count + checksum comparison |
| Performance baseline | Latency and throughput within 5% of pre-outage |
| SSL/TLS | Certificates valid and served correctly |
| Monitoring | No anomalous alerts in standby region |
| Rollback plan tested | Failback can be reversed within 15 minutes |

---

## 7. Testing Schedule

### 7.1 Drill Types

| Drill Type | Frequency | Scope | Participants |
|------------|-----------|-------|-------------|
| **Tabletop Exercise** | Quarterly | Scenario-based discussion | Engineering leads, PM, Ops |
| **Partial Failover** | Quarterly | Non-production service | SRE team |
| **Full DR Failover** | Semi-annually | All critical services | Entire engineering org |
| **Chaos Engineering** | Monthly | Random fault injection (non-prod) | SRE team |

### 7.2 Quarterly Tabletop Exercise Format

```
1. Scenario distribution (48 hours in advance)
2. 2-hour workshop:
   - Walk through the scenario step by step
   - Identify gaps in runbooks
   - Test communication protocols
3. Post-exercise:
   - Document lessons learned
   - Update runbooks within 2 weeks
   - Track action items to completion
```

### 7.3 Full DR Drill (Semi-Annual)

```
1. Schedule 2-week window with stakeholder communication
2. Execute failover to standby region during maintenance window
3. Run validation suite against standby environment
4. Execute failback to production region
5. Debrief within 48 hours
6. Publish report and update plan
```

### 7.4 Metrics & Reporting

| Metric | Target | Reporting |
|--------|--------|-----------|
| DR plan accuracy | 100% of services have runbooks | Per drill |
| Failover RTO achieved | Within tier RTO target | Per drill |
| Failover RPO achieved | Within tier RPO target | Per drill |
| Runbook currency | Updated within 30 days of any change | Quarterly review |
| Training completion | 100% of on-call staff | Per drill |

---

## 8. Contact & Escalation

| Role | Contact | Escalation Time |
|------|---------|-----------------|
| On-Call Engineer | PagerDuty / Slack | Immediate |
| Service Owner | Slack + Email | 15 minutes |
| VP Engineering | Phone | 30 minutes |
| External Communications | PR / Legal | 1 hour (if customer-impacting) |

---

## 9. Appendix

### 9.1 Glossary
- **RTO:** Recovery Time Objective — maximum acceptable downtime
- **RPO:** Recovery Point Objective — maximum acceptable data loss
- **Warm Standby:** Pre-provisioned infrastructure in standby region with minimal capacity
- **Failback:** Restoring operations to the original region after an outage
- **WAL:** Write-Ahead Logging — PostgreSQL's transaction log mechanism

### 9.2 References
- [AWS Well-Architected Framework — Reliability Pillar](https://aws.amazon.com/architecture/well-architected/)
- [Site Reliability Engineering, Google](https://sre.google/sre-book/table-of-contents/)
- Internal incident response playbook: `docs/incident-response.md`

### 9.3 Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-08-21 | Platform Engineering | Initial draft |

---

*This document is a living artifact. Review and update after every DR drill, architecture change, or incident.*
