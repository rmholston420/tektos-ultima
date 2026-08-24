# Git Branching Strategy

## Overview

This document defines the branching strategy for our projects. It is based on GitFlow with lightweight adaptations for modern CI/CD workflows.

---

## Branch Types

### `main`
- **Purpose:** Production-ready code at all times.
- **Protection:** Branch protection rules enabled. No direct pushes.
- **Lifecycle:** Permanent.

### `develop`
- **Purpose:** Integration branch for the next release. Contains all completed features ready for the next production deployment.
- **Protection:** Branch protection rules enabled.
- **Lifecycle:** Permanent.

### `feature/*`
- **Purpose:** New functionality or enhancements.
- **Base:** Created from `develop`.
- **Merge target:** `develop`.
- **Lifecycle:** Temporary; deleted after merge.

### `release/*`
- **Purpose:** Prepare a new production release. Allows final bug fixes, documentation updates, and version bumps without blocking new feature development.
- **Base:** Created from `develop`.
- **Merge target:** `main` and back-merged into `develop`.
- **Lifecycle:** Temporary; deleted after completion.

### `hotfix/*`
- **Purpose:** Urgent fixes for production issues.
- **Base:** Created from `main`.
- **Merge target:** `main` and back-merged into `develop`.
- **Lifecycle:** Temporary; deleted after merge.

---

## When to Create Each Branch

| Branch Type | Trigger |
|---|---|
| `feature/*` | Starting any new feature, task, or improvement. |
| `release/*` | When `develop` is feature-complete and ready for QA/testing before a production release. |
| `hotfix/*` | When a critical bug is discovered in production that must be fixed immediately. |
| `main` / `develop` | Never create manually — these are maintained by the merge workflow. |

---

## Merge Workflow

All integrations into `main` or `develop` follow this process:

1. **Create a Pull Request (PR)** from your branch into the target branch.
2. **Code Review:** At least one other team member must review and approve the PR.
3. **CI Checks:** All CI pipeline checks (lint, test, build) must pass.
4. **Squash Merge:** Merge using **squash merge** to keep history clean. Each feature or fix results in a single, descriptive commit.
5. **Delete the source branch** after the merge is complete.

### Branch Protection Rules (Recommended)

- Require PR review approval before merging.
- Require status checks to pass before merging.
- Disallow force pushes.
- Require linear history (via squash merge).

---

## Naming Conventions

All branches must follow these patterns:

| Type | Pattern | Example |
|---|---|---|
| Feature | `feature/<ticket>-<short-description>` | `feature/PROJ-142-add-user-auth` |
| Release | `release/<version>` | `release/v2.3.0` |
| Hotfix | `hotfix/<ticket>-<short-description>` | `hotfix/PROJ-199-fix-payment-timeout` |

### Guidelines

- Use **kebab-case** (lowercase with hyphens).
- Keep descriptions **short and descriptive** (3–5 words).
- Include a **ticket/issue number** when applicable.
- Never use special characters or spaces.

---

## Quick Reference

```
main          ← production (always deployable)
  ↑ merge from: release/*, hotfix/*
develop       ← next release (integration)
  ↑ merge from: feature/*
  ↑ merge from: release/*, hotfix/* (back-merge)
feature/*     ← new work
release/*     ← release preparation
hotfix/*      ← urgent production fixes
```

---

## Best Practices

- Keep PRs **small and focused** — aim for a single logical change.
- Update your branch from the target branch **regularly** to avoid large merge conflicts.
- Write clear **commit messages** and **PR descriptions** that explain the "why."
- Delete branches after merging to keep the repository clean.
- Tag releases on `main` with semantic versioning (e.g., `v1.2.3`).
