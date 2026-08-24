"""Tektos-Ultima-v1 — Skill System

Skills are reusable procedures that Tektos can automatically create, select, and execute.

Architecture:
  SkillRegistry (SQLite skill_registry table)
      ↓
  SkillManager (creation, selection, execution orchestration)
      ↓
  SkillExecutor (runtime that loads and runs skill steps)
      ↓
  /api/skills (REST) + self-improvement integration

Skill lifecycle:
  1. Discovery — self-improvement engine or reflection engine identifies a reusable pattern
  2. Creation — SkillManager creates a skill entry in the registry and writes a SKILL.md file
  3. Selection — SkillManager matches skills to current context via trigger conditions
  4. Execution — SkillExecutor runs the skill's steps in order
  5. Evaluation — Self-improvement engine evaluates the skill's effectiveness
  6. Retention — Successful skills are retained; failed skills are archived or deleted
"""

from .registry import Skill, SkillRegistry
from .manager import SkillManager
from .executor import SkillExecutor

__all__ = ["Skill", "SkillRegistry", "SkillManager", "SkillExecutor"]
