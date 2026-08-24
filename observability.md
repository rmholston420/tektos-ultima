# Observability Platform Implementation Plan

> **Goal:** Build a unified observability platform across the three pillars (logs, metrics, traces) with actionable alerting, clear dashboards, and cost-controlled retention.

---

## 1. Current State Assessment

| Pillar | Current State | Gaps |
|---|---|---|
| **Logging** | Unstructured app logs on individual servers; log rotation in place | No central aggregation; no structured format; difficult to correlate across services |
| **Metrics** | Scattered node-level metrics; some custom scripts | No unified time-series store; no service-level metrics; no SLO tracking |
| **Tracing** | None | No distributed tracing; blind spots in cross-service latency |

**Immediate Actions:**
- Inventory all services and their deployment targets (container, VM, bare metal).
- Identify critical user journeys to prioritize tracing and SLO definition.
- Map existing monitoring tools and data sources to avoid duplication.

---

## 2. Three Pillars Implementation

### 2.1 Logs — Structured Logging

- **Format:** Adopt structured JSON logging in all services (include `service`, `environment`, `trace_id`, `level`, `message`, `timestamp`).
- **Agent:** Deploy **Fluent Bit** as a lightweight log forwarder on every host/container.
- **Backend:** Forward structured logs to **Loki** (lightweight, cost-efficient) or **Elasticsearch** if full-text search is required.
- **Correlation:** Inject `trace_id` into log entries to link logs with traces.
- **Quick wins:**
  - Add structured logging libraries to top 5 highest-traffic services within 2 weeks.
  - Configure Fluent Bit sidecars in Kubernetes; `stdout/stderr` capture for containerized apps.

### 2.2 Metrics — Prometheus

- **Stack:** Prometheus server(s) with long-term storage (Cortex/Mimir or Thanos for scaling).
- **Instrumentation:**
  - Use official client libraries per language (Go, Python, Java, Node.js, etc.).
  - Expose standard counters, gauges, and histograms.
  - Label all metrics with `service`, `env`, `version`, and `instance`.
- **Service Discovery:** Use Kubernetes `ServiceMonitor` CRDs for automatic scraping.
- **Quick wins:**
  - Deploy Prometheus and Grafana in a staging cluster within 1 week.
  - Instrument the payment service first as a pilot (high business value).

### 2.3 Traces — Jaeger

- **Backend:** Jaeger (all-in-one mode for small scale; distributed mode with Cassandra/ES for large scale).
- **Instrumentation:** Add OpenTelemetry SDK to services; configure Jaeger exporter.
- **Sampling:** Start with adaptive sampling — 100% for error traces, 10% for production traffic, 100% for debug endpoints.
- **Integration:**
  - Propagate `trace_id` as `traceparent` (W3C Trace Context) across HTTP/gRPC.
  - Cross-link traces in Grafana dashboards and logs in Loki.
- **Quick wins:**
  - Deploy Jaeger in staging within 1 week.
  - Instrument 3 services end-to-end to validate propagation before rollout.

---

## 3. Alerting Strategy

### 3.1 SLOs and Error Budgets

- **Define SLOs** for every critical service:
  - **Availability SLO:** e.g., 99.9% of requests succeed (HTTP 2xx/3xx).
  - **Latency SLO:** e.g., 95th percentile P99 < 500ms.
  - **Correctness SLO:** e.g., 99.95% of orders complete without data loss.
- **Error budgets:** Track remaining budget per service per month. Alert when budget is consumed at >50% remaining time.

### 3.2 Alert Rules (Prometheus Alertmanager)

| Severity | Condition | Response Time |
|---|---|---|
| **P0 — Critical** | SLO budget burning fast (e.g., >80% consumed in 1 hour); core service down | < 5 min |
| **P1 — High** | Error rate spike (>5%); P99 latency breach | < 15 min |
| **P2 — Medium** | Disk/memory threshold breach; deployment failure | < 1 hour |
| **P3 — Low** | Warning-level log volume spike; minor latency increase | Next business day |

- **Deduplication:** Group alerts by service and environment.
- **Silencing:** Auto-silence during known deployments (use deployment webhook).

### 3.3 Notification Channels

- **P0/P1:** PagerDuty + Slack `#alerts-critical` + SMS fallback.
- **P2:** Slack `#alerts-general` + email digest.
- **P3:** Slack `#observability` daily digest.
- **Runbooks:** Every alert must link to an inline runbook (stored in repo, linked via annotation).

---

## 4. Dashboard Design

### 4.1 Executive View (15-min refresh)

| Panel | Description |
|---|---|
| Overall system health | Composite score based on SLO compliance across all services |
| Error budget burn rate | Per-service error budget remaining (red/amber/green) |
| Active incidents | Count and severity of open incidents |
| Top services by revenue impact | Ranked list of services driving the most traffic/revenue |

*Audience: Engineering leadership, on-call managers.*

### 4.2 Operational View (30-sec refresh)

| Panel | Description |
|---|---|
| Request rate & error rate | Per-service, time-series with SLO threshold overlay |
| P50 / P95 / P99 latency | Latency percentiles with anomaly detection |
| Top 10 slowest endpoints | Ranked list of slowest API endpoints |
| Recent deployments | Timeline of deployments correlated with metric changes |
| Error log stream | Real-time error log feed (last 500 entries) |

*Audience: On-call engineers, SRE team.*

### 4.3 Service-Level View (30-sec refresh)

| Panel | Description |
|---|---|
| Service map | Live dependency graph with latency and error coloring |
| Trace sampling | Recent trace list with latency breakdown |
| Resource utilization | CPU, memory, disk I/O per instance |
| Connection pool / queue depth | Backend dependency health (DB, cache, queue) |
| Custom business metrics | Service-specific KPIs (orders/min, transactions/sec) |

*Audience: Service owners, developers.*

**Tool:** Grafana as the unified frontend; templates per tier for reuse.

---

## 5. Data Retention and Cost Management

### 5.1 Retention Tiers

| Tier | Data | Retention | Storage | Cost Strategy |
|---|---|---|---|---|
| **Hot** | Metrics, traces, recent logs | 15 days | SSD / local disk | Prometheus WAL + Loki active index |
| **Warm** | Aggregated metrics (5m, 1h), traces | 30 days | HDD / cloud block | Thanos Compact / Cortex downsampling |
| **Cold** | Raw logs, full traces | 90 days (or per compliance) | Object storage (S3/GCS) | Loki chunks → S3; Jaeger traces → S3 archive |
| **Archive** | Compliance logs | 1–7 years (per policy) | Glacier / cheap object | Lifecycle policies with auto-transition |

### 5.2 Cost Controls

- **Metrics:** Downsample raw data every 15 min to 5 min, then 5 min to 1h. Drop high-cardinality labels not used in queries.
- **Traces:** Enforce sampling policy; archive traces older than 30 days to S3 and delete from Jaeger index.
- **Logs:** Drop debug-level logs in production; compress logs at rest; use Loki's `retention_deletes_enabled` to purge old chunks.
- **Budgets:** Set monthly spend alerts per storage tier; review quarterly.

---

## 6. Integration Plan

### 6.1 Existing Tools

| Tool | Integration |
|---|---|
| **Kubernetes** | Prometheus `ServiceMonitor` + Fluent Bit DaemonSet + OpenTelemetry Collector sidecar |
| **CI/CD (e.g., GitHub Actions)** | Emit deployment events to Alertmanager for auto-silencing and dashboard annotations |
| **PagerDuty** | Alertmanager integration for P0/P1 escalation |
| **Slack** | Alertmanager webhook + Grafana alert notifications |
| **Service Mesh (Istio/Linkerd)** | Export mesh telemetry to Prometheus and inject trace context |

### 6.2 Custom Exporters

- **BMC (Business Metric Collector):** Export custom business KPIs (orders, signups, revenue) as Prometheus metrics.
- **Health Exporter:** Expose readiness/liveness probe status as a metric for dashboard inclusion.
- **Third-party API metrics:** Wrap external API calls with a metrics exporter for dependency tracking.

### 6.3 Log Agents

| Target | Agent | Config |
|---|---|---|
| **Kubernetes pods** | Fluent Bit (DaemonSet) | Parse `stdout/stderr` JSON; add `kubernetes.*` metadata labels |
| **Bare-metal / VM** | Fluent Bit (systemd) | Tail journalctl logs; tag with host labels |
| **Legacy apps (no structured logs)** | Logstash or Fluent Bit file input | Regex parsing; enrich with `service` and `env` tags |
| **Cloud services (RDS, SQS, etc.)** | CloudWatch Agent → Fluent Bit | Stream CloudWatch logs into Loki |

### 6.4 Rollout Phases

| Phase | Duration | Scope |
|---|---|---|
| **Phase 1 — Foundation** | Weeks 1–2 | Deploy Prometheus, Grafana, Jaeger, Loki; configure Fluent Bit in staging |
| **Phase 2 — Pilot** | Weeks 3–5 | Instrument 3 pilot services; define first SLOs; build executive dashboard |
| **Phase 3 — Expand** | Weeks 6–10 | Roll out to all production services; implement alerting rules; build operational dashboards |
| **Phase 4 — Harden** | Weeks 11–12 | Tune retention; cost review; runbook library; chaos testing of alerting pipeline |

---

## Appendix: Key Metrics Checklist

- [ ] HTTP request rate, error rate, latency (P50/P95/P99)
- [ ] SLO compliance and error budget burn rate
- [ ] Deployment frequency and change failure rate (DORA metrics)
- [ ] CPU, memory, disk, network per instance
- [ ] Database query latency and connection pool saturation
- [ ] Queue depth and processing latency
- [ ] Trace span counts and error rates per service
- [ ] Log error/warning count per service per hour
- [ ] Active alert count by severity
- [ ] Mean time to detect (MTTD) and mean time to resolve (MTTR)
