# Multi-Tenant SaaS Architecture & Rollout Plan

**Version:** 1.0  
**Date:** 2026-08-21  
**Status:** Draft

---

## 1. Tenant Isolation Strategy

### Hybrid Isolation Model

| Tenant Tier | Isolation Level | Database Strategy |
|-------------|-----------------|-------------------|
| Free | Logical isolation | Shared schema with RLS |
| Professional | Strong isolation | Schema-per-tenant |
| Enterprise | Maximum isolation | Dedicated database |

### Row-Level Security (RLS) — Default for Free/Pro
- Every query enforces `WHERE tenant_id = current_tenant()`
- Database-level guardrails prevent cross-tenant data leaks
- Application middleware injects tenant context automatically

### Schema-per-Tenant
- Automated schema creation during provisioning
- Independent migration execution per schema
- Simplified backup/restore at tenant granularity

### Database-per-Tenant (Enterprise)
- Full infrastructure separation
- Independent scaling, backups, and monitoring
- Meets strictest compliance requirements

> **Key principle:** tenant isolation must be enforced at the **database layer** as the final security boundary, not just in application code.

---

## 2. Data Residency & Compliance

### Regional Data Placement

| Regulation | Scope | Implementation |
|------------|-------|----------------|
| **GDPR** | EU/EEC | Data stays in EU regions; DPA templates provided |
| **CCPA** | California | Data sale opt-out; right to deletion workflows |
| **HIPAA** | US Healthcare | BAA-covered infrastructure; PHI encryption |
| **Data Sovereignty** | Country-specific | Geo-fencing per tenant preference |

### Compliance Architecture
- **Geo-routing:** DNS + API gateway routes to tenant's designated region
- **Cross-region replication:** Opt-in only, never automatic
- **Data classification:** Tags (public, pii, phi, confidential) drive encryption/access controls
- **Automated compliance scanning** via OPA policies on every data access

### Audit & Retention
- Immutable audit log (append-only, cryptographically verified)
- Configurable retention (7-year default for regulated data)
- Tenant-facing compliance dashboard

---

## 3. Multi-Region Deployment Architecture

### Active-Active Regional Clusters

```
                    ┌─────────────┐
                    │  Global DNS  │
                    │  (Geo-IP)    │
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │  US-East  │  │ EU-West  │  │ APAC-Tok │
      │  (Active) │  │ (Active) │  │ (Active) │
      └────┬─────┘  └────┬─────┘  └────┬─────┘
           │              │              │
           └──────────────┼──────────────┘
                          ▼
               ┌──────────────────┐
               │  Async Replication│
               └──────────────────┘
```

### Latency Optimization
- CDN edge caching for static assets and cacheable API responses
- Regional API gateways with local JWT validation
- Database read replicas per region for low-latency reads

### Failover Strategy
- **RPO:** < 5 minutes (async WAL replication)
- **RTO:** < 15 minutes (automated DNS failover + connection draining)
- **Health checks:** Every 10s per region; automatic traffic shift on failure
- **DR drills:** Quarterly testing with documented runbooks

---

## 4. Billing & Subscription Management

### Pricing Tiers

| Tier | Price | Features |
|------|-------|----------|
| Free | $0 | 3 users, 1 GB, community support |
| Starter | $29/user | 25 users, 50 GB, email support |
| Professional | $79/user | Unlimited users, 500 GB, SSO, priority support |
| Enterprise | Custom | Dedicated infra, SLA, custom integrations |

### Usage-Based Billing
- **Storage:** $0.10/GB/month beyond allowance
- **API calls:** $0.001/call beyond 100k/month
- **Compute:** $5/1000 vCPU-hours
- **Seat add-ons:** $15/user/month beyond base

### Proration Engine
- Upgrades/downgrades prorate at the second level
- Credits applied to next invoice cycle
- Mid-cycle adjustments supported

### Payment Processing
- **Stripe** primary gateway
- Automated dunning (3 retries, 3-day intervals)
- Tax calculation via Stripe Tax
- Self-service billing portal with CSV/PDF exports

---

## 5. Tenant Onboarding & Offboarding Lifecycle

### Onboarding Flow

```
1. Signup ──► 2. Provisioning ──► 3. Configuration ──► 4. Welcome
   │              │                   │                    │
   email/SSO      Create DB/schema    Set defaults         Send email
                  Generate keys       Invite admin
                  Assign plan
```

### Provisioning SLA
- **95% of tenants:** Provisioned within 60 seconds
- Automated via Terraform + CI/CD pipelines
- Seed migrations run automatically

### Offboarding (Graceful Deprovisioning)

| Phase | Action | Timeline |
|-------|--------|----------|
| 1 | Soft delete (data preserved, access revoked) | Day 0 |
| 2 | Grace period (admin can reactivate) | Days 1–30 |
| 3 | Data export (encrypted archive to S3) | Day 30 |
| 4 | Hard delete (permanent removal) | Day 60 |
| 5 | Compliance retention (audit logs) | 7 years |

### Data Export
- One-click export (JSON, CSV, PDF)
- Encrypted transfer via signed S3 URLs
- Bulk export tool for datasets >10 GB

---

## 6. Security Model

### Access Control Framework

| Model | Scope | Implementation |
|-------|-------|----------------|
| **RBAC** | Role-based | Admin, Editor, Viewer, Auditor |
| **ABAC** | Attribute-based | Dynamic policies (e.g., `resource.dept == user.dept`) |
| **SSO/SAML** | Enterprise identity | Okta, Azure AD, Google Workspace |
| **OIDC** | Consumer/social | Social login, mobile auth |

### SSO Integration
- SAML 2.0 for enterprise federation
- SCIM 2.0 for automated user provisioning
- JIT user creation on first SSO login

### Audit Logging
- Every auth event, data access, config change logged
- Fields: `tenant_id`, `user_id`, `action`, `resource`, `ip`, `timestamp`
- Immutable storage with cryptographic verification
- SIEM integration (Splunk, Datadog, PagerDuty)

### Secrets Management
- AWS Secrets Manager / HashiCorp Vault
- Automatic rotation every 90 days
- Tenant API keys scoped to specific resources

---

## 7. Performance Isolation Guarantees

### Resource Quotas

| Resource | Free | Starter | Pro | Enterprise |
|----------|------|---------|-----|------------|
| vCPU | 0.1 | 0.5 | 2.0 | 10.0+ |
| Memory | 128 MB | 512 MB | 2 GB | 8 GB+ |
| Storage | 1 GB | 50 GB | 500 GB | Unlimited |
| API/min | 60 | 600 | 6,000 | 60,000 |
| Connections | 5 | 20 | 100 | 500 |

### Rate Limiting Strategy
- **Token bucket** algorithm per tenant at API gateway
- **Sliding window** counters in Redis (30-second windows)
- Three enforcement layers: Gateway → Middleware → Database RLS

### Noisy Neighbor Prevention
- **cgroups** for CPU/memory isolation at container level
- Redis Sentinel with per-tenant key namespaces
- Priority queues for critical operations
- Auto-scaling per tier; enterprise gets dedicated instances

### Monitoring
- Per-tenant latency (p50, p95, p99)
- Error rate thresholds → automatic throttling
- Anomaly detection (ML-based baseline)

---

## 8. Rollout Strategy

### Phase 1: Beta (Weeks 1–4)
- **5–10 design partner tenants**
- Validate provisioning pipeline, onboarding flow
- **Success:** < 5-minute provisioning, zero data loss

### Phase 2: Closed Beta (Weeks 5–8)
- **25–50 invited tenants**
- Test billing, rate limiting, support workflows
- **Success:** < 2% critical bugs, billing accuracy > 99.5%

### Phase 3: Public Beta (Weeks 9–12)
- **Open signup, self-serve**
- Load testing, CI/CD validation
- **Success:** 99.9% uptime, < $0.50 infra cost/tenant/month

### Phase 4: GA (Week 13+)
- Full feature set available
- Enterprise tier with dedicated SLA
- Rollback capability via blue/green deployment

### Feature Flags
- Platform: LaunchDarkly or Unleash
- Granularity: Tenant-level, user-level, cohort-level
- Default: Disabled until QA approval
- Audit: Every flag change logged

---

## 9. Cost Model & Unit Economics

### Infrastructure Cost (Per Tenant, Pro Tier)

| Component | Monthly Cost |
|-----------|-------------|
| Compute | $12.00 |
| Database | $8.50 |
| Storage | $0.10 |
| CDN/Edge | $0.50 |
| API Gateway | $0.30 |
| Monitoring | $0.10 |
| **Total** | **~$21.50** |

### Revenue vs. Cost

| Tier | Revenue | Cost | Margin |
|------|---------|------|--------|
| Free | $0 | $5.00 | -100% |
| Starter | $87 | $8.00 | 90.8% |
| Professional | $237 | $21.50 | 90.9% |
| Enterprise | $1,200+ | $45.00 | 96.3% |

### Key Metrics
- **CAC Payback:** < 6 months
- **Gross Margin (blended):** > 85%
- **LTV:CAC:** > 3:1
- **Infra cost/revenue dollar:** < $0.10 at scale

### Optimization Levers
1. Reserved instances (saves ~40%)
2. Spot instances for background jobs (saves ~70%)
3. Storage tiering (cold data → Glacier after 90 days)
4. Maximize co-tenancy density for Free/Starter tiers

---

## 10. Implementation Roadmap

### Sprint 1–2: Foundation
- [ ] Tenant-aware database schema design
- [ ] RLS policies implemented and tested
- [ ] Tenant context middleware

### Sprint 3–4: Core Services
- [ ] Provisioning automation (Terraform)
- [ ] SSO/SAML integration (2 IdPs)
- [ ] RBAC/ABAC engine

### Sprint 5–6: Billing & Monitoring
- [ ] Stripe integration + proration
- [ ] Usage metering and reporting
- [ ] Rate limiting and quota enforcement

### Sprint 7–8: Rollout Infrastructure
- [ ] Feature flag system
- [ ] Multi-region deployment (active-active)
- [ ] CI/CD with canary deployments

### Sprint 9–10: Beta & Hardening
- [ ] Beta tenant onboarding
- [ ] Load testing and performance validation
- [ ] Audit logging + SIEM integration
- [ ] Disaster recovery drill

---

## Appendix

### Glossary
- **Tenant:** Distinct customer/organization
- **RLS:** Row-Level Security
- **SCIM:** System for Cross-domain Identity Management
- **RPO/RTO:** Recovery Point/Time Objective

### References
- [AWS Multi-Tenant Patterns](https://aws.amazon.com/solutions/multi-tenant/)
- [OWASP Multi-Tenant Security](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)
- [Stripe Billing Docs](https://stripe.com/docs/billing)
- [GDPR Art. 32](https://gdpr.eu/article-32-security-of-processing/)

---

*Review quarterly; update as architecture, compliance, and business model evolve.*
