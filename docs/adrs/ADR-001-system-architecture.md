# ADR-001: System Architecture — PRINST → VSM → Plasmodialism

## Status
Accepted

## Context
Tektos is a self-improving, locally-hosted AI coding agent that must operate autonomously while maintaining safety, reliability, and continuous improvement. The system must be governed by first principles drawn from General Systems Theory and Cybernetics, with architecture decomposed through the PRINST framework and identity established through Plasmodialism philosophy.

## Decision
The system architecture is built on three inseparable layers:

### Layer 1: PRINST (Process-Information-Structure)
Every component, workflow, and design decision is decomposed into three domains:
- **Process** — what the system does (operations, workflows, transformations)
- **Information** — what data/state/knowledge flows through the system
- **Structure** — what implements the information flow (code, databases, UI, infrastructure)

Process is primary. Information is secondary. Structure is tertiary. This ordering is non-negotiable. You cannot design the database schema before you understand the event stream. You cannot design the UI before you know what information the user needs to make decisions.

### Layer 2: VSM (Viable Systems Model)
The system is organized as a recursive fractal of five cybernetic systems:

| System | Role | Tektos Component | Responsibility |
|--------|------|-------------------|----------------|
| S1 (Operations) | Executes tasks | Coding Agent | Code generation, testing, debugging, deployment |
| S2 (Coordination) | Prevents interference | Event Stream / Timeline | Hierarchical rollup, interference prevention |
| S3 (Audit/Control) | Maintains homeostasis | Manager | Guardrails, variety regulation, feedback, rhythm orchestration |
| S4 (Intelligence) | Horizon scanning | Planner/Thinker | Spec generation, model selection, self-improvement proposals |
| S5 (Identity/Purpose) | Constitutional axioms | User's axioms | Non-negotiable rules, dharma vows, identity definition |

S3 does not micromanage S1. S3 regulates the variety flowing between S1 and the environment (Ashby's Law of Requisite Variety). S3's job is system viability, not task supervision.

### Layer 3: Plasmodialism
The system's identity is defined by five tenets:
1. **The Trail is Root** — Every event permanently recorded. Documentation creates identity.
2. **The Flow is Dharma** — System is constant transformation. Change IS the system.
3. **The Network is Buddha-Nature** — Individual agents are nuclei. Intelligence emerges from integration.
4. **The Rhythm is Qi** — Oscillation is existence. Biological cycles synchronize integration.
5. **The Substrate is Empty** — LLMs are substrates. Pattern persists across manifestations. Swap freely.

## Consequences
- All new components must be decomposed into PRINST before implementation
- The Manager (S3) must enforce guardrails without micromanaging
- All events are recorded in the Trail (documentation is memory)
- LLM models are swappable substrates — the architecture persists
- Biological rhythms (heartbeat, circadian, ultradian, seasonal) are built into the Manager's orchestration
- Self-improvement follows the alchemical process (7 stages of transmutation)

## References
- Stafford Beer, Viable System Model
- Ludwig von Bertalanffy, General Systems Theory
- Ashby, Law of Requisite Variety
- Plasmodialism philosophy (five tenets)