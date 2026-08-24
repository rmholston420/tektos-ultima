# On-Premise to Cloud Migration Plan

## 1. Assessment Phase

### 1.1 Inventory & Discovery
- **Asset Catalog:** Document all servers, VMs, containers, storage volumes, network configurations, and applications.
- **Configuration Database:** Record OS versions, middleware, runtime environments, and custom configurations.
- **Usage Metrics:** Collect CPU, memory, disk I/O, and network utilization over a 30–90 day period to identify baseline patterns.
- **Tooling:** Use automated discovery tools (e.g., AWS Application Migration Service, Azure Migrate, or cloud provider assessment tools).

### 1.2 Dependency Mapping
- **Application Dependency Map:** Identify inter-application dependencies using network flow logs and APM data.
- **Data Flow Diagrams:** Document how data moves between services, databases, and external systems.
- **External Integrations:** Catalog third-party APIs, partner connections, and on-prem-only services.
- **Critical Path Analysis:** Flag services with tight coupling or synchronous dependencies that limit migration order.

### 1.3 Cost Analysis & TCO Comparison
- **Current State (On-Prem):** Calculate total cost of ownership over 3–5 years including hardware depreciation, data center facilities, power/cooling, staff, licenses, and maintenance contracts.
- **Future State (Cloud):** Estimate cloud costs using the provider's pricing calculator, factoring in compute, storage, networking, managed services, and support plans.
- **Hidden Costs:** Account for data egress fees, cross-AZ/region traffic, backup storage, and operational tooling.
- **Deliverable:** A TCO comparison spreadsheet with monthly and annual projections, showing break-even timeline and 3-year savings estimate.

---

## 2. Migration Strategy — The 6 Rs

| Strategy | Description | Best For |
|---|---|---|
| **Rehost** (Lift & Shift) | Move VMs/applications to cloud with minimal changes. | Time-sensitive migrations, legacy apps with low risk tolerance. |
| **Replatform** | Minor optimizations (e.g., migrate to managed DB, update OS). | Apps that benefit from managed services with limited refactoring. |
| **Refactor / Re-architect** | Rewrite parts of the application for cloud-native design (microservices, serverless). | Strategic apps where long-term agility and cost efficiency are priorities. |
| **Rebuild** | Rebuild from scratch using cloud-native services. | Legacy apps where codebase is obsolete or unmaintainable. |
| **Replace** | Swap with a SaaS solution (e.g., replace custom CRM with Salesforce). | Commodity functionality where best-of-breed SaaS exists. |
| **Retain** | Keep on-prem. | Regulatory constraints, data residency requirements, or apps with zero ROI for migration. |

### Strategy Assignment
- Classify every application into one of the 6 Rs.
- Target: ≥60% Rehost/Replatform in wave 1 for quick wins; ≥20% Refactor/Rebuild in later waves for long-term value.
- Document the rationale for each classification in the migration tracker.

---

## 3. Phased Rollout Plan

### Phase 1 — Non-Production (Weeks 1–6)
**Objective:** Validate migration tooling, processes, and team readiness.

| Wave | Workloads | Success Criteria |
|---|---|---|
| 1.1 | Dev environments, test databases, CI/CD pipelines | All non-prod services running in cloud with identical functionality; automated rollback verified. |
| 1.2 | Staging environment, load testing infrastructure | Performance parity with on-prem; migration script runbooks validated end-to-end. |

### Phase 2 — Staging / Partial Production (Weeks 7–14)
**Objective:** Migrate low-risk production services to validate production-grade operations.

| Wave | Workloads | Success Criteria |
|---|---|---|
| 2.1 | Stateless front-end services, CDN/static assets | Zero downtime migration; DNS cutover <5 min. |
| 2.2 | Independent microservices, background workers | Monitoring/alerting operational; error rates below on-prem baseline. |
| 2.3 | Read-only or replicated databases | Data consistency verified; replication lag <1s during cutover. |

### Phase 3 — Full Production (Weeks 15–24)
**Objective:** Migrate remaining production workloads including stateful systems.

| Wave | Workloads | Success Criteria |
|---|---|---|
| 3.1 | Core transactional databases (with dual-write or CDC) | Data integrity 100%; RPO ≤ 5 min, RTO ≤ 30 min. |
| 3.2 | Message queues, caching layers | No message loss; cache hit rates maintained. |
| 3.3 | Remaining monoliths, batch jobs, analytics pipelines | All SLAs met; performance within 10% of on-prem baseline. |

### Cutover Process (per service)
1. Freeze writes to source (15 min).
2. Final data sync (5–30 min depending on volume).
3. Validate data consistency (automated checksums).
4. Switch DNS / load balancer routing.
5. Monitor for 24 hours; confirm all KPIs.
6. Decommission on-prem resources after 30-day stability period.

---

## 4. Data Migration

### 4.1 Databases
- **Relational (PostgreSQL, MySQL, SQL Server):**
  - Use cloud provider native tools (AWS DMS, Azure Database Migration Service, Google DTS).
  - For zero-downtime: enable continuous replication (CDC) → full load → online cutover.
- **NoSQL (MongoDB, Cassandra, DynamoDB):**
  - Native export/import or cloud-native replication where available.
  - Validate schema compatibility and data types before migration.
- **Migration Order:** Start with read replicas → promote after validation.

### 4.2 File Storage
- **Unstructured Data (NAS/SAN → Object Storage):**
  - Use cloud provider transfer tools (AWS DataSync, Azure Data Box, gsutil).
  - Preserve file metadata, permissions, and directory structure.
  - Migrate in priority order: cold/archive data first, then active data.
- **Databases vs. Files:** Migrate databases first, then application data stores, then file storage.

### 4.3 Backup & Restore Procedures
- **Pre-Migration Backup:** Full snapshot of all on-prem systems before any migration activity.
- **Cloud Backup Strategy:**
  - Enable automated snapshots for all compute and storage resources.
  - Use cross-region replication for critical data (RPO target: 1 hour).
  - Implement immutable backups (S3 Object Lock, Azure Immutable Blob) for ransomware protection.
- **Restore Testing:**
  - Execute at least 2 full restore drills before and after migration.
  - Document RTO/RPO per workload and verify against SLAs.
  - Maintain a runbook for disaster recovery with step-by-step recovery commands.

---

## 5. Security & Compliance

### 5.1 Identity & Access Management (IAM)
- **Principle of Least Privilege:** Assign roles with minimum required permissions; avoid root/admin access.
- **SSO Integration:** Federate identity with existing IdP (Active Directory, Okta) via SAML/OIDC.
- **MFA:** Enforce MFA for all console and API access.
- **Role-Based Access Control:** Define roles per team (Dev, Ops, Security, DBA) with scoped policies.
- **Just-in-Time Access:** Use privileged access management (PAM) for elevated operations.

### 5.2 Encryption
- **Data at Rest:** Enable AES-256 encryption on all storage (EBS, S3, RDS, disks).
- **Data in Transit:** Enforce TLS 1.2+ for all internal and external communications.
- **Key Management:** Use KMS/HSM with customer-managed keys; rotate keys annually.
- **Secrets Management:** Migrate secrets to a vault service (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault).

### 5.3 Network Security
- **VPC/VNet Design:** Isolate workloads with public, private, and database subnets.
- **Security Groups / NACLs:** Default-deny inbound; explicitly allow required traffic.
- **WAF & DDoS:** Deploy Web Application Firewall and DDoS protection on public endpoints.
- **Private Connectivity:** Use Direct Connect / ExpressRoute / Cloud Interconnect for hybrid links.

### 5.4 Audit Logging & Monitoring
- **Centralized Logging:** Ship all logs to a dedicated logging account/service (CloudTrail, VPC Flow Logs, CloudWatch, SIEM).
- **Retention:** Minimum 90 days for operational logs; 1 year for compliance logs.
- **Alerting:** Configure alerts for security events (unauthorized access, policy violations, unusual API calls).
- **SIEM Integration:** Forward logs to on-prem or cloud SIEM for correlation and threat detection.

### 5.5 Compliance Frameworks
- **Identify applicable frameworks:** SOC 2, ISO 27001, HIPAA, PCI-DSS, GDPR, FedRAMP.
- **Shared Responsibility Model:** Document which controls are managed by the cloud provider vs. the organization.
- **Evidence Collection:** Automate compliance evidence gathering (AWS Config rules, Azure Policy, GCP Security Scanner).
- **Annual Audits:** Schedule post-migration audits within 6 months of go-live.

---

## 6. Cost Optimization

### 6.1 Compute
- **Reserved Instances / Savings Plans:** Commit to 1–3 year terms for predictable workloads (target 40–60% savings).
- **Spot Instances:** Use for fault-tolerant, stateless workloads (batch processing, CI/CD, test environments).
- **Auto-Scaling:** Configure horizontal auto-scaling based on CPU/memory/request count; set min/max bounds.
- **Right-Sizing:** Review instance types quarterly using utilization reports; downsize over-provisioned resources.

### 6.2 Storage
- **Lifecycle Policies:** Transition infrequently accessed data to cheaper tiers (Glacier, Cool, Coldline) automatically.
- **Deduplication & Compression:** Enable at the application and storage layer.
- **Delete Orphaned Resources:** Regularly audit and remove unused EBS volumes, snapshots, and idle load balancers.

### 6.3 Monitoring & Governance
- **Tagging Strategy:** Enforce tags for cost allocation (env, team, app, cost-center).
- **Budget Alerts:** Set alerts at 50%, 80%, and 100% of monthly budget per team/project.
- **Cost Anomaly Detection:** Use ML-based anomaly detection to flag unexpected spend spikes.
- **Quarterly Reviews:** Conduct FinOps reviews with engineering and finance to optimize spend.

---

## 7. Rollback Procedures & Risk Mitigation

### 7.1 Rollback Triggers
- Data integrity failure during migration.
- Performance degradation exceeding 20% of baseline.
- Critical security incident or compliance violation.
- Unresolvable application errors within 4 hours of cutover.
- SLA breach risk that cannot be mitigated.

### 7.2 Rollback Procedures
1. **Immediate:** Re-route DNS/load balancer to on-prem endpoint (automated failback script).
2. **Data Sync:** Re-enable write traffic to on-prem systems; apply any delta changes made during migration window.
3. **Validation:** Confirm on-prem system functionality and data consistency.
4. **Post-Mortem:** Document root cause and remediation before retry.
5. **Timeline:** Full rollback must be achievable within 1 hour of trigger decision.

### 7.3 Risk Mitigation Matrix

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Data loss during migration | Low | Critical | Pre-migration backups; multi-pass validation; checksum verification |
| Extended downtime | Medium | High | Dry-run cutover; parallel run period; automated rollback |
| Performance regression | Medium | Medium | Load testing in staging; auto-scaling; performance baseline comparison |
| Security breach | Low | Critical | Pre-migration security assessment; penetration test; WAF/DDoS protection |
| Cost overrun | Medium | Medium | Budget alerts; right-sizing; reserved instance planning |
| Skill gap | Medium | Medium | Training program; runbook documentation; vendor support engagement |
| Compliance violation | Low | Critical | Pre-assessment; automated policy checks; legal review |

### 7.4 Communication Plan
- **Stakeholders:** Executive sponsor, engineering leads, operations, security, finance, legal.
- **Cadence:** Weekly status updates; daily stand-ups during migration windows.
- **Escalation Path:** L1 (team lead) → L2 (program manager) → L3 (executive sponsor).
- **Incident Response:** Dedicated war room (Slack channel + bridge line) during cutover windows.

---

## Appendix: Key Metrics & Success Criteria

| Metric | Target |
|---|---|
| Migration completion | 100% of classified workloads migrated within 6 months |
| Downtime per service | ≤ 15 minutes (planned cutover) |
| Data integrity | 100% (zero data loss verified by checksums) |
| Performance | Within 10% of on-prem baseline |
| Cost savings | ≥ 20% reduction in TCO by month 12 |
| Security incidents | Zero critical incidents during migration |
| Rollback readiness | 100% of services with tested rollback runbook |

---

*Document Version: 1.0*
*Last Updated: 2026-08-21*
*Owner: Cloud Migration Program Office*
