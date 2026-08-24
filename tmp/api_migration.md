# API Version Migration Plan

> **Scope:** Migration from API v1 → v2
> **Date:** 2026-08-21
> **Owner:** Platform Engineering Team

---

## 1. Current State Analysis

### 1.1 v1 Endpoints

| Endpoint | Method | Description | Monthly Calls |
|---|---|---|---|
| `/api/v1/users` | GET/POST | User management | 2.4M |
| `/api/v1/users/{id}` | GET/PUT/DELETE | Single user CRUD | 3.1M |
| `/api/v1/orders` | GET/POST | Order listing & creation | 5.7M |
| `/api/v1/orders/{id}` | GET/PUT | Order detail & update | 4.2M |
| `/api/v1/products` | GET/POST | Product catalog | 8.9M |
| `/api/v1/products/{id}` | GET/PUT/DELETE | Product CRUD | 6.3M |
| `/api/v1/auth/login` | POST | Authentication | 12.1M |
| `/api/v1/auth/refresh` | POST | Token refresh | 9.8M |

### 1.2 Known Dependencies

- **Internal services:** 14 downstream consumers (auth, billing, analytics, mobile apps, partner integrations)
- **Third-party SDKs:** 3 official SDKs (Python, JS, Java) — all v1-compatible only
- **Monitoring:** Datadog dashboards, PagerDuty alerts wired to v1 response codes
- **CI/CD:** 42 integration tests target v1 endpoints

### 1.3 Usage Statistics

- **Peak traffic:** 1,200 req/s (weekday 14:00–16:00 UTC)
- **Error rate (v1):** 0.42% (target: <0.1% for v2)
- **Avg latency (v1):** 185ms p95
- **Client breakdown:** 68% mobile, 22% web dashboard, 10% third-party partners

---

## 2. Migration Strategy

### 2.1 Parallel Run

- Both v1 and v2 routes will coexist on the same host under `/api/v1/` and `/api/v2/`
- A **request router middleware** will inspect the `X-API-Version` header or URL path to dispatch to the correct handler
- All v2 responses include `X-Migration-Status: stable` header for tracking

### 2.2 Feature Flags

| Flag | Purpose | Default |
|---|---|---|
| `v2_orders_enabled` | Enable v2 order endpoints | `false` |
| `v2_users_enabled` | Enable v2 user endpoints | `false` |
| `v2_products_enabled` | Enable v2 product endpoints | `false` |
| `v2_auth_enabled` | Enable v2 auth endpoints | `true` (low risk) |
| `v2_dark_launch` | Route 0% of traffic to v2 for validation | `false` |

Flags are managed via LaunchDarkly and can be toggled per-tenant, per-user, or globally.

### 2.3 Gradual Rollout (5 Phases)

| Phase | Traffic Share | Duration | Criteria to Proceed |
|---|---|---|---|
| **P0: Internal** | 0% (dark launch) | 3 days | No errors in logs; CI tests pass |
| **P1: Canary** | 1% of traffic | 5 days | Error rate < 0.5%; p95 latency ≤ 200ms |
| **P2: Beta** | 10% of traffic | 10 days | No P1/P2 incidents; client feedback positive |
| **P3: General** | 50% of traffic | 7 days | Stable at 50%; all dashboards green |
| **P4: Full** | 100% of v2 | 3 days | Zero v1-only traffic; cleanup ready |

### 2.4 Data Compatibility

- v2 introduces `created_at` (ISO 8601) replacing `created_on` (Unix epoch) for all entities
- A **response transformer** in the v1 middleware will convert legacy formats during the overlap period
- All v2 endpoints accept both old and new field names for backward compatibility during rollout

---

## 3. Deprecation Timeline

| Milestone | Date | Action |
|---|---|---|
| **Announcement** | 2026-09-01 | Publish deprecation notice; send email to all API consumers |
| **v2 GA release** | 2026-09-15 | v2 endpoints marked stable; v1 still fully supported |
| **v1 sunset announcement** | 2026-12-01 | Official EOL notice with 90-day warning |
| **v1 read-only** | 2027-01-15 | v1 POST/PUT/DELETE disabled; GET still works |
| **v1 sunset** | 2027-03-15 | v1 endpoints return `410 Gone` with migration link |
| **Code cleanup** | 2027-04-01 | Remove v1 route handlers, tests, and SDK stubs |

> **Support period:** 6 months of bug-fix-only support for v1 after sunset announcement. No new features.

---

## 4. Client Communication Plan

### 4.1 Changelog

- Maintain a `CHANGELOG.md` in the API repo
- Every v2 release includes: breaking changes, new fields, deprecation warnings
- Post release notes to the internal developer portal and Slack `#api-changes`

### 4.2 Migration Guide

Create a per-endpoint migration guide covering:

1. **Endpoint changes** — old path → new path
2. **Request/response differences** — field renames, new required fields
3. **Code snippets** — before/after examples in Python, JS, Java
4. **Auth changes** — token format, scope updates
5. **Error code changes** — old codes → new codes

Publish at: `https://api.example.com/docs/migration/v1-to-v2`

### 4.3 Support Channels

| Channel | Purpose | Response SLA |
|---|---|---|
| `#api-migration` Slack | General questions, issues | 4 hours |
| GitHub Discussions | Public Q&A, feature requests | 24 hours |
| Dedicated support email | Urgent migration blockers | 2 hours |
| Office hours | Bi-weekly live session (Thursdays 10 AM PT) | Scheduled |

### 4.4 Proactive Outreach

- Identify top 20 consumers by API volume; assign an engineer as migration liaison
- Schedule 1:1 calls with each to review their integration and timeline
- Provide a **migration checklist** PDF for their project planning

---

## 5. Rollback Procedures & Risk Mitigation

### 5.1 Rollback Triggers

| Condition | Severity | Action |
|---|---|---|
| Error rate > 2% sustained for 15 min | P1 | Immediately revert traffic to 100% v1 |
| p95 latency > 500ms for 10 min | P2 | Scale back to previous phase |
| Data corruption detected | P0 | Halt rollout; investigate |
| Critical bug in v2 auth | P0 | Roll back v2 auth flag; notify all |

### 5.2 Rollback Steps

1. **Disable feature flags** — turn off all `v2_*_enabled` flags
2. **Restore traffic** — router middleware sends 100% to v1
3. **Verify** — confirm v1 dashboards are green; error rate drops
4. **Communicate** — notify stakeholders of rollback and next steps
5. **Investigate** — post-incident review within 24 hours

> **Rollback time target:** < 5 minutes from trigger to full v1 restoration.

### 5.3 Risk Mitigation

| Risk | Likelihood | Mitigation |
|---|---|---|
| v2 regression in production | Medium | Canary testing; automated rollback; feature flags |
| Client integration delays | High | Early outreach; migration guide; dedicated support |
| Data migration errors | Low | Dual-write validation; checksum comparison |
| Performance degradation | Medium | Load testing v2 in staging pre-rollout; auto-scaling |
| Third-party SDK non-compliance | Medium | Publish SDK updates 2 weeks before GA; provide manual migration steps |

### 5.4 Backup & Safety Nets

- **API contract tests** run against v2 before every deployment
- **V2 read replica** of production data for safe experimentation
- **Snapshot of v1 configs** taken before any v2 changes go live
- **PagerDuty escalation** configured specifically for v2 migration incidents

---

## Appendix: Quick Reference

- **Feature flag service:** LaunchDarkly (`ld://api-migration`)
- **Monitoring:** Datadog dashboard `api_v2_migration`
- **Docs portal:** `https://api.example.com/docs/migration/v1-to-v2`
- **Rollback runbook:** `/runbooks/api-v2-rollback.md`
- **Status page:** `https://status.example.com/api-migration`
