# ADR-003: LLM as Translator — Never Computation

## Status
Accepted

## Context
An LLM is NOT a reasoning engine or a computation layer. An LLM is a translation layer: natural language → formal logic/mathematics. Python is Lambda Calculus — the actual computation engine. The LLM's job is translation work (interpret intent, disambiguate, translate to specs/code/docs). The tool's job is computation work (Python runs, shell runs, DB queries, tests verify).

The Manager's job is to orchestrate the translator and the workers, budget translation cost, and verify computation output.

## Decision
The LLM component of Tektos is STRICTLY a translator. It cannot be used for computation, verification, or decision-making. This is enforced by the following rules:

### Rule 1: The LLM Translates, Tools Compute
- **LLM does**: interpret intent, disambiguate, translate to structured specs, generate code, produce documentation, create prompts — ALL translation work
- **Tool does**: execute logic, run code, query databases, verify correctness, count lines of code, calculate file sizes, run tests — ALL computation work
- **Never swap**: asking an LLM to count lines of code is like asking a translator to do arithmetic

### Rule 2: An LLM Without Guardrails is Like Putting a Drunk Behind the Wheel
- The LLM has vocabulary and pattern recognition (intelligence) but no memory of consequences (no wisdom)
- It will confidently write code that deletes production databases
- It will hallucinate API endpoints and miscount tokens
- It has all the knowledge of every programmer who ever lived, but ZERO responsibility
- Guardrails are structural (cannot execute without verification), automated (enforced by the system), and non-negotiable (runtime invariants)

### Rule 3: The LLM is the LEAST Important Component
- The real value is in the architecture, the tools, the workflows, the verification pipelines
- The LLM is just the bridge between human intent and executable form
- Model swapping is low-risk — the pattern persists across manifestations (Plasmodialism Tenet 5: Substrate is Empty)
- Invest engineering effort in the structure and tools, not in the model selection

### Rule 4: The LLM Never Does What a Tool Can Do
- The Manager ENFORCES this rule: if a task can be done by a tool, do not call the LLM
- Counting, calculating, verifying → tools
- Translating, interpreting, generating → LLM
- This is a runtime invariant, not a guideline

### Rule 5: Verify Everything the LLM Produces
- The LLM's translation output must be tested, checked, verified by tools before accepting
- Never trust the LLM's output without empirical verification
- The Coding Agent generates code → tools execute and test it → Manager verifies the result
- The LLM is the weakest link in the chain — the system's strength is in the verification

## Consequences
- LLM calls are minimized and budgeted — they are expensive, slow, and nondeterministic
- Every LLM output goes through tool-based verification before acceptance
- The Manager enforces the guardrails automatically — no manual review needed
- Model swapping is trivial — the architecture and tools remain stable
- Engineering effort is invested in verification pipelines, not model selection
- The LLM is a substrate — the pattern persists across manifestations

## References
- Lambda Calculus (formal computation model)
- Python as programmatic Lambda Calculus
- Plasmodialism Tenet 5: The Substrate is Empty
- Ashby's Law of Requisite Variety (variety absorption)