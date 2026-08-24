# Software Release Checklist

## 1. Pre-Release

### Code Freeze
- [ ] Merge all approved changes into the release branch
- [ ] Disable CI/CD pipelines for non-essential branches
- [ ] Confirm no new features are being developed on the release branch

### Testing
- [ ] Run full regression test suite — all tests pass
- [ ] Execute integration tests against staging environment
- [ ] Perform performance/load testing if applicable
- [ ] Run security scans (SAST/DAST) and resolve findings
- [ ] Conduct manual QA on critical user journeys
- [ ] Verify backward compatibility for APIs and data migrations

### Documentation
- [ ] Update CHANGELOG with release notes (features, fixes, breaking changes)
- [ ] Update API documentation if interfaces changed
- [ ] Review and update user-facing documentation
- [ ] Ensure version numbers are consistent across all artifacts

### Readiness
- [ ] Obtain sign-off from engineering, QA, and product owners
- [ ] Confirm deployment pipeline is configured and tested
- [ ] Prepare deployment runbook with step-by-step instructions

---

## 2. Release Day

### Deployment
- [ ] Notify team of release start via communication channel
- [ ] Take a database backup (if schema/data changes are involved)
- [ ] Deploy to staging for a final smoke test
- [ ] Deploy to production (follow runbook)
- [ ] Verify health checks pass on all services

### Monitoring
- [ ] Monitor error rates, response times, and throughput for 30+ minutes
- [ ] Watch key business metrics (orders, signups, transactions, etc.)
- [ ] Check logs for anomalies or unexpected patterns
- [ ] Confirm all dependent services are operating normally

### Rollback Plan
- [ ] Keep rollback artifacts (previous version binaries, DB migration scripts) readily available
- [ ] Pre-approve rollback decision authority
- [ ] **If critical issues are detected, execute rollback immediately** (see Section 4)

---

## 3. Post-Release

### Verification
- [ ] Confirm all services are stable after 1 hour
- [ ] Run smoke tests against production
- [ ] Validate key user flows in production
- [ ] Ensure monitoring alerts are properly configured for the new version

### Communication
- [ ] Announce successful release to stakeholders and team
- [ ] Update status page if public-facing
- [ ] Notify customer support of known issues or changes
- [ ] Close the release ticket and archive release artifacts

### Retrospective
- [ ] Schedule a brief post-release review (within 48 hours)
- [ ] Document any issues encountered during the release
- [ ] Capture lessons learned and process improvements
- [ ] Update this checklist based on retrospective findings

---

## 4. Rollback Procedure

**Trigger conditions:**
- Error rate exceeds defined threshold (e.g., >1% of requests fail)
- Critical feature is broken and cannot be hotfixed within 30 minutes
- Data integrity issues detected
- Performance degradation exceeds SLA

**Steps:**
1. **Assess:** Confirm the issue is release-related and severity warrants rollback
2. **Decide:** Rollback authority makes the go/no-go call (do not hesitate)
3. **Notify:** Inform the team and stakeholders of the rollback
4. **Revert code:** Deploy the previous stable version
5. **Revert data:** Run down-migration scripts if schema changes were applied
6. **Verify:** Confirm services are healthy and metrics return to normal
7. **Communicate:** Inform stakeholders that rollback is complete
8. **Investigate:** After rollback, diagnose root cause before attempting a new release

**Note:** Rollback is always preferred over attempting emergency fixes in production unless a hotfix can be validated and deployed within the SLA window.
