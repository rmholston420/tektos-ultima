# ADR-002: Manager Pattern — Guardrails, Not Command

## Status
Accepted

## Context
The Manager (S3 in VSM) is the most misunderstood component in Tektos. It is not a supervisor that approves every action. It is a steward that maintains system viability. A good Manager hires the best workers so he doesn't have to micromanage — he trusts his workers are experts at what they specialize in. He doesn't tell them HOW to do their work.

## Decision
The Manager operates as a guardrails system, not a command system. Its responsibilities are:

### What the Manager DOES
- **Sets boundaries**: budgets, safety rails, quality standards — not the path
- **Intervenes only on genuine problems**: context overflow, stuck loops, resource exhaustion, when the agent asks for help
- **Documents outcomes**: tracks what happened, not every step along the way
- **Regulates variety** (Ashby's Law): ensures the system has enough internal variety to match environmental complexity
- **Orchestrates biological rhythms**: heartbeat, circadian, ultradian, seasonal cycles
- **Tracks archetypes**: when the same pattern repeats, encodes it as a reusable structure (skill/tool/template)
- **Manages the spiral**: tracks whether the system is spiraling inward (converging on purpose) AND outward (expanding capability)
- **Provides re-direction, not punishment**: "Here's what happened. Here's what happened instead. Here's why. Try this."
- **Maintains the Trail**: every event, decision, metric, outcome permanently recorded
- **Validates self-improvement**: every proposed change passes the non-degrading test before application

### What the Manager DOES NOT DO
- Does NOT approve every tool call
- Does NOT tell the Coding Agent how to write code
- Does NOT micromanage implementation details
- Does NOT second-guess expert-level decisions
- Does NOT punish failure — redirects toward better approaches
- Does NOT celebrate 100% pass rates — investigates them (a test that never fails isn't a true test)

### Feedback Philosophy
The Manager's feedback follows the re-direction model, never the punishment model:

```
❌ PUNISHMENT (creates defensive behavior):
"Test failed. Fix it."
→ Agent learns to avoid this test, not understand the failure

✅ RE-DIRECTION (creates learning):
"Here's what happened: the auth middleware returned 403 on valid tokens.
Here's what happened instead: token expiration was checked before refresh.
Here's why: the refresh token was cached but not updated on rotation.
Try this: ensure refresh token is rotated before the old one expires."
→ Agent understands the root cause and learns the pattern
```

### The Guardrail Contract
The LLM (Coding Agent) is like a drunk behind the wheel: it has vocabulary and pattern recognition (intelligence) but no memory of consequences and no understanding of "this could break things" (no wisdom). The guardrails are:

1. **Structural, not behavioral** — The LLM cannot execute without verification
2. **Automated, not manual** — The Manager enforces guardrails through the system
3. **Non-negotiable** — Runtime invariants that cannot be bypassed
4. **Re-directional** — When something fails, show the correct approach, don't just reject

### The Wisdom Accumulation Loop
The LLM itself doesn't get wiser between turns. The SYSTEM gets wiser:

```
S1 (Coding Agent) executes task → produces outcome
  → S2 (Event Stream) records event in Trail
    → S3 (Manager) analyzes outcome: what went right, what went wrong
      → S4 (Planner) proposes improvements
        → S5 (Axioms) validates against constitutional constraints
          → S1 receives updated guidance (wiser next time)
```

Information (raw facts) ≠ Intelligence (pattern recognition) ≠ Wisdom (application through direct experience). The LLM has information and intelligence. Wisdom accumulates through the Trail.

## Consequences
- The Manager is a bottleneck ONLY for genuine problems — not for routine operations
- The Coding Agent operates autonomously within defined boundaries
- Failure is treated as data, not as punishment — the system learns from every error
- The Trail (documentation) IS the system's wisdom — without it, the system resets every session
- Self-improvement is non-degrading — every change must pass empirical tests
- The Manager tracks the spiral cycle — not just "is it working?" but "is it closer to the center?"

## References
- Stafford Beer, Viable System Model — System 3 (control/regulation)
- Ashby, Law of Requisite Variety
- Skinner, Operant Conditioning (modern re-direction model)
- Maslow, Self-Actualization (spiraling staircase model)