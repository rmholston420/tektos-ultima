# Code Review Guidelines

## 1. Reviewer Checklist

### Functionality
- [ ] Does the code behave as intended?
- [ ] Are all edge cases and error paths handled?
- [ ] Does it match the requirements / ticket description?
- [ ] Are there any regressions in existing functionality?

### Style
- [ ] Code follows project conventions (naming, formatting, structure)
- [ ] No dead code, hardcoded values, or debug leftovers
- [ ] Imports are organized and unused ones removed
- [ ] Comments explain *why*, not *what*

### Security
- [ ] No secrets, API keys, or credentials in code
- [ ] Inputs are validated and sanitized
- [ ] AuthN / AuthZ checks are in place where needed
- [ ] Dependencies are up to date and free of known vulnerabilities

### Performance
- [ ] No unnecessary loops, N+1 queries, or expensive operations in hot paths
- [ ] Memory usage is reasonable (no leaks, proper resource cleanup)
- [ ] Caching is considered for repeated/expensive operations
- [ ] Scalability concerns are noted if applicable

---

## 2. Reviewer Etiquette

- **Be constructive.** Critique the code, not the person. Use "we" instead of "you."
- **Be timely.** Aim to review PRs within 24 hours. Blocked? Say so and give an ETA.
- **Ask questions, don't command.** Instead of *"Change this,"* try *"What do you think about trying…?"*
- **Distinguish must-fix from nice-to-have.** Label suggestions clearly as `🔴 blocker`, `🟡 suggestion`, or `🟢 nit`.
- **Acknowledge good work.** Point out well-written code, clever solutions, or thorough tests.
- **Don't wait for perfection.** Ship early, iterate often. Leave follow-up tickets for non-critical items.

---

## 3. Author Responsibilities

- **Self-review before submitting.** Run linters, formatters, and tests locally.
- **Write a clear PR description.** Include:
  - What changed and why
  - Any trade-offs or known limitations
  - Screenshots or logs for UI / behavioral changes
- **Keep PRs small.** Aim for 200–400 lines. Split large changes into focused PRs.
- **Address feedback promptly.** Respond to comments (even just "acknowledged") and push fixes in a timely manner.
- **Update documentation.** READMEs, API docs, or inline comments should reflect changes.
- **Include or update tests.** New features need tests; bug fixes need regression tests.

---

## 4. Sample Review Comment Format

```
🔴 [Blocker] /src/auth.py:42 — The token is decoded without verifying the signature.
   Risk: This allows forged tokens to pass authentication.
   Suggestion: Use `jwt.decode(token, key, algorithms=["HS256"])` instead.
```

```
🟡 [Suggestion] /src/user_service.py:17 — Consider using a dict lookup instead of a linear scan.
   Current: iterating over all users to find a match → O(n)
   Suggested: build a `user_by_id = {u.id: u for u in users}` for O(1) lookups.
```

```
🟢 [Nit] /src/utils.py:8 — Minor: rename `data` to `raw_input` for clarity.
```

---

## Quick Reference

| Principle        | Do ✅                          | Don't ❌                        |
|------------------|--------------------------------|--------------------------------|
| Tone             | "What if we tried…"            | "This is wrong."               |
| Scope            | One focused PR                 | Kitchen-sink PRs               |
| Timing           | Review within 24h              | Leave PRs hanging for days     |
| Feedback         | Specific, actionable comments  | Vague "this doesn't feel right"|
| Approval         | Approve when ready             | Approve without reading        |
