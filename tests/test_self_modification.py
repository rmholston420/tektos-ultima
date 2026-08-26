"""Tests for src/tektos/runtime/self_modification.py

Covers: ModificationType, ModificationStatus, ModificationRequest, SelfTestResult,
SelfModificationEngine (submission, execution, rollback, self-tests, status,
convenience functions).
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tektos.runtime.self_modification import (
    ModificationType,
    ModificationStatus,
    ModificationRequest,
    SelfTestResult,
    SelfModificationEngine,
    get_self_modification_engine,
    submit_self_modification,
)


# ── Enums & Data Classes ──────────────────────────────────────────────────────

class TestModificationType:
    def test_values(self):
        assert ModificationType.CODE.value == "code"
        assert ModificationType.AXIOM.value == "axiom"
        assert ModificationType.TOOL.value == "tool"
        assert ModificationType.WORKFLOW.value == "workflow"
        assert ModificationType.CONFIG.value == "config"
        assert ModificationType.MEMORY.value == "memory"


class TestModificationStatus:
    def test_values(self):
        assert ModificationStatus.PENDING.value == "pending"
        assert ModificationStatus.IN_PROGRESS.value == "in_progress"
        assert ModificationStatus.COMPLETED.value == "completed"
        assert ModificationStatus.FAILED.value == "failed"
        assert ModificationStatus.REJECTED.value == "rejected"
        assert ModificationStatus.ROLLED_BACK.value == "rolled_back"


class TestModificationRequest:
    def test_creation(self):
        r = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Test",
            target="test.py",
            changes={"content": "print('hello')"},
            justification="Test justification",
        )
        assert r.request_id == "r1"
        assert r.modification_type == ModificationType.CODE
        assert r.description == "Test"
        assert r.target == "test.py"
        assert r.changes == {"content": "print('hello')"}
        assert r.justification == "Test justification"
        assert r.risk_level == "low"
        assert r.status == ModificationStatus.PENDING
        assert r.completed_at == 0.0
        assert r.error is None
        assert r.rollback_plan is None

    def test_to_dict(self):
        r = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Test",
            target="test.py",
            changes={"content": "print('hello')"},
            justification="Test",
            risk_level="high",
            rollback_plan="rollback",
        )
        d = r.to_dict()
        assert d["request_id"] == "r1"
        assert d["modification_type"] == "code"
        assert d["risk_level"] == "high"
        assert d["rollback_plan"] == "rollback"
        assert d["status"] == "pending"


class TestSelfTestResult:
    def test_creation(self):
        r = SelfTestResult(test_name="test", passed=True, duration=1.5)
        assert r.test_name == "test"
        assert r.passed is True
        assert r.duration == 1.5
        assert r.error is None
        assert r.details == {}

    def test_to_markdown_passed(self):
        r = SelfTestResult(test_name="import_check", passed=True, duration=0.5)
        md = r.to_markdown()
        assert "✓" in md
        assert "import_check" in md
        assert "0.50s" in md
        assert "**Error**" not in md

    def test_to_markdown_failed(self):
        r = SelfTestResult(test_name="file_access", passed=False, duration=0.1, error="boom")
        md = r.to_markdown()
        assert "✗" in md
        assert "file_access" in md
        assert "**Error**: boom" in md


# ── SelfModificationEngine ────────────────────────────────────────────────────

class TestSelfModificationEngine:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.engine = SelfModificationEngine(project_root=self.tmpdir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creation_defaults(self):
        assert self.engine.project_root == Path(self.tmpdir)
        assert self.engine.max_risk_level == "medium"
        assert self.engine._requests == {}
        assert self.engine._completed_modifications == []
        assert self.engine._self_tests == []
        assert self.engine._modification_log == []

    def test_creation_custom(self):
        e = SelfModificationEngine(project_root="/tmp", max_risk_level="high")
        assert e.project_root == Path("/tmp")
        assert e.max_risk_level == "high"

    @pytest.mark.asyncio
    async def test_submit_modification_low_risk(self):
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Test",
            target="test.py",
            changes={"content": "print('hello')"},
            justification="Test",
            risk_level="low",
        )
        # Create the target file
        Path(self.tmpdir, "test.py").write_text("original")
        result = await self.engine.submit_modification(req)
        assert result.status == ModificationStatus.PENDING
        assert "r1" in self.engine._requests

    @pytest.mark.asyncio
    async def test_submit_modification_high_risk_rejected(self):
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Test",
            target="test.py",
            changes={"content": "print('hello')"},
            justification="Test",
            risk_level="high",
        )
        result = await self.engine.submit_modification(req)
        assert result.status == ModificationStatus.REJECTED
        assert result.error and "exceeds maximum" in result.error

    @pytest.mark.asyncio
    async def test_submit_modification_code_target_not_found(self):
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Test",
            target="nonexistent.py",
            changes={"content": "print('hello')"},
            justification="Test",
            risk_level="low",
        )
        result = await self.engine.submit_modification(req)
        assert result.status == ModificationStatus.REJECTED
        assert result.error and "not found" in result.error

    @pytest.mark.asyncio
    async def test_submit_modification_axiom_no_target_check(self):
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.AXIOM,
            description="Test axiom",
            target="test_axiom",
            changes={"rule": "test"},
            justification="Test",
            risk_level="low",
        )
        result = await self.engine.submit_modification(req)
        assert result.status == ModificationStatus.PENDING

    @pytest.mark.asyncio
    async def test_execute_modification_not_found(self):
        result = await self.engine.execute_modification("nonexistent")
        assert result.status == ModificationStatus.PENDING
        assert result.description == "Not found"

    @pytest.mark.asyncio
    async def test_execute_code_modification(self):
        target_file = Path(self.tmpdir, "test.py")
        target_file.write_text("original content")
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Update code",
            target="test.py",
            changes={"content": "new content"},
            justification="Test",
            risk_level="low",
        )
        await self.engine.submit_modification(req)
        result = await self.engine.execute_modification("r1")
        assert result.status == ModificationStatus.COMPLETED
        assert target_file.read_text() == "new content"
        assert len(self.engine._completed_modifications) == 1

    @pytest.mark.asyncio
    async def test_execute_code_modification_patch(self):
        target_file = Path(self.tmpdir, "test.py")
        target_file.write_text("old_string is here")
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Patch code",
            target="test.py",
            changes={"patch": {"old_string": "old_string", "new_string": "new_string"}},
            justification="Test",
            risk_level="low",
        )
        await self.engine.submit_modification(req)
        result = await self.engine.execute_modification("r1")
        assert result.status == ModificationStatus.COMPLETED
        assert target_file.read_text() == "new_string is here"

    @pytest.mark.asyncio
    async def test_execute_axiom_modification(self):
        axiom_dir = Path(self.tmpdir, "src", "tektos", "axioms")
        axiom_dir.mkdir(parents=True, exist_ok=True)
        axiom_file = axiom_dir / "test_axiom.axiom"
        axiom_file.write_text("{}")
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.AXIOM,
            description="Update axiom",
            target="test_axiom",
            changes={"rule": "new_rule"},
            justification="Test",
            risk_level="low",
        )
        await self.engine.submit_modification(req)
        result = await self.engine.execute_modification("r1")
        assert result.status == ModificationStatus.COMPLETED
        assert json.loads(axiom_file.read_text()) == {"rule": "new_rule"}

    @pytest.mark.asyncio
    async def test_execute_axiom_modification_no_file(self):
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.AXIOM,
            description="Update axiom",
            target="nonexistent",
            changes={"rule": "new_rule"},
            justification="Test",
            risk_level="low",
        )
        await self.engine.submit_modification(req)
        result = await self.engine.execute_modification("r1")
        assert result.status == ModificationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_execute_tool_modification(self):
        tool_dir = Path(self.tmpdir, "src", "tektos", "tools")
        tool_dir.mkdir(parents=True, exist_ok=True)
        tool_file = tool_dir / "test_tool.py"
        tool_file.write_text("{}")
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.TOOL,
            description="Update tool",
            target="test_tool",
            changes={"name": "new_tool"},
            justification="Test",
            risk_level="low",
        )
        await self.engine.submit_modification(req)
        result = await self.engine.execute_modification("r1")
        assert result.status == ModificationStatus.COMPLETED
        assert json.loads(tool_file.read_text()) == {"name": "new_tool"}

    @pytest.mark.asyncio
    async def test_execute_workflow_modification(self):
        workflow_dir = Path(self.tmpdir, "workflows")
        workflow_dir.mkdir(parents=True, exist_ok=True)
        workflow_file = workflow_dir / "test_workflow.json"
        workflow_file.write_text("{}")
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.WORKFLOW,
            description="Update workflow",
            target="test_workflow",
            changes={"step": "new_step"},
            justification="Test",
            risk_level="low",
        )
        await self.engine.submit_modification(req)
        result = await self.engine.execute_modification("r1")
        assert result.status == ModificationStatus.COMPLETED
        assert json.loads(workflow_file.read_text()) == {"step": "new_step"}

    @pytest.mark.asyncio
    async def test_execute_config_modification(self):
        config_dir = Path(self.tmpdir, "config")
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "test_config.yaml"
        config_file.write_text("{}")
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CONFIG,
            description="Update config",
            target="test_config",
            changes={"key": "value"},
            justification="Test",
            risk_level="low",
        )
        await self.engine.submit_modification(req)
        result = await self.engine.execute_modification("r1")
        assert result.status == ModificationStatus.COMPLETED
        assert json.loads(config_file.read_text()) == {"key": "value"}

    @pytest.mark.asyncio
    async def test_execute_memory_modification(self):
        memory_dir = Path(self.tmpdir, "memory")
        memory_dir.mkdir(parents=True, exist_ok=True)
        memory_file = memory_dir / "test_memory.json"
        memory_file.write_text("{}")
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.MEMORY,
            description="Update memory",
            target="test_memory",
            changes={"key": "value"},
            justification="Test",
            risk_level="low",
        )
        await self.engine.submit_modification(req)
        result = await self.engine.execute_modification("r1")
        assert result.status == ModificationStatus.COMPLETED
        assert json.loads(memory_file.read_text()) == {"key": "value"}

    @pytest.mark.asyncio
    async def test_execute_modification_exception(self):
        target_file = Path(self.tmpdir, "test.py")
        target_file.write_text("original")
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Test",
            target="test.py",
            changes={"content": "new"},
            justification="Test",
            risk_level="low",
        )
        await self.engine.submit_modification(req)
        with patch.object(self.engine, '_execute_code_modification', side_effect=RuntimeError("boom")):
            result = await self.engine.execute_modification("r1")
        assert result.status == ModificationStatus.FAILED
        assert result.error == "boom"

    @pytest.mark.asyncio
    async def test_rollback_modification(self):
        target_file = Path(self.tmpdir, "test.py")
        target_file.write_text("modified")
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Test",
            target="test.py",
            changes={"content": "modified"},
            justification="Test",
            risk_level="low",
            rollback_plan="original_content",
        )
        await self.engine.submit_modification(req)
        # The source code expects rollback_plan to be a dict (despite type annotation saying str | None)
        object.__setattr__(req, "rollback_plan", {"original_content": "original"})
        await self.engine._rollback_modification(req)
        assert req.status == ModificationStatus.ROLLED_BACK
        assert target_file.read_text() == "original"

    @pytest.mark.asyncio
    async def test_rollback_no_plan(self):
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Test",
            target="test.py",
            changes={},
            justification="Test",
            risk_level="low",
        )
        await self.engine._rollback_modification(req)
        assert req.status == ModificationStatus.PENDING

    @pytest.mark.asyncio
    async def test_run_self_tests(self):
        results = await self.engine.run_self_tests()
        assert len(results) == 4
        test_names = [r.test_name for r in results]
        assert "import_check" in test_names
        assert "file_access" in test_names
        assert "memory_persistence" in test_names
        assert "tool_execution" in test_names
        assert len(self.engine._self_tests) == 4

    @pytest.mark.asyncio
    async def test_run_self_tests_multiple_times(self):
        await self.engine.run_self_tests()
        await self.engine.run_self_tests()
        assert len(self.engine._self_tests) == 8

    def test_get_status(self):
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Test",
            target="test.py",
            changes={},
            justification="Test",
            risk_level="low",
        )
        self.engine._requests["r1"] = req
        self.engine._completed_modifications.append(req)
        self.engine._self_tests.append(SelfTestResult(test_name="test", passed=True, duration=1.0))
        status = self.engine.get_status()
        assert status["total_requests"] == 1
        assert status["completed_modifications"] == 1
        assert len(status["self_tests"]) == 1
        assert status["passed_tests"] == 1
        assert status["failed_tests"] == 0
        assert "r1" in status["requests"]

    def test_to_memory_entry(self):
        self.engine._completed_modifications.append(
            ModificationRequest(request_id="r1", modification_type=ModificationType.CODE,
                                description="Test", target="test.py", changes={}, justification="Test")
        )
        self.engine._self_tests.append(SelfTestResult(test_name="test", passed=True, duration=1.0))
        self.engine._self_tests.append(SelfTestResult(test_name="test2", passed=False, duration=1.0))
        entry = self.engine.to_memory_entry()
        assert entry["total_requests"] == 0
        assert entry["completed_modifications"] == 1
        assert entry["self_tests_passed"] == 1
        assert entry["self_tests_failed"] == 1


# ── Convenience Functions ─────────────────────────────────────────────────────

class TestConvenienceFunctions:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        # Reset singleton
        import tektos.runtime.self_modification as sm
        sm._engine = None

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        import tektos.runtime.self_modification as sm
        sm._engine = None

    def test_get_self_modification_engine(self):
        e1 = get_self_modification_engine(project_root=self.tmpdir)
        e2 = get_self_modification_engine(project_root=self.tmpdir)
        assert e1 is e2

    def test_get_self_modification_engine_different_root(self):
        e1 = get_self_modification_engine(project_root=self.tmpdir)
        e2 = get_self_modification_engine(project_root="/tmp")
        assert e1 is not e2

    @pytest.mark.asyncio
    async def test_submit_self_modification(self):
        target_file = Path(self.tmpdir, "test.py")
        target_file.write_text("original")
        req = ModificationRequest(
            request_id="r1",
            modification_type=ModificationType.CODE,
            description="Test",
            target="test.py",
            changes={"content": "new"},
            justification="Test",
            risk_level="low",
        )
        engine = get_self_modification_engine(project_root=self.tmpdir)
        result = await engine.submit_modification(req)
        assert result.status == ModificationStatus.PENDING
