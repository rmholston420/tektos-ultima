"""Tektos memory system.

Modules:
- experience_replay.py: ExperienceReplay — bridges SynthesisEngine → Planner
- memory_system.py: MemorySystem — unified memory facade
- reflection_engine.py: ReflectionEngine — Hegelian reflection (S2→S3)
- synthesis_engine.py: SynthesisEngine — reflection → actionable guidance

Self-improvement loop:
SynthesisEngine → ExperienceReplay → Planner.plan(synthesis_guidance) → BuildSpec
"""
