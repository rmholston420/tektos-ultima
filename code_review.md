# Code Review Guidelines

## 1. Reviewer Checklist

Before approving a pull request, work through each category below:

### Functionality
- [ ] Does the code fulfill the stated requirements?
- [ ] Are edge cases and error conditions handled?
- [ ] Is the logic correct and free of bugs?
- [ ] Are there any unintended side effects or regressions?
- [ ] Do existing tests still pass?

### Style
- [ ] Consistent with project style conventions
- [ ] Clear, descriptive names for variables and functions
- [ ] Well-organized, readable structure
- [ ] No code smells (duplication, excessive complexity, long functions)
- [ ] No dead or unnecessary code

### Security
- [ ] Input validation and sanitization in place
- [ ] Sensitive data (passwords, tokens, keys) properly protected
- [ ] Authentication/authorization checks where needed
- [ ] No SQL injection, XSS, or common vulnerabilities
- [ ] Dependencies up to date and free of known vulnerabilities

### Performance
- [ ] No obvious performance bottlenecks
- [ ] Database queries optimized (no N+1, proper indexing)
- [ ] Reasonable memory usage (no leaks, unnecessary allocations)
- [ ] Expensive operations cached where appropriate
- [ ] Scales with increasing data volume

---

## 2. Reviewer Etiquette

- **Be constructive.** Focus on the code, not the person. Explain *why* a change is needed.
  - ✅ *"Consider using a map here for O(1) lookups"*
  - ❌ *"This is inefficient"*
- **Be timely.** Respond within 1–2 business days. Stale PRs block progress.
- **Be respectful.** Acknowledge good work. Not every suggestion is mandatory—discuss trade-offs.
- **Be specific.** Point to exact lines and explain the impact.
- **Know when to approve.** Small, well-tested PRs meeting all criteria should be approved promptly.
- **Escalate when needed.** If you can't resolve a disagreement, involve a tech lead.

---

## 3. Author Responsibilities

- **Self-review first.** Read your own diff line-by-line before submitting. Fix obvious issues.
- **Keep PRs small.** One feature or fix per PR. Split large changes.
- **Write clear descriptions.** Include context, rationale, and testing instructions.
- **Add/update tests.** Cover happy paths, edge cases, and error conditions.
- **Update documentation.** Reflect changes in README, inline comments, or API docs.
- **Respond to feedback.** Address comments promptly. Disagree? Explain your reasoning.
- **Keep PRs current.** Rebase or merge latest changes to avoid conflicts.

---

## 4. Sample Review Comment Format

```
📍 File: `src/auth/login.ts`, Line 42

**Issue**: Password is stored in plain text in the session object.

**Suggestion**: Hash the password before storing it using `bcrypt.hash()`.
This prevents credential exposure in case of a session leak.

**Example**:
```ts
// Before
req.session.password = password;

// After
req.session.password = await bcrypt.hash(password, 10);
```

**Priority**: 🔴 High
```

---

## Quick Reference

| Rule | Description |
|------|-------------|
| One purpose per PR | Changes should be cohesive and focused |
| 2–3 reviewers minimum | Ensure diverse perspectives |
| CI must pass | No merging without passing checks |
| Discuss, don't dictate | Use questions and suggestions over commands |
| Auto-close stale PRs | PRs inactive for 14 days may be closed |
