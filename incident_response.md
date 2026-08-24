# Incident Response Plan

## 1. Severity Levels

| Level | Definition | Response Time | Resolution Target |
|-------|-----------|---------------|-------------------|
| **P0** | Complete outage or data loss affecting all users | Immediate (15 min) | 2 hours |
| **P1** | Major functionality degraded for significant user base | 30 min | 4 hours |
| **P2** | Partial degradation or workaround available | 2 hours | 24 hours |
| **P3** | Minor issue, no workaround needed, low user impact | Next business day | 1 week |

**Guidelines:**
- P0/P1: All-hands war room, status page updated every 30 min
- P2: Dedicated channel, status page updated every 2 hours
- P3: Standard ticketing queue, no public status page update

---

## 2. Roles and Responsibilities

### Incident Commander (IC)
- Owns the incident response process
- Makes triage and escalation decisions
- Assigns tasks and tracks progress
- Primary point of contact for leadership
- Declares incident resolution

### Communications Lead
- Drafts all external and internal communications
- Maintains status page accuracy
- Monitors social media and support channels for customer feedback
- Escalates customer sentiment to IC

### Tech Lead
- Leads technical investigation and resolution
- Assigns engineering tasks
- Provides technical status updates to IC
- Validates root cause and fix before resolution

### On-Call Engineer
- Initial responder and triage
- Implements fix under Tech Lead direction
- Documents findings for post-incident review

---

## 3. Escalation Procedures

### Escalation Path
1. **On-Call Engineer** → attempts initial triage and mitigation
2. **Tech Lead** → if issue persists >15 min or requires deeper investigation
3. **Incident Commander** → if P0/P1 or cross-team coordination needed
4. **Engineering Manager / VP Eng** → if business impact requires executive awareness
5. **C-Suite** → if customer trust, legal, or PR risk is significant

### Contact List

| Role | Primary | Backup | Channel |
|------|---------|--------|---------|
| On-Call Engineer | Rotating schedule | Next in rotation | PagerDuty |
| Tech Lead | eng-lead@company.com | senior-eng@company.com | Slack `#incident` |
| Incident Commander | ic-rotator@company.com | eng-manager@company.com | Slack `#incident` |
| Communications Lead | comms-lead@company.com | marketing@company.com | Slack `#incident` |
| Engineering Manager | eng-mgr@company.com | vp-eng@company.com | Phone |
| Legal / PR | legal@company.com | pr@company.com | Phone |

> **Note:** Rotate IC and On-Call duties weekly. Update contacts quarterly.

---

## 4. Communication Templates

### Status Page Update

```
## [P#] [Issue Summary]

**Severity:** P0/P1/P2/P3
**Last Updated:** [Timestamp]
**Impact:** [Brief description of affected users/services]

**What happened:**
[One-sentence summary]

**What we're doing:**
[Current investigation or fix status]

**Next update:** [Timestamp]
```

### Internal Update (Slack / Email)

```
🚨 INCIDENT: [Issue Summary]
Severity: P#
Opened: [Time]
IC: [Name]

**Impact:** [Who/what is affected]
**Current Status:** [Investigation / Mitigation / Fix / Monitoring]
**Next Steps:** [1-3 bullet points]
**Update Channel:** [Link]
**Next Update:** [Time]
```

### Customer Email

```
Subject: Update on [Service] Issues

Hi [Customer/Team],

We're investigating an issue affecting [service/component]. Some users may be
experiencing [specific symptoms].

**What we know:**
- Issue began at [time]
- [Brief explanation, no blame]

**What we're doing:**
- [Action 1]
- [Action 2]

**Estimated resolution:** [Time or "We'll update by X"]

Track progress: [Status page link]

We'll provide another update in [timeframe].

— The [Company] Team
```

---

## 5. Post-Incident Review

### When
- P0/P1: Within 48 hours of resolution
- P2: Within 1 week
- P3: Optional, based on lessons learned

### Process

1. **Gather Data**
   - Timeline from monitoring/alerting systems
   - Chat logs from incident channel
   - All status page and communication records

2. **Hold Retrospective Meeting** (30-60 min)
   - Attendees: IC, Tech Lead, On-Call Engineers, Communications Lead
   - Review timeline together
   - Discuss: What went well? What didn't? What surprised us?

3. **Write Blameless Post-Mortem**
   - Summary (2-3 sentences)
   - Timeline of events
   - Root cause analysis (use 5 Whys)
   - Impact assessment (users affected, duration, revenue)
   - What went well
   - What could improve

4. **Action Items**
   - Categorize: Prevent, Detect, Respond, Improve
   - Assign owner and due date
   - Prioritize by impact
   - Track in project management tool

5. **Follow-Up**
   - Review action items at next team standup
   - Reopen post-mortem when items are complete
   - Share learnings in company-wide newsletter

### Action Item Template

| Item | Owner | Due Date | Category | Status |
|------|-------|----------|----------|--------|
| Add monitoring for [specific metric] | @name | [date] | Detect | Open |
| Runbook update: [procedure] | @name | [date] | Respond | Open |
| Add automated rollback for [change] | @name | [date] | Prevent | Open |

---

## Quick Reference

**When in doubt, escalate.** A P2 escalated is better than a P0 that wasn't.

**War Room Setup:**
- Create Slack channel: `#incident-[date]-[short-desc]`
- Start a call/bridge for real-time coordination
- Open status page draft in parallel
- Assign a scribe to document timeline

**Resolution Criteria:**
- Root cause identified
- Fix deployed and verified
- Monitoring confirms stability for [15 min / 1 hour]
- All workarounds removed
- Customer communications sent
- Post-mortem scheduled
