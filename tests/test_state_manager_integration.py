"""Integration tests for LAST_KNOWN_STATE.md workflow.

Tests the complete state persistence cycle: create → save → load → update → snapshot.
Validates round-trip fidelity, incremental updates, and default templates.
"""

import json
import tempfile
from pathlib import Path

import pytest

# Import the actual state manager classes
from tektos.runtime.state_manager import (
    LastKnownState,
    StateManager,
    create_default_state,
)


# ---------------------------------------------------------------------------
# LastKnownState dataclass tests
# ---------------------------------------------------------------------------

class TestLastKnownStateRoundTrip:
    """Test LastKnownState serialization/deserialization round-trips."""

    def test_to_dict_from_dict_roundtrip(self):
        """to_dict() → from_dict() should produce equivalent state."""
        original = LastKnownState(
            project="tektos",
            timestamp="2026-08-14T12:00:00Z",
            session_id="test-123",
            objective="Build feature X",
            progress="75% complete",
            completion_pct=75.0,
            current_file="src/tektos/main.py",
            current_command="uvicorn tektos.main:app --reload",
            running_processes=["uvicorn:8020", "next:3003"],
            api_endpoints={"/health": "200 OK", "/api/sessions": "active"},
            key_decisions=["Use SQLite for event store", "REST-first API"],
            constraints=["GPU temp ≤ 80°C", "100GB HDD free"],
            notes=["User prefers dark mode"],
            next_steps=["Run tests", "Commit changes"],
            exact_commands=["pytest -v", "git add -A && git commit -m 'test'"],
            blockers=["Waiting for API key from user"],
            todo_items=[
                {"content": "Fix auth", "status": "pending"},
                {"content": "Write docs", "status": "completed"},
            ],
            environment={"PYTHONPATH": ".", "NODE_ENV": "development"},
            memory_context="Session handoff via SESSION_HANDOFF.md",
            referenced_files=["src/tektos/main.py", "tests/test_rest_contract.py"],
        )
        
        # Round-trip through dict
        data = original.to_dict()
        restored = LastKnownState.from_dict(data)
        
        # All fields should match
        assert restored.project == original.project
        assert restored.session_id == original.session_id
        assert restored.objective == original.objective
        assert restored.progress == original.progress
        assert restored.completion_pct == original.completion_pct
        assert restored.current_file == original.current_file
        assert restored.current_command == original.current_command
        assert restored.running_processes == original.running_processes
        assert restored.api_endpoints == original.api_endpoints
        assert restored.key_decisions == original.key_decisions
        assert restored.constraints == original.constraints
        assert restored.notes == original.notes
        assert restored.next_steps == original.next_steps
        assert restored.exact_commands == original.exact_commands
        assert restored.blockers == original.blockers
        assert restored.todo_items == original.todo_items
        assert restored.environment == original.environment
        assert restored.memory_context == original.memory_context
        assert restored.referenced_files == original.referenced_files

    def test_to_markdown_from_markdown_roundtrip(self):
        """to_markdown() → from_markdown() should preserve key fields."""
        original = LastKnownState(
            project="tektos",
            timestamp="2026-08-14T12:00:00Z",
            session_id="test-123",
            objective="Build feature X",
            progress="75% complete",
            completion_pct=75.0,
            current_file="src/tektos/main.py",
            next_steps=["Run tests", "Commit changes"],
            blockers=["Waiting for API key"],
        )
        
        # Serialize to markdown
        md = original.to_markdown()
        
        # Verify markdown structure
        assert "# LAST_KNOWN_STATE.md" in md
        assert "**Project:** tektos" in md
        assert "**Session:** test-123" in md
        assert "## Objective" in md
        assert "Build feature X" in md
        assert "**Progress:** 75% complete" in md
        assert "**Completion:** 75.0%" in md
        assert "## Current State" in md
        assert "**Current File:** `src/tektos/main.py`" in md
        assert "## Next Steps" in md
        assert "1. Run tests" in md
        assert "2. Commit changes" in md
        assert "## Blockers" in md
        assert "Waiting for API key" in md

    def test_empty_state_markdown(self):
        """Minimal state should produce valid markdown with only required fields."""
        state = LastKnownState(
            project="minimal",
            timestamp="2026-01-01T00:00:00Z",
        )
        
        md = state.to_markdown()
        assert "# LAST_KNOWN_STATE.md" in md
        assert "**Project:** minimal" in md
        # Optional sections should not appear when empty
        assert "## Key Decisions" not in md
        assert "## Blockers" not in md
        assert "## Next Steps" not in md

    def test_dict_serialization_is_json_safe(self):
        """to_dict() output must be JSON-serializable."""
        state = LastKnownState(
            project="test",
            timestamp="2026-08-14T12:00:00Z",
            session_id="abc-123",
            objective="Test",
            progress="10%",
            completion_pct=10.0,
            current_file="test.py",
            current_command="pytest",
            running_processes=["proc1", "proc2"],
            api_endpoints={"/api": "ok"},
            key_decisions=["A", "B"],
            constraints=["C"],
            notes=["N"],
            next_steps=["S1"],
            exact_commands=["cmd"],
            blockers=["B1"],
            todo_items=[{"content": "T", "status": "pending"}],
            environment={"KEY": "VAL"},
            memory_context="M",
            referenced_files=["f1"],
        )
        
        data = state.to_dict()
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed["project"] == "test"
        assert parsed["session_id"] == "abc-123"


# ---------------------------------------------------------------------------
# StateManager persistence tests
# ---------------------------------------------------------------------------

class TestStateManagerPersistence:
    """Test StateManager save/load with real file I/O."""

    def setup_method(self):
        """Create a temporary directory for each test."""
        self.tmpdir = tempfile.mkdtemp()
        self.state_manager = StateManager(
            project="tektos-test",
            workspace=self.tmpdir,
        )

    def test_save_and_load_state(self):
        """save_state() → load_state() should preserve all data."""
        state = LastKnownState(
            project="tektos-test",
            timestamp="2026-08-14T12:00:00Z",
            session_id="test-123",
            objective="Build feature X",
            progress="75% complete",
            completion_pct=75.0,
            current_file="src/tektos/main.py",
            next_steps=["Run tests", "Commit"],
            blockers=["Waiting for key"],
        )
        
        # Save
        self.state_manager.save_state(state)
        
        # Verify file was written
        assert self.state_manager.state_file.exists()
        md = self.state_manager.state_file.read_text()
        assert "Build feature X" in md
        
        # Load (new StateManager instance simulates fresh session)
        fresh_sm = StateManager(
            project="tektos-test",
            workspace=self.tmpdir,
        )
        loaded = fresh_sm.load_state()
        
        # Verify round-trip
        assert loaded.project == "tektos-test"
        assert loaded.objective == "Build feature X"
        assert loaded.progress == "75% complete"
        assert loaded.completion_pct == 75.0
        assert loaded.current_file == "src/tektos/main.py"
        assert loaded.next_steps == ["Run tests", "Commit"]
        assert loaded.blockers == ["Waiting for key"]

    def test_load_nonexistent_returns_default(self):
        """load_state() with no existing file should return empty state."""
        fresh_sm = StateManager(
            project="tektos-test",
            workspace=self.tmpdir,
        )
        loaded = fresh_sm.load_state()
        
        assert loaded.project == "tektos-test"
        assert loaded.objective == ""
        assert loaded.progress == ""
        assert loaded.next_steps == []
        assert loaded.blockers == []

    def test_update_state_incrementally(self):
        """update_state() should modify fields in-place and persist."""
        # Start with a state
        state = LastKnownState(
            project="tektos-test",
            timestamp="2026-08-14T12:00:00Z",
            objective="Initial",
            next_steps=["Step 1"],
        )
        self.state_manager.save_state(state)
        
        # Incrementally update
        updated = self.state_manager.update_state(
            objective="Updated objective",
            progress="50% done",
            next_steps=["Step 2", "Step 3"],
        )
        
        # Verify update
        assert updated.objective == "Updated objective"
        assert updated.progress == "50% done"
        # next_steps should have both original and new (extend behavior for lists)
        assert "Step 1" in updated.next_steps
        assert "Step 2" in updated.next_steps
        assert "Step 3" in updated.next_steps
        
        # Verify persistence
        fresh_sm = StateManager(
            project="tektos-test",
            workspace=self.tmpdir,
        )
        reloaded = fresh_sm.load_state()
        assert reloaded.objective == "Updated objective"
        assert "Step 2" in reloaded.next_steps


# ---------------------------------------------------------------------------
# Default state template tests
# ---------------------------------------------------------------------------

class TestCreateDefaultState:
    """Test create_default_state() template generation."""

    def test_default_state_has_required_fields(self):
        """Template should include all required fields."""
        state = create_default_state("my-project")
        
        assert state.project == "my-project"
        assert state.timestamp is not None
        assert state.objective == "Initialize project"
        assert state.progress == "Setting up project structure"

    def test_default_state_has_next_steps(self):
        """Template should include default next steps."""
        state = create_default_state("my-project")
        
        assert len(state.next_steps) == 3
        assert "Initialize git repository" in state.next_steps
        assert "Create project structure" in state.next_steps
        assert "Set up development environment" in state.next_steps

    def test_default_state_has_empty_lists(self):
        """Template should have empty collections for optional fields."""
        state = create_default_state("my-project")
        
        assert state.key_decisions == []
        assert state.constraints == []
        assert state.exact_commands == []
        assert state.blockers == []
        assert state.todo_items == []
        assert state.environment == {}
        assert state.memory_context == ""
        assert state.referenced_files == []
        assert state.notes == []


# ---------------------------------------------------------------------------
# Integration: full workflow
# ---------------------------------------------------------------------------

class TestFullWorkflow:
    """Test complete state workflow: create → save → load → update → re-load."""

    def test_complete_workflow(self):
        """End-to-end: simulate a session's state lifecycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sm = StateManager(project="workflow-test", workspace=tmpdir)
            
            # 1. Session starts: create default state
            state = create_default_state("workflow-test")
            state.session_id = "sess-001"
            sm.save_state(state)
            
            # 2. Verify initial state persisted
            loaded = sm.load_state()
            assert loaded.project == "workflow-test"
            assert loaded.session_id == "sess-001"
            assert loaded.objective == "Initialize project"
            
            # 3. During work: incrementally update
            updated = sm.update_state(
                objective="Building REST API",
                progress="40% complete",
                completion_pct=40.0,
                current_file="src/tektos/main.py",
                next_steps=["Implement health check", "Implement session CRUD"],
                key_decisions=["Use FastAPI TestClient for testing"],
                blockers=[],
            )
            
            # 4. Verify updates persisted
            sm.save_state(updated)
            fresh_sm = StateManager(project="workflow-test", workspace=tmpdir)
            reloaded = fresh_sm.load_state()
            
            assert reloaded.objective == "Building REST API"
            assert reloaded.progress == "40% complete"
            assert reloaded.completion_pct == 40.0
            assert reloaded.current_file == "src/tektos/main.py"
            assert "Implement health check" in reloaded.next_steps
            assert "Implement session CRUD" in reloaded.next_steps
            assert reloaded.key_decisions == ["Use FastAPI TestClient for testing"]
            
            # 5. Session ends: save final state
            final = sm.update_state(
                objective="REST API complete",
                progress="100% complete",
                completion_pct=100.0,
                next_steps=["Run full test suite", "Commit changes"],
            )
            sm.save_state(final)
            
            # 6. New session resumes from saved state
            new_sm = StateManager(project="workflow-test", workspace=tmpdir)
            resumed = new_sm.load_state()
            
            assert resumed.objective == "REST API complete"
            assert resumed.completion_pct == 100.0
            assert "Run full test suite" in resumed.next_steps
            assert "Commit changes" in resumed.next_steps
            
            # 7. Verify markdown file is human-readable
            md = fresh_sm.state_manager.state_file.read_text() if hasattr(fresh_sm, 'state_manager') else sm.state_file.read_text()
            assert "# LAST_KNOWN_STATE.md" in md
            assert "REST API complete" in md


# ---------------------------------------------------------------------------
# Run with: pytest tests/test_state_manager_integration.py -v
# ---------------------------------------------------------------------------
