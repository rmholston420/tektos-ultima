"""Tests for SessionState and SessionStateManager — markdown I/O, dict conversion, persistence."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tektos.runtime.session_state import (
    SessionState,
    SessionStateManager,
    create_default_session_state,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_state(**overrides) -> SessionState:
    """Create a minimal SessionState with optional overrides."""
    base = SessionState(
        session_id="test-session-1",
        project="Tektos-Ultima-v1",
        timestamp=datetime.now(timezone.utc).isoformat(),
        objective="Build a feature",
        progress="In progress",
        completion_pct=50.0,
        current_file="src/main.py",
        current_command="pytest tests/",
        running_processes=["python server.py"],
        api_endpoints={"/health": "ok", "/api/sessions": "ok"},
        key_decisions=["Use aiogram 3.x"],
        constraints=["No external deps"],
        next_steps=["Write integration test", "Run coverage"],
        exact_commands=["pytest --cov", "python -m pytest"],
        blockers=["LLM endpoint down"],
        notes=["User wants green eyes highlighted"],
        referenced_files=["src/main.py", "tests/test_main.py"],
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


# ── SessionState — Serialization ────────────────────────────────────────────

class TestSessionStateSerialization:
    def test_to_dict_contains_all_fields(self):
        state = _make_state()
        d = state.to_dict()
        assert d["session_id"] == "test-session-1"
        assert d["project"] == "Tektos-Ultima-v1"
        assert d["objective"] == "Build a feature"
        assert d["completion_pct"] == 50.0
        assert d["key_decisions"] == ["Use aiogram 3.x"]
        assert d["api_endpoints"] == {"/health": "ok", "/api/sessions": "ok"}

    def test_from_dict_roundtrip(self):
        state = _make_state()
        d = state.to_dict()
        restored = SessionState.from_dict(d)
        assert restored.session_id == state.session_id
        assert restored.project == state.project
        assert restored.objective == state.objective
        assert restored.completion_pct == state.completion_pct
        assert restored.key_decisions == state.key_decisions
        assert restored.blockers == state.blockers
        assert restored.referenced_files == state.referenced_files

    def test_from_dict_partial(self):
        partial = {"session_id": "s2", "project": "P", "timestamp": "2026-01-01T00:00:00+00:00"}
        state = SessionState.from_dict(partial)
        assert state.session_id == "s2"
        assert state.project == "P"
        assert state.objective == ""  # defaults
        assert state.version == 1


# ── SessionState — Markdown ─────────────────────────────────────────────────

class TestSessionStateMarkdown:
    def test_to_markdown_header(self):
        state = _make_state()
        md = state.to_markdown()
        assert "# LAST_KNOWN_STATE.md" in md
        assert f"**Session:** {state.session_id}" in md
        assert f"**Project:** {state.project}" in md

    def test_to_markdown_objective(self):
        state = _make_state(objective="Build a feature")
        md = state.to_markdown()
        assert "## Objective" in md
        assert "Build a feature" in md

    def test_to_markdown_completion(self):
        state = _make_state(completion_pct=75.0)
        md = state.to_markdown()
        assert "**Completion:** 75.0%" in md

    def test_to_markdown_current_state(self):
        state = _make_state(current_file="src/main.py", current_command="pytest")
        md = state.to_markdown()
        assert "Current File" in md
        assert "`src/main.py`" in md
        assert "Current Command" in md
        assert "`pytest`" in md

    def test_to_markdown_key_decisions(self):
        state = _make_state(key_decisions=["Decision A", "Decision B"])
        md = state.to_markdown()
        assert "## Key Decisions" in md
        assert "1. Decision A" in md
        assert "2. Decision B" in md

    def test_to_markdown_next_steps(self):
        state = _make_state(next_steps=["Step 1", "Step 2"])
        md = state.to_markdown()
        assert "## Next Steps" in md
        assert "1. Step 1" in md
        assert "2. Step 2" in md

    def test_to_markdown_exact_commands(self):
        state = _make_state(exact_commands=["pytest --cov"])
        md = state.to_markdown()
        assert "## Exact Commands" in md
        assert "```bash" in md
        assert "pytest --cov" in md

    def test_to_markdown_blockers(self):
        state = _make_state(blockers=["LLM down"])
        md = state.to_markdown()
        assert "## Blockers" in md
        assert "🚫 LLM down" in md

    def test_to_markdown_notes(self):
        state = _make_state(notes=["User note"])
        md = state.to_markdown()
        assert "## Notes" in md
        assert "- User note" in md

    def test_to_markdown_task_list(self):
        state = SessionState(
            session_id="s1",
            project="P",
            timestamp=datetime.now(timezone.utc).isoformat(),
            todo_items=[
                {"content": "Finish test", "status": "completed"},
                {"content": "Fix bug", "status": "pending"},
            ],
        )
        md = state.to_markdown()
        assert "## Task List" in md
        assert "- [✓] Finish test" in md
        assert "- [○] Fix bug" in md

    def test_to_markdown_memory_context(self):
        state = _make_state(memory_context="Important context")
        md = state.to_markdown()
        assert "## Memory Context" in md
        assert "Important context" in md

    def test_to_markdown_referenced_files(self):
        state = _make_state(referenced_files=["src/main.py"])
        md = state.to_markdown()
        assert "## Referenced Files" in md
        assert "`src/main.py`" in md

    def test_to_markdown_empty_state(self):
        state = SessionState(
            session_id="s1",
            project="P",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        md = state.to_markdown()
        assert "# LAST_KNOWN_STATE.md" in md
        # Current State section is always emitted (even if empty)
        assert "## Current State" in md
        # No optional sections should appear
        assert "## Blockers" not in md


# ── SessionState — Markdown Parsing ─────────────────────────────────────────

class TestSessionStateParsing:
    def test_parse_objective(self):
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Objective

Build the feature

**Progress:** in progress
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert state.objective == "Build the feature"

    def test_parse_progress(self):
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Objective

Build the feature

**Progress:** halfway there
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert state.progress == "halfway there"

    def test_parse_completion_pct(self):
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Objective

Build the feature

**Completion:** 75%
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert state.completion_pct == 75.0

    def test_parse_next_steps(self):
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Objective

Build the feature

## Next Steps

1. Write test
2. Run coverage
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert state.next_steps == ["Write test", "Run coverage"]

    def test_parse_key_decisions(self):
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Key Decisions

1. Use aiogram 3.x
2. SQLite for events
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert state.key_decisions == ["Use aiogram 3.x", "SQLite for events"]

    def test_parse_blockers(self):
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Blockers

- 🚫 LLM endpoint down
- 🚫 Missing config
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert "LLM endpoint down" in state.blockers
        assert "Missing config" in state.blockers

    def test_parse_task_list(self):
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Task List

- [✓] Done task
- [○] Pending task
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert len(state.todo_items) == 2
        assert state.todo_items[0]["status"] == "completed"
        assert state.todo_items[1]["status"] == "pending"

    def test_parse_missing_optional_sections(self):
        md = f"""# LAST_KNOWN_STATE.md
**Session:** s1
**Project:** P
**Timestamp:** 2026-01-01T00:00:00+00:00

## Objective

Simple objective
"""
        state = SessionState.from_markdown(md, "s1", "P")
        assert state.objective == "Simple objective"
        assert state.next_steps == []
        assert state.key_decisions == []
        assert state.blockers == []


# ── SessionStateManager ─────────────────────────────────────────────────────

class TestSessionStateManager:
    def test_default_state_manager(self, tmp_path):
        mgr = SessionStateManager(
            session_id="s1",
            project="P",
            workspace=str(tmp_path),
        )
        assert mgr.session_id == "s1"
        assert mgr.project == "P"
        assert mgr.state_file == tmp_path / "LAST_KNOWN_STATE.md"

    def test_save_and_load_state(self, tmp_path):
        mgr = SessionStateManager(
            session_id="s1",
            project="P",
            workspace=str(tmp_path),
        )
        state = SessionState(
            session_id="s1",
            project="P",
            timestamp=datetime.now(timezone.utc).isoformat(),
            objective="Build something",
            progress="In progress",
            completion_pct=60.0,
        )
        mgr.save_state(state)
        loaded = mgr.load_state()
        assert loaded.session_id == "s1"
        assert loaded.objective == "Build something"
        assert loaded.completion_pct == 60.0

    def test_load_state_creates_default(self, tmp_path):
        mgr = SessionStateManager(
            session_id="s1",
            project="P",
            workspace=str(tmp_path),
        )
        loaded = mgr.load_state()
        assert loaded.session_id == "s1"
        assert loaded.objective == "Initialize session"
        assert loaded.progress == "Starting work"
        assert len(loaded.next_steps) == 3

    def test_update_state(self, tmp_path):
        mgr = SessionStateManager(
            session_id="s1",
            project="P",
            workspace=str(tmp_path),
        )
        state = mgr.load_state()
        updated = mgr.update_state(objective="New objective", next_steps=["Step A"])
        assert updated.objective == "New objective"
        assert "Step A" in updated.next_steps

    def test_save_full_snapshot_increments_version(self, tmp_path):
        mgr = SessionStateManager(
            session_id="s1",
            project="P",
            workspace=str(tmp_path),
        )
        state = mgr.load_state()
        orig_version = state.version
        mgr.save_full_snapshot(state)
        assert state.version == orig_version + 1

    def test_state_file_created_on_disk(self, tmp_path):
        mgr = SessionStateManager(
            session_id="s1",
            project="P",
            workspace=str(tmp_path),
        )
        state = mgr.load_state()
        mgr.save_state(state)
        assert mgr.state_file.exists()
        content = mgr.state_file.read_text()
        assert "# LAST_KNOWN_STATE.md" in content

    def test_update_state_merges_lists(self, tmp_path):
        mgr = SessionStateManager(
            session_id="s1",
            project="P",
            workspace=str(tmp_path),
        )
        state = mgr.load_state()
        state.next_steps = ["Step A"]
        mgr.save_state(state)
        updated = mgr.update_state(next_steps=["Step B"])
        assert "Step A" in updated.next_steps
        assert "Step B" in updated.next_steps


# ── create_default_session_state ────────────────────────────────────────────

class TestCreateDefaultSessionState:
    def test_creates_default(self):
        state = create_default_session_state("s1", "P")
        assert state.session_id == "s1"
        assert state.project == "P"
        assert state.objective == "Initialize session"
        assert len(state.next_steps) == 3
