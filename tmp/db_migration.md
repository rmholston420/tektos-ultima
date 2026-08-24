# Database Schema Migration Plan

> **Date:** 2026-08-21
> **Scope:** v3.4 → v3.5 schema migration
> **Target:** PostgreSQL 15+ / MySQL 8.0+

---

## 1. Schema Changes Overview

### New Tables

| Table | Purpose | Key Columns |
|---|---|---|
| `audit_logs` | Immutable audit trail | `id`, `entity_type`, `entity_id`, `action`, `changed_by`, `changed_at`, `old_values` (JSONB) |
| `user_preferences` | Per-user settings | `user_id` (FK), `key`, `value` (JSONB), `updated_at` |
| `job_queue` | Async job processing | `id`, `job_type`, `payload` (JSONB), `status`, `retry_count`, `created_at`, `scheduled_at` |

### Column Changes

| Table | Column | Change | Rationale |
|---|---|---|---|
| `users` | `email` | Add `UNIQUE` constraint | Prevent duplicate accounts |
| `orders` | `status` | Add new enum value `'refunded'` | Support refund workflow |
| `orders` | `total_amount` | Change from `DECIMAL(10,2)` → `DECIMAL(12,4)` | Support micro-currency precision |
| `products` | `sku` | Add `NOT NULL` + `UNIQUE` | Enforce data quality |
| `orders` | `shipping_address_id` | Add new FK column (nullable) | Decouple address from user profile |

### New Indexes

| Index | Table | Columns | Type |
|---|---|---|---|
| `idx_orders_status_created` | `orders` | `(status, created_at DESC)` | B-tree |
| `idx_audit_logs_entity` | `audit_logs` | `(entity_type, entity_id)` | B-tree |
| `idx_job_queue_status` | `job_queue` | `(status, scheduled_at)` | B-tree (partial, WHERE status = 'pending') |
| `idx_products_sku` | `products` | `sku` | B-tree (unique) |

---

## 2. Zero-Downtime Migration Approach

This migration uses a **zero-downtime** strategy based on the expand/contract pattern:

### Phase 1 — Schema Expansion (Deploy First)

1. **Add new columns as nullable** — never add `NOT NULL` or constraints on existing columns in the first deploy.
2. **Create new tables** — backfill will happen gradually.
3. **Add new indexes `CONCURRENTLY`** (PostgreSQL) or online DDL (MySQL) to avoid table locks.
4. **Deploy application code** that writes to both old and new columns (dual-write).

### Phase 2 — Backfill & Transition (Deploy Second)

1. Run the **ETL migration** (see Section 3) to populate new columns/tables.
2. Gradually shift application reads from old columns to new columns.
3. Validate data parity between old and new storage.

### Phase 3 — Schema Contraction (Deploy Third, after monitoring period)

1. Add `NOT NULL` constraints once data is confirmed complete.
2. Add `UNIQUE` constraints.
3. Remove deprecated columns (after a safe retirement period).

---

## 3. ETL Data Migration Steps

### ETL Pipeline: Orders Table

| Step | Action | Command / Logic |
|---|---|---|
| 1 | Validate source data | `SELECT COUNT(*) FROM orders WHERE total_amount IS NULL;` |
| 2 | Backfill `shipping_address_id` | `UPDATE orders SET shipping_address_id = COALESCE(shipping_address_id, (SELECT id FROM shipping_addresses WHERE user_id = orders.user_id LIMIT 1)) WHERE shipping_address_id IS NULL;` |
| 3 | Migrate `total_amount` precision | `UPDATE orders SET total_amount = total_amount::numeric(12,4);` |
| 4 | Populate `audit_logs` for existing records | Generate audit entries for last 30 days of changes |
| 5 | Populate `job_queue` from pending orders | `INSERT INTO job_queue (job_type, payload, status) SELECT 'fulfill', to_jsonb(o), 'pending' FROM orders WHERE status = 'processing' AND NOT EXISTS (SELECT 1 FROM job_queue j WHERE j.entity_id = o.id);` |

### ETL Validation Checks

```sql
-- 1. Row count parity
SELECT COUNT(*) FROM orders;
SELECT COUNT(*) FROM orders_backup_v34;

-- 2. Sum verification (total_amount)
SELECT SUM(total_amount) FROM orders;
SELECT SUM(total_amount) FROM orders_backup_v34;

-- 3. NULL check on migrated columns
SELECT COUNT(*) FROM orders WHERE shipping_address_id IS NULL AND status != 'draft';

-- 4. Foreign key integrity
SELECT o.id FROM orders o LEFT JOIN shipping_addresses sa ON o.shipping_address_id = sa.id WHERE sa.id IS NULL;
```

### Rollback Data

- **Snapshot before migration:** Full `pg_dump` / `mysqldump` of affected tables stored in encrypted S3 bucket (`s3://db-backups/migration-pre-<date>.sql.gz`).
- **Dual-write buffer:** For 48 hours post-migration, all writes go to both old and new columns so stale reads remain safe.
- **Audit log of migration:** Every ETL step is recorded in the `migration_run` table with timestamp, rows affected, and status.

---

## 4. Testing Strategy

### Staging Environment

- [ ] Run full ETL pipeline on anonymized production data copy.
- [ ] Verify all validation queries return expected results.
- [ ] Run application integration tests against migrated schema.
- [ ] Load test: simulate 2× production traffic during migration.

### Canary Deployment

- [ ] Deploy migration to 5% of production replicas.
- [ ] Monitor error rates, latency, and database CPU for 2 hours.
- [ ] Verify `audit_logs` are being populated correctly.
- [ ] If error rate < 0.1% and latency p99 < 200ms → proceed.

### Production Validation

- [ ] Run full ETL with `--dry-run` flag first (no writes).
- [ ] Execute migration with 10% traffic routing.
- [ ] Compare checksums of migrated data against source.
- [ ] Promote to 50% → 100% traffic in 30-minute increments.
- [ ] Monitor for 24 hours before contracting schema.

---

## 5. Rollback Plan & Monitoring

### Rollback Triggers

| Trigger | Threshold | Action |
|---|---|---|
| Error rate | > 1% for 5 min | Halt migration, revert code |
| Latency p99 | > 500ms for 5 min | Pause ETL, investigate |
| Data inconsistency | Any failed validation check | Rollback, restore from snapshot |
| Disk usage | > 85% | Pause, add capacity or archive |

### Rollback Procedure

1. **Stop** the migration runner (`migration-control --stop`).
2. **Revert** application code to pre-migration version.
3. **Restore** database from pre-migration snapshot if needed.
4. **Verify** rollback: run validation queries from Section 3.
5. **Document** root cause before re-attempt.

### Monitoring & Alerting

- **Database metrics:** CPU, connections, replication lag, lock waits (via Prometheus + Grafana).
- **Application metrics:** Error rate, request latency, queue depth.
- **Data quality:** Custom alerts on validation query failures (run every 15 min via cron).
- **Audit trail:** All migration steps logged to structured logging with correlation IDs.
- **Runbook:** Available at `internal-wiki/runbooks/db-migration-v35`.

### Post-Migration Checklist

- [ ] All validation queries pass.
- [ ] No active alerts for > 24 hours.
- [ ] Application feature flags for dual-write can be removed.
- [ ] Pre-migration snapshot retention policy reviewed (keep 30 days).
- [ ] Team retrospective completed.

---

*End of migration plan.*
