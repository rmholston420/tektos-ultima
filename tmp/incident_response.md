# Incident Response Plan

## 1. Severity Levels

| Level | Definition | Response Time | Resolution Target |
|-------|-----------|---------------|-------------------|
| **P0 - Critical** | Complete outage, data loss, security breach, or widespread customer impact | Immediate (within 15 min) | 4 hours |
| **P1 - High** | Major feature degraded, significant portion of users affected, or no workaround | 30 min | 12 hours |
| **P2 - Medium** | Partial degradation, workaround available, limited user impact | 2 hours | 3 business days |
| **P3 - Low** | Minor issue, cosmetic, or internal tooling impact | 1 business day | Next release |

**Guidelines:**
- Default to the higher severity if uncertain
- Re-classify as severity changes during investigation
- P0/P1 require executive notification within 1 hour

---

## 2. Roles and Responsibilities

### Incident Commander (IC)
- Owns the incident response process end-to-end
- Makes tactical decisions on remediation approach
- Assigns roles and tasks to team members
- Ensures documentation and timeline are maintained
- Declares incident resolved when root cause is fixed and verified

### Comms Lead
- Manages all external and internal communications
- Updates status page with current information and ETA
- Drafts customer-facing emails and internal updates
- Ensures messaging is consistent and accurate
- Manages stakeholder expectations (executives, customers, partners)

### Tech Lead
- Leads technical investigation and remediation
- Coordinates engineers working on the fix
- Validates that fixes resolve the issue
- Documents technical findings and root cause
- Recommends preventive measures

### Supporting Roles (as needed)
- **On-call Engineer**: First responder for detection and initial triage
- **SRE/DevOps**: Infrastructure and deployment support
- **Security Engineer**: Handles security-related incidents
- **Product/Support**: Provides customer impact context and manages support tickets

---

## 3. Escalation Procedures

### Escalation Path

```
On-call Engineer (Detection & Triage)
    ↓ (within 30 min or if unable to resolve)
Incident Commander + Tech Lead
    ↓ (P0/P1 or within 1 hour without resolution)
Engineering Manager + VP Engineering
    ↓ (P0 or >2 hours unresolved)
CTO + Executive Team
```

### When to Escalate
- Unable to identify root cause within 30 minutes
- Impact is wider than initially assessed
- P1+ severity with no fix identified within 1 hour
- Security incident involving data exposure
- Customer-facing communication becomes necessary

### Contact List

| Role | Primary | Backup |
|------|---------|--------|
| On-call Engineer | [on-call channel/phone] | [backup on-call] |
| Incident Commander | [name / rotating] | [name / rotating] |
| Tech Lead | [name] | [name] |
| Engineering Manager | [name] | [name] |
| VP Engineering | [name] | [name] |
| Security Lead | [name] | [name] |
| Comms Lead | [name] | [name] |
| CTO | [name] | [name] |

> **Maintain this list and update after any personnel changes.**

### Emergency Contacts
- **PagerDuty / Alerting**: [integration link]
- **Slack #incidents**: [channel link]
- **Status Page**: [status page URL]
- **War Room (Video)**: [meeting link]

---

## 4. Communication Templates

### Status Page Update

```
## [Incident Title] — [Status: Investigating / Identified / Monitoring / Resolved]

**Last Updated:** [Time, UTC]
**Impact:** [Brief description of affected users/services]

**What's happening:**
[Clear, factual description of the issue]

**What we're doing:**
[Current actions being taken]

**Next update:** [Time of next update]
```

### Internal Update (Slack / Email)

```
🚨 INCIDENT UPDATE — [Title] — [Time]

Severity: P[0-3]
Status: [Investigating / Identified / Working on fix / Resolved]
IC: [Name]

Summary:
[Brief overview of the issue and current status]

Impact:
[Which services/users are affected and to what degree]

Actions Taken:
- [Action 1]
- [Action 2]

Next Steps:
- [What happens next]

Questions? → [Slack channel link]
```

### Customer Email

```
Subject: Update on [Service] — [Brief Description]

Hi [Customer/Team],

We're writing to inform you of an incident affecting [Service Name] that occurred on [Date] at approximately [Time].

**What happened:**
[Brief, non-technical description of the issue]

**Impact:**
[Describe what customers experienced — avoid technical jargon]

**Resolution:**
[Explain what was done to resolve the issue]

**Prevention:**
[What you're doing to prevent recurrence — be specific but not overly technical]

**Current Status:**
[Service is fully operational / Monitoring closely / etc.]

We sincerely apologize for the disruption. If you have questions or concerns, please reach out to [support email / link].

Thank you for your patience.

— The [Company] Team
```

### Executive Summary (P0/P1)

```
EXECUTIVE INCIDENT SUMMARY

Incident: [Title]
Date/Time: [Start] → [Resolution]
Duration: [X hours/minutes]
Severity: P[0-1]

Summary:
[2-3 sentence overview for non-technical leadership]

Business Impact:
- Users affected: [number/percentage]
- Revenue impact: [estimate if applicable]
- Support tickets: [number]

Root Cause:
[High-level explanation]

What We're Doing:
- [Fix 1]
- [Fix 2]

Next Steps:
- Post-incident review scheduled for [date]
- Preventive measures: [brief list]
```

---

## 5. Post-Incident Review Process

### Timeline

| Phase | When | Who |
|-------|------|-----|
| **Immediate Follow-up** | Within 24 hours of resolution | IC, Tech Lead |
| **Blameless Retrospective** | Within 5 business days | All participants |
| **Action Item Tracking** | Ongoing | IC / Tech Lead |
| **Follow-up Review** | 2-4 weeks after | IC, Engineering Manager |

### Retrospective Agenda

1. **Timeline Review** (15 min)
   - Walk through the incident chronology
   - Identify detection, response, and resolution times

2. **What Went Well** (10 min)
   - Effective responses and decisions
   - Good communication and coordination

3. **What Could Improve** (15 min)
   - Gaps in detection, response, or communication
   - Process or tooling deficiencies

4. **Root Cause Analysis** (15 min)
   - Use 5 Whys or similar method
   - Identify underlying systemic issues, not just surface causes

5. **Action Items** (10 min)
   - Assign owners and deadlines
   - Categorize as: immediate, short-term, long-term

### Action Item Format

```
- [ ] [Description] — Owner: [name] — Due: [date] — Priority: [P0-P3]
- [ ] [Description] — Owner: [name] — Due: [date] — Priority: [P0-P3]
```

### Follow-up

- Track all action items in project management tool
- Review progress in the 2-4 week follow-up meeting
- Update this plan if processes or templates need modification
- Share learnings with the broader team

### Documentation Checklist

- [ ] Incident timeline documented
- [ ] Root cause analysis completed
- [ ] Action items created and assigned
- [ ] Customer communications sent
- [ ] Status page updated to resolved
- [ ] Retrospective notes shared with team
- [ ] Plan updated (if lessons learned require changes)

---

## Quick Reference: Incident Workflow

```
1. DETECT  → Alert or customer report
2. TRIAGE  → On-call assesses severity, creates incident
3. NOTIFY  → IC assigned, war room opened, status page updated
4. INVEST  → Tech Lead investigates, IC coordinates
5. FIX     → Remediation implemented and verified
6. COMM    → Comms Lead provides updates until resolved
7. CLOSE   → IC declares resolved, status page updated
8. REVIEW  → Blameless retrospective within 5 business days
```

---

*This document should be reviewed and updated quarterly. Last updated: 2026-08-21*
