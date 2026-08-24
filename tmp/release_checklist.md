# Software Release Checklist

## Pre-Release

### Code Freeze
- [ ] Announce code freeze to the team
- [ ] Ensure all planned features are merged to the release branch
- [ ] Block additional merges except for critical hotfixes (approved by lead)
- [ ] Tag the release candidate commit

### Testing
- [ ] Run full automated test suite — all tests pass
- [ ] Run integration and end-to-end tests
- [ ] Perform manual QA on critical user journeys
- [ ] Verify backward compatibility (API contracts, database migrations)
- [ ] Conduct performance/load testing if applicable
- [ ] Confirm security scan results are clean
- [ ] Sign-off from QA lead

### Documentation
- [ ] Update CHANGELOG with release notes
- [ ] Update API documentation (if applicable)
- [ ] Review user-facing changes for clarity
- [ ] Update deployment/runbook documentation
- [ ] Verify database migration scripts are documented

---

## Release Day

### Deployment
- [ ] Create release tag and build artifacts
- [ ] Deploy to staging environment for final smoke test
- [ ] Confirm smoke tests pass on staging
- [ ] Deploy to production (use approved deployment procedure)
- [ ] Run database migrations (if any)
- [ ] Clear application caches
- [ ] Verify health checks pass

### Monitoring
- [ ] Monitor error rates and logs for anomalies
- [ ] Watch key performance metrics (latency, throughput)
- [ ] Verify all dependent services are healthy
- [ ] Confirm alerting is active and functional
- [ ] Assign an on-call engineer to watch for issues

### Rollback Plan (see Rollback Procedure below)
- [ ] Confirm rollback procedure is understood by all on-call
- [ ] Ensure previous version artifacts are still available
- [ ] Keep database migration rollback scripts ready
- [ ] Decide rollback trigger criteria (e.g., error rate > 1%, P99 latency spike)

---

## Post-Release

### Verification
- [ ] Smoke test production environment
- [ ] Verify key user flows in production
- [ ] Confirm feature flags are set correctly
- [ ] Validate monitoring dashboards are accurate

### Communication
- [ ] Send release announcement to stakeholders
- [ ] Notify support team of known issues (if any)
- [ ] Update status page if there are known outages or limitations
- [ ] Close the release in project management tools

### Retrospective
- [ ] Schedule a brief retrospective within 2 business days
- [ ] Document what went well and what didn't
- [ ] Capture action items for future releases
- [ ] Archive release artifacts and notes

---

## Rollback Procedure

If rollback is triggered, follow these steps:

1. **Assess** — Confirm the issue severity and scope. Is it a partial failure or full outage?
2. **Announce** — Notify the team and stakeholders that a rollback is underway.
3. **Stop** — Halt any ongoing deployments or automated processes.
4. **Revert** —
   - Revert to the previous application version/artifact
   - Roll back database migrations only if necessary (prefer forward-compatible migrations)
   - Re-deploy the previous version to production
5. **Verify** —
   - Run smoke tests on the rolled-back version
   - Confirm error rates and performance have returned to normal
6. **Communicate** —
   - Inform stakeholders the rollback is complete
   - Log the incident and root cause
7. **Investigate** — Determine why the release failed and address before attempting a redeploy.

> **Rule of thumb:** If you can't resolve the issue within 30 minutes, roll back first, diagnose later.
