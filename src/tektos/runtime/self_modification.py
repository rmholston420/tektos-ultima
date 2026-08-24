"""Self-Modification — Comprehensive Self-Improvement System.

Implements comprehensive self-modification capabilities for Tektos,
enabling the agent to:
- Modify its own code (with safety constraints)
- Update its own axioms and rules
- Improve its own tools and workflows
- Learn from experience and adapt behavior
- Self-test and validate changes

This follows the SOTA pattern of self-improving agents that can
evolve their capabilities over time while maintaining safety.

SOTA Reference: Self-modifying agents research, OpenHands self-modification,
Claude Code self-improvement patterns.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class ModificationType(Enum):
    """Types of self-modifications."""
    CODE = "code"
    AXIOM = "axiom"
    TOOL = "tool"
    WORKFLOW = "workflow"
    CONFIG = "config"
    MEMORY = "memory"


class ModificationStatus(Enum):
    """Modification execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


@dataclass
class ModificationRequest:
    """A request to modify Tektos."""
    request_id: str
    modification_type: ModificationType
    description: str
    target: str  # File path, axiom ID, tool name, etc.
    changes: dict[str, Any]
    justification: str
    risk_level: str = "low"  # low, medium, high
    status: ModificationStatus = ModificationStatus.PENDING
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    error: str | None = None
    rollback_plan: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "modification_type": self.modification_type.value,
            "description": self.description,
            "target": self.target,
            "changes": self.changes,
            "justification": self.justification,
            "risk_level": self.risk_level,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "rollback_plan": self.rollback_plan,
        }


@dataclass
class SelfTestResult:
    """Result from a self-test."""
    test_name: str
    passed: bool
    duration: float
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    
    def to_markdown(self) -> str:
        """Convert to markdown for display."""
        status = "✓" if self.passed else "✗"
        return (
            f"## {status} {self.test_name}\n\n"
            f"**Duration**: {self.duration:.2f}s\n\n"
            f"{'**Error**: ' + self.error if self.error else ''}"
        )


class SelfModificationEngine:
    """Engine for safe self-modification.
    
    Manages self-modification requests, validates changes,
    and executes modifications with rollback capability.
    """
    
    def __init__(self, project_root: str = ".", max_risk_level: str = "medium"):
        """Initialize self-modification engine.
        
        Args:
            project_root: Path to the project root.
            max_risk_level: Maximum risk level allowed (low, medium, high).
        """
        self.project_root = Path(project_root)
        self.max_risk_level = max_risk_level
        self._requests: dict[str, ModificationRequest] = {}
        self._completed_modifications: list[ModificationRequest] = []
        self._self_tests: list[SelfTestResult] = []
        self._modification_log: list[dict[str, Any]] = []
    
    async def submit_modification(self, request: ModificationRequest) -> ModificationRequest:
        """Submit a modification request.
        
        Args:
            request: The modification request to submit.
        
        Returns:
            The submitted request with updated status.
        """
        # Validate risk level
        risk_order = {"low": 0, "medium": 1, "high": 2}
        if risk_order.get(request.risk_level, 0) > risk_order.get(self.max_risk_level, 1):
            request.status = ModificationStatus.REJECTED
            request.error = f"Risk level {request.risk_level} exceeds maximum {self.max_risk_level}"
            log.warning(f"[SelfModification] Rejected request {request.request_id}: "
                       f"risk level {request.risk_level}")
            return request
        
        # Validate target exists
        if request.modification_type == ModificationType.CODE:
            target_path = self.project_root / request.target
            if not target_path.exists():
                request.status = ModificationStatus.REJECTED
                request.error = f"Target file not found: {request.target}"
                log.warning(f"[SelfModification] Rejected request {request.request_id}: "
                           f"target not found")
                return request
        
        # Store request
        self._requests[request.request_id] = request
        log.info(f"[SelfModification] Submitted request {request.request_id}: "
                f"{request.description}")
        
        return request
    
    async def execute_modification(self, request_id: str) -> ModificationRequest:
        """Execute a modification request.
        
        Args:
            request_id: The request to execute.
        
        Returns:
            The executed request with updated status.
        """
        request = self._requests.get(request_id)
        if not request:
            log.error(f"[SelfModification] Request {request_id} not found")
            return ModificationRequest(
                request_id=request_id,
                modification_type=ModificationType.CODE,
                description="Not found",
                target="",
                changes={},
                justification="",
            )
        
        request.status = ModificationStatus.IN_PROGRESS
        log.info(f"[SelfModification] Executing request {request_id}: "
                f"{request.description}")
        
        try:
            # Execute based on modification type
            if request.modification_type == ModificationType.CODE:
                await self._execute_code_modification(request)
            elif request.modification_type == ModificationType.AXIOM:
                await self._execute_axiom_modification(request)
            elif request.modification_type == ModificationType.TOOL:
                await self._execute_tool_modification(request)
            elif request.modification_type == ModificationType.WORKFLOW:
                await self._execute_workflow_modification(request)
            elif request.modification_type == ModificationType.CONFIG:
                await self._execute_config_modification(request)
            elif request.modification_type == ModificationType.MEMORY:
                await self._execute_memory_modification(request)
            
            request.status = ModificationStatus.COMPLETED
            request.completed_at = time.time()
            self._completed_modifications.append(request)
            
            log.info(f"[SelfModification] Completed request {request_id}")
            
        except Exception as exc:
            request.status = ModificationStatus.FAILED
            request.error = str(exc)
            request.completed_at = time.time()
            
            # Attempt rollback if rollback plan exists
            if request.rollback_plan:
                await self._rollback_modification(request)
            
            log.error(f"[SelfModification] Failed request {request_id}: {exc}")
        
        return request
    
    async def _execute_code_modification(self, request: ModificationRequest) -> None:
        """Execute code modification."""
        target_path = self.project_root / request.target
        
        # Apply changes
        if "content" in request.changes:
            target_path.write_text(request.changes["content"])
            log.info(f"[SelfModification] Updated code: {request.target}")
        elif "patch" in request.changes:
            # Apply patch
            patch_content = request.changes["patch"]
            current_content = target_path.read_text()
            # Simple patch application (in production, use a proper patch library)
            old_string = patch_content.get("old_string", "")
            new_string = patch_content.get("new_string", "")
            if old_string in current_content:
                target_path.write_text(
                    current_content.replace(old_string, new_string)
                )
                log.info(f"[SelfModification] Applied patch: {request.target}")
    
    async def _execute_axiom_modification(self, request: ModificationRequest) -> None:
        """Execute axiom modification."""
        # Update axiom file
        axiom_path = self.project_root / "src" / "tektos" / "axioms" / f"{request.target}.axiom"
        if axiom_path.exists():
            axiom_path.write_text(json.dumps(request.changes, indent=2))
            log.info(f"[SelfModification] Updated axiom: {request.target}")
    
    async def _execute_tool_modification(self, request: ModificationRequest) -> None:
        """Execute tool modification."""
        # Update tool definition
        tool_path = self.project_root / "src" / "tektos" / "tools" / f"{request.target}.py"
        if tool_path.exists():
            tool_path.write_text(json.dumps(request.changes, indent=2))
            log.info(f"[SelfModification] Updated tool: {request.target}")
    
    async def _execute_workflow_modification(self, request: ModificationRequest) -> None:
        """Execute workflow modification."""
        # Update workflow configuration
        workflow_path = self.project_root / "workflows" / f"{request.target}.json"
        if workflow_path.exists():
            workflow_path.write_text(json.dumps(request.changes, indent=2))
            log.info(f"[SelfModification] Updated workflow: {request.target}")
    
    async def _execute_config_modification(self, request: ModificationRequest) -> None:
        """Execute config modification."""
        # Update configuration
        config_path = self.project_root / "config" / f"{request.target}.yaml"
        if config_path.exists():
            config_path.write_text(json.dumps(request.changes, indent=2))
            log.info(f"[SelfModification] Updated config: {request.target}")
    
    async def _execute_memory_modification(self, request: ModificationRequest) -> None:
        """Execute memory modification."""
        # Update memory file
        memory_path = self.project_root / "memory" / f"{request.target}.json"
        if memory_path.exists():
            memory_path.write_text(json.dumps(request.changes, indent=2))
            log.info(f"[SelfModification] Updated memory: {request.target}")
    
    async def _rollback_modification(self, request: ModificationRequest) -> None:
        """Rollback a modification."""
        if not request.rollback_plan:
            log.warning(f"[SelfModification] No rollback plan for {request.request_id}")
            return
        
        try:
            # Execute rollback
            if request.modification_type == ModificationType.CODE:
                target_path = self.project_root / request.target
                if "original_content" in request.rollback_plan:
                    target_path.write_text(request.rollback_plan["original_content"])
                    log.info(f"[SelfModification] Rolled back code: {request.target}")
            
            request.status = ModificationStatus.ROLLED_BACK
            log.info(f"[SelfModification] Rolled back request {request.request_id}")
            
        except Exception as exc:
            log.error(f"[SelfModification] Rollback failed for {request.request_id}: {exc}")
    
    async def run_self_tests(self) -> list[SelfTestResult]:
        """Run self-tests to validate system health.
        
        Returns:
            List of self-test results.
        """
        tests = [
            ("import_check", self._test_imports),
            ("file_access", self._test_file_access),
            ("memory_persistence", self._test_memory_persistence),
            ("tool_execution", self._test_tool_execution),
        ]
        
        results = []
        for test_name, test_fn in tests:
            start_time = time.time()
            try:
                passed, error, details = await test_fn()
                results.append(SelfTestResult(
                    test_name=test_name,
                    passed=passed,
                    duration=time.time() - start_time,
                    error=error,
                    details=details,
                ))
            except Exception as exc:
                results.append(SelfTestResult(
                    test_name=test_name,
                    passed=False,
                    duration=time.time() - start_time,
                    error=str(exc),
                ))
        
        self._self_tests.extend(results)
        return results
    
    async def _test_imports(self) -> tuple[bool, str | None, dict[str, Any]]:
        """Test that all imports work."""
        try:
            import tektos
            import tektos.runtime
            import tektos.memory
            import tektos.agents
            return True, None, {"modules": ["tektos", "tektos.runtime", "tektos.memory", "tektos.agents"]}
        except Exception as exc:
            return False, str(exc), {}
    
    async def _test_file_access(self) -> tuple[bool, str | None, dict[str, Any]]:
        """Test file access."""
        try:
            test_file = self.project_root / "test_access.txt"
            test_file.write_text("test")
            content = test_file.read_text()
            test_file.unlink()
            return True, None, {"file_access": "ok"}
        except Exception as exc:
            return False, str(exc), {}
    
    async def _test_memory_persistence(self) -> tuple[bool, str | None, dict[str, Any]]:
        """Test memory persistence."""
        try:
            memory_dir = self.project_root / "memory"
            memory_dir.mkdir(exist_ok=True)
            test_file = memory_dir / "test_persistence.json"
            test_file.write_text(json.dumps({"test": "data"}))
            content = json.loads(test_file.read_text())
            test_file.unlink()
            return True, None, {"memory_persistence": "ok"}
        except Exception as exc:
            return False, str(exc), {}
    
    async def _test_tool_execution(self) -> tuple[bool, str | None, dict[str, Any]]:
        """Test tool execution."""
        try:
            # Simple tool execution test
            import subprocess
            result = subprocess.run(
                ["echo", "test"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0, None, {"tool_execution": "ok"}
        except Exception as exc:
            return False, str(exc), {}
    
    def get_status(self) -> dict[str, Any]:
        """Get current status of self-modification engine.
        
        Returns:
            Status dictionary.
        """
        return {
            "total_requests": len(self._requests),
            "completed_modifications": len(self._completed_modifications),
            "self_tests": len(self._self_tests),
            "passed_tests": sum(1 for t in self._self_tests if t.passed),
            "failed_tests": sum(1 for t in self._self_tests if not t.passed),
            "requests": {rid: r.to_dict() for rid, r in self._requests.items()},
            "self_tests": [t.to_markdown() for t in self._self_tests],
        }
    
    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "total_requests": len(self._requests),
            "completed_modifications": len(self._completed_modifications),
            "self_tests_passed": sum(1 for t in self._self_tests if t.passed),
            "self_tests_failed": sum(1 for t in self._self_tests if not t.passed),
        }


# ── Convenience Functions ───────────────────────────────────────────────────

_engine: SelfModificationEngine | None = None


def get_self_modification_engine(project_root: str = ".",
                                 max_risk_level: str = "medium") -> SelfModificationEngine:
    """Get or create the self-modification engine.
    
    Args:
        project_root: Path to the project root.
        max_risk_level: Maximum risk level allowed.
    
    Returns:
        SelfModificationEngine instance.
    """
    global _engine
    if _engine is None or _engine.project_root != Path(project_root):
        _engine = SelfModificationEngine(
            project_root=project_root,
            max_risk_level=max_risk_level,
        )
    return _engine


def submit_self_modification(request: ModificationRequest) -> ModificationRequest:
    """Submit a self-modification request.
    
    Args:
        request: The modification request to submit.
    
    Returns:
        The submitted request.
    """
    engine = get_self_modification_engine()
    return asyncio.run(engine.submit_modification(request))
