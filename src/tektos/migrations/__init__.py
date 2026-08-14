"""
Tektos-Ultima-v1 — Dynamic Schema Migration Engine.

The databases are the brain's memory. This engine allows the agent to
evolve its own storage schemas — not just records, but the structure
that shapes those records.

Exports:
    SchemaEvolutionEngine — introspect → detect → propose → apply → verify
"""

from .schema_evolution import SchemaEvolutionEngine

__all__ = ["SchemaEvolutionEngine"]
