# Internal Developer Platform (IDP) Plan

> **Version:** 1.0  
> **Date:** 2026-08-21  
> **Status:** Draft  

---

## 1. Platform Vision & Goals

### Vision

An IDP that eliminates operational friction so engineering teams can focus on shipping product features — not plumbing.

### Goals

| Goal | Description |
|------|-------------|
| **Developer Experience** | Reduce onboarding from weeks to hours. Provide a single, intuitive interface for all development workflows. |
| **Self-Service** | Enable developers to provision infrastructure, deploy services, and access tools without manual requests or wait times. |
| **Standardization** | Enforce golden configurations and best practices by default, while allowing controlled customization. |
| **Velocity** | Cut time-to-production for new services from days to minutes. |
| **Reliability** | Improve platform-wide SLOs through standardized patterns and automated guardrails. |

### Success Metrics

- Developer satisfaction score ≥ 4.2/5 (quarterly survey)
- Average time to first deploy < 30 minutes
- Reduction in manual ops requests by 60%
- Platform adoption rate > 75% of engineering teams within 12 months

---

## 2. Core Services

### 2.1 CI/CD Pipeline Service

- Unified pipeline templates (build → test → scan → deploy → verify)
- Multi-cloud and on-prem deployment targets
- Rollback automation and canary deployment support
- Pipeline-as-code with version-controlled configuration

### 2.2 Service Catalog

- Central registry of all services, components, and APIs
- Rich metadata: owner, tier, SLOs, dependencies, compliance status
- Searchable, filterable, with API for programmatic access
- Lifecycle management: create → promote → deprecate → retire

### 2.3 Golden Paths (Scaffolding)

- Pre-built templates for common application types (web API, worker, data pipeline, frontend)
- Includes: CI/CD config, monitoring, logging, security scanners, deployment manifests
- One-command generation: `idp create service --template=api --language=go`
- Templates evolve centrally; teams consume via versioned references

### 2.4 Infrastructure Provisioning

- Declarative infrastructure (IaC) via Terraform/Pulumi backends
- Environment templates (dev, staging, prod) with policy enforcement
- Automated resource quotas and namespace isolation
- Cost attribution per team/service through tagged resources

### 2.5 Shared Component Library

- Auth, rate limiting, service mesh, observability — all as reusable modules
- Versioned, tested, and supported by the platform team
- Clear upgrade paths and deprecation notices

---

## 3. Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│              Developer Portal                   │
│           (Backstage-style UI)                  │
├──────────────┬──────────┬───────────────────────┤
│   Web App    │   CLI    │    API Gateway        │
├──────────────┴──────────┴───────────────────────┤
│              Platform Core                       │
│  ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │ Catalog  │ │ Pipeline │ │ Provisioning    │  │
│  │ Service  │ │  Service │ │   Service       │  │
│  └──────────┘ └──────────┘ └─────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │ Golden   │ │ Plugin   │ │  Auth /         │  │
│  │ Paths    │ │ Ecosystem│ │  RBAC           │  │
│  └──────────┘ └──────────┘ └─────────────────┘  │
├──────────────┬──────────┴───────────────────────┤
│              Infrastructure Layer                │
│  Kubernetes  │  Cloud Providers  │  CI/CD       │
│  Clusters    │  (AWS/GCP/Azure)  │  Runners     │
└──────────────┴──────────────────────────────────┘
```

### Key Design Principles

- **Backstage-style portal** — Open-source compatible, extensible, with a unified developer dashboard
- **API-first** — Every platform capability exposed via REST/GraphQL APIs; CLI is a thin wrapper
- **Plugin ecosystem** — Teams can build and publish plugins (scaffolders, integrations, custom tools)
- **Extensibility** — YAML-based plugin descriptors; no framework lock-in
- **Observability** — Platform metrics, audit logs, and tracing built in from day one

### Technology Stack (Initial)

| Layer | Technology |
|-------|-----------|
| Portal | Backstage (or equivalent) |
| API | Go/TypeScript, REST + GraphQL |
| CI/CD | GitHub Actions / GitLab CI + Argo CD |
| Infra | Terraform, Kubernetes, Helm |
| Auth | OIDC + SAML, OAuth2 |
| Catalog | Backstage catalog + custom DB |
| Hosting | Internal Kubernetes cluster(s) |

---

## 4. Implementation Phases

### Phase 1 — MVP (Months 1–3)

**Objective:** Prove value with a narrow scope and 2–3 pilot teams.

- Deploy Backstage portal on internal cluster
- Implement service catalog (manual + YAML-based)
- Create 2 golden path templates (Go API, Python service)
- Basic CI/CD integration (GitHub Actions → deploy to staging)
- Single auth provider (OIDC)
- **Pilot:** 2 engineering teams, 5–10 services

**Exit criteria:**
- Pilot teams can scaffold, deploy, and monitor a service end-to-end
- Zero critical bugs in production portal
- Satisfaction score ≥ 3.5/5 from pilot teams

### Phase 2 — Beta (Months 4–7)

**Objective:** Expand capabilities and onboard 50% of engineering.

- Full golden path library (4+ templates)
- Infrastructure provisioning with environment templates
- Automated compliance scanning in pipeline
- Plugin system v1 (scaffolders + integrations)
- Service-to-service dependency mapping in catalog
- Cost tagging and basic reporting
- **Onboarding:** All teams invited; dedicated office hours

**Exit criteria:**
- 50% of services using the platform
- CI/CD deploy time < 15 minutes (median)
- Satisfaction score ≥ 4.0/5

### Phase 3 — General Availability (Months 8–12)

**Objective:** Mature the platform as the default development environment.

- Advanced plugin marketplace (community-built plugins)
- Multi-cluster and multi-cloud provisioning
- SLO-based deployments with automated rollback
- Self-service environment creation (dev/staging)
- Advanced catalog features (impact analysis, API docs, contract testing)
- Automated deprecation and sunsetting workflows
- **Target:** 80%+ platform adoption; legacy tooling deprecated

**Exit criteria:**
- 80% of new services created on platform
- Manual ops requests reduced by 60%
- Satisfaction score ≥ 4.2/5
- Platform team operates at 1–2 FTE for maintenance

---

## 5. Adoption Strategy

### Training & Onboarding

- **New-hire track:** 2-hour guided workshop + sandbox environment
- **Team champions:** Identify 1–2 advocates per team for peer support
- **Office hours:** Weekly 1-hour drop-in sessions during beta
- **Video library:** Short screencasts for common workflows

### Documentation

- **Quickstart guide:** Scaffold → deploy in < 10 minutes
- **Golden path docs:** Per-template usage, customization, and examples
- **API reference:** Auto-generated from OpenAPI/GraphQL schema
- **FAQ & troubleshooting:** Community-maintained wiki
- **Change log:** All platform updates documented in portal

### Feedback Loops

| Mechanism | Frequency | Purpose |
|-----------|-----------|---------|
| In-app feedback button | Continuous | Quick pain points |
| Quarterly survey | Quarterly | Satisfaction & priorities |
| Platform council | Monthly | Feedback from team champions |
| Slack channel `#platform` | Continuous | Day-to-day support |
| Bug bounty (internal) | Ongoing | Proactive issue discovery |

### Adoption Metrics

- Weekly active users (WAU)
- Template usage distribution
- Pipeline success rate
- Time-to-first-deploy (new teams)
- Platform vs. non-platform service ratio
- Support ticket volume and resolution time

---

## 6. Governance

### Standards

- All services use platform-maintained golden paths by default
- Required metadata in catalog (owner, tier, SLO, contact)
- Standardized logging (structured JSON), metrics (OpenTelemetry), and tracing
- Branch protection and PR template requirements for platform repos

### Compliance

- **Security scanning:** SAST, DAST, and dependency checks mandatory in pipeline
- **Secrets management:** Vault or equivalent; no secrets in code
- **Data classification:** Tagged in catalog; access policies enforced
- **Audit trail:** All platform actions logged with user and timestamp
- **Compliance reports:** Generated on demand for SOC2/ISO audits

### Cost Management

- **Tagging:** Every resource tagged with team, service, and environment
- **Quotas:** Per-team resource limits enforced at namespace level
- **Reporting:** Monthly cost reports by team/service in the portal
- **Right-sizing:** Automated recommendations for underutilized resources
- **Budget alerts:** Slack notifications at 80% and 100% of team budget

### Security

- **Least privilege:** RBAC with role-based access to platform features
- **Supply chain:** Signed container images, SBOM generation, policy enforcement
- **Vulnerability SLA:** Critical CVEs patched within 48 hours
- **Pen testing:** Annual third-party assessment of platform
- **Incident response:** Platform runbooks and war-room procedures documented

---

## Appendix: Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Platform becomes a bottleneck | High | Self-service design; async provisioning; SLA on platform responses |
| Low adoption due to poor DX | High | Pilot with real teams early; iterate on feedback; champion program |
| Over-engineering early | Medium | MVP scope tightly controlled; phase gates with go/no-go criteria |
| Team resistance to standards | Medium | Golden paths reduce effort vs. DIY; show time-savings data |
| Platform team scaling | High | Plugin ecosystem shifts burden to teams; clear support model |

---

*This plan is a living document. Review and update quarterly with the platform council.*
