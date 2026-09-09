"""Tests for SkillManager._execute_inline unknown-action dispatch (P7).

Before: unknown skill-step action was logged at DEBUG and silently no-op.
After: unknown action falls back to the injected ToolRegistry.dispatch().
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tektos.skills.manager import SkillManager
from tektos.skills.registry import Skill, SkillRegistry


class _RecordingRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def dispatch(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        self.calls.append((tool_name, tool_input))
        return "ok"


@pytest.fixture()
def sm(tmp_path):
    reg = SkillRegistry(db_path=str(tmp_path / "skills.db"), skill_dir=str(tmp_path))
    return SkillManager(registry=reg, skill_dir=str(tmp_path))


def _mk_skill(steps: list[dict[str, Any]]) -> Skill:
    return Skill(
        id="s1",
        name="t",
        description="",
        trigger_conditions=[],
        steps=steps,
    )


def test_unknown_action_dispatches_to_tool_registry(sm) -> None:
    tr = _RecordingRegistry()
    sm.set_tool_registry(tr)

    skill = _mk_skill([
        {"action": "bash", "description": "run", "input": {"cmd": "echo hi"}}
    ])

    asyncio.run(sm._execute_inline(skill, {}))

    assert tr.calls == [("bash", {"cmd": "echo hi"})]


def test_unknown_action_no_registry_is_noop(sm) -> None:
    skill = _mk_skill([{"action": "xyz", "description": "nope"}])
    asyncio.run(sm._execute_inline(skill, {}))


def test_known_action_still_bypasses_dispatch(sm) -> None:
    tr = _RecordingRegistry()
    sm.set_tool_registry(tr)

    skill = _mk_skill([
        {"action": "apply_lesson", "description": "remember"}
    ])
    asyncio.run(sm._execute_inline(skill, {}))

    assert tr.calls == []
