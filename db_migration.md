# Database Schema Migration Plan

> **Date:** 2026-08-21  
> **Status:** Draft  
> **Owner:** Backend Team

---

## 1. Schema Changes Overview

### New Tables

| Table | Purpose | Key Columns |
|---|---|---|
| `user_preferences` | Store per-user settings | `user_id` (FK), `key`, `value`, `updated_at` |
| `audit_log` | Track data mutations | `id`, `entity`, `entity_id`, `action`, `changed_by`, `timestamp` |
| `notification_queue` | Async notification delivery | `id`, `user_id`, `type`, `payload`, `status`, `created_at` |

### Column Changes

| Table | Change | Type |
|---|---|---|
| `users` | Add `email_verified` (boolean, default `false`) | Non-nullable with default |
| `orders` | Add `payment_status` enum (`pending`, `paid`, `failed`, `refunded`) | Non-nullable with default `pending` |
| `orders` | Rename `total_amount` → `subtotal` | Data-type compatible |
| `orders` | Add `total_amount` (computed column via trigger or app logic) | New column |

### Indexes

| Index | Table | Columns | Type |
|---|---|---|---|
| `idx_user_preferences_key` | `user_preferences` | `user_id`, `key` | Composite |
| `idx_audit_log_entity` | `audit_log` | `entity`, `entity_id`, `timestamp` | Composite |
| `idx_notification_status` | `notification_queue` | `status`, `created_at` | Composite |
| `idx_orders_payment` | `orders` | `payment_status`, `updated_at` | Composite |

---

## 2. Migration Approach

### Principles

- **Zero-downtime:** All schema changes must be deployable without service interruption.
- **Backward-compatible:** Schema changes follow the **expand/contract** pattern:
  1. **Expand:** Add new columns/tables (nullable, with defaults) and new indexes.
  2. **Deploy code:** Update application to write to both old and new structures.
  3. **Backfill:** Migrate existing data to new columns/tables.
  4. **Contract:** Drop old columns/tables in a subsequent release.

### Change Phases

| Phase | Action | Risk |
|---|---|---|
| Phase 1 | Add new tables, nullable columns, indexes | Low — read-only for DB, app still uses old schema |
| Phase 2 | Deploy code (dual-write) | Medium — app writes to both old and new structures |
| Phase 3 | Backfill existing data | Medium — run in batches, monitor lock contention |
| Phase 4 | Switch reads to new columns | Low — verify data parity |
| Phase 5 | Remove old columns (next release) | Low — old column no longer written to |

### Constraints

- No `DROP COLUMN`, `ALTER COLUMN TYPE`, or `NOT NULL` on non-default columns in Phase 1.
- All migrations must be idempotent.
- Maximum table lock time: < 5 seconds (use `CREATE INDEX CONCURRENTLY` / `ALTER TABLE ... ADD COLUMN` patterns).

---

## 3. Data Migration Steps

### ETL Scripts

```sql
-- Backfill orders.total_amount from orders.total_amount (renamed to subtotal)
UPDATE orders
SET total_amount = subtotal * (1 + tax_rate)
WHERE total_amount IS NULL;

-- Backfill user_preferences from existing JSON settings
INSERT INTO user_preferences (user_id, key, value, updated_at)
SELECT user_id, 'settings', settings_json::text, updated_at
FROM users
WHERE settings_json IS NOT NULL
ON CONFLICT DO NOTHING;
```

- Scripts run as **batched operations** (10,000 rows per batch) to avoid long-running transactions.
- Each batch is wrapped in a transaction with a retry loop.
- Batch size tuned to keep per-batch duration under 2 seconds.

### Validation

| Check | Method |
|---|---|
| Row counts match | `COUNT(*)` comparison between source and target |
| Sample data parity | Random sample comparison via checksum |
| Index coverage | `EXPLAIN ANALYZE` on critical queries |
| FK integrity | `SELECT * FROM orders WHERE payment_status NOT IN ('pending','paid','failed','refunded')` |

- Validation runs **before** and **after** backfill.
- Results logged to `migration_validation` table for audit trail.

### Rollback Data

- **Snapshot:** Full table export (`pg_dump` / `mysqldump`) of affected tables taken before migration.
- **Delta log:** All backfilled rows logged to `migration_audit_log` with old and new values.
- **Point-in-time recovery:** RDS/Postgres PITR enabled for 7 days post-migration.

---

## 4. Testing Strategy

### Staging Environment

- Full production-data copy (sanitized) in staging.
- Run migration script against staging with identical batch sizes.
- Validate with automated test suite:
  - Schema assertions (column existence, types, constraints)
  - Query correctness (equivalence of old vs. new queries)
  - Performance benchmarks (p95 latency < 1.2× baseline)

### Canary Release

- Deploy new code to **5%** of production instances.
- Route 5% of traffic to canary instances.
- Monitor for:
  - Error rate spike (> 0.5% increase triggers rollback)
  - Latency degradation (> 10% increase)
  - Data consistency errors

### Production Validation

- After canary promotion (24-hour observation window):
  - Run full production validation suite
  - Enable dual-write fully
  - Begin backfill in production (off-peak hours)
- Post-backfill:
  - Switch reads to new schema
  - Run 24-hour smoke tests
  - Confirm no regressions in downstream dashboards

---

## 5. Rollback Plan and Monitoring

### Rollback Triggers

| Trigger | Action |
|---|---|
| Error rate > 1% for 5 minutes | Automatic rollback to previous schema version |
| Data inconsistency detected | Stop migration, revert backfill, alert on-call |
| p95 latency > 2× baseline | Pause migration, investigate |
| Manual rollback request | Revert to snapshot + previous code version |

### Rollback Procedure

1. **Stop** all new migrations (cancel running jobs).
2. **Revert** application code to pre-migration version (code already supports both schemas).
3. **Revert** data if needed:
   - Use `migration_audit_log` delta for targeted rollback.
   - Fall back to snapshot restore for uncontrolled changes.
4. **Verify** service health and data integrity post-rollback.
5. **Document** root cause before retrying.

### Monitoring

| Metric | Tool | Alert Threshold |
|---|---|---|
| Query latency (p95) | Prometheus + Grafana | > 200ms |
| Migration batch duration | Custom dashboard | > 5s per batch |
| Error rate | Datadog / New Relic | > 0.5% |
| Row count drift | Validation script (hourly) | Any drift detected |
| Lock waits | `pg_stat_activity` / `SHOW ENGINE STATUS` | > 3 active locks |
| Disk usage | CloudWatch / Prometheus | > 80% |

### Runbook

```
1. Check Grafana dashboard → "Migration Health"
2. If errors: check migration_audit_log for failed batches
3. If data drift: run validation script → compare results
4. If rollback needed:
   a. Cancel all migration jobs
   b. Revert code: git checkout <pre-migration-tag>
   c. Restore data if corrupted
   d. Verify service health
5. Post-mortem within 24 hours
```

---

## Appendix: Checklist

- [ ] Schema changes reviewed by DBA team
- [ ] Migration scripts tested in staging with production-like data
- [ ] Rollback procedure tested end-to-end
- [ ] Monitoring dashboards created and alerts configured
- [ ] On-call team briefed and runbook shared
- [ ] Maintenance window communicated (if off-peak backfill required)
- [ ] Rollback snapshot taken before migration
