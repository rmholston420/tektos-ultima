"""Tests for src/tektos/runtime/multi_agent_orchestrator.py

Covers: AgentRole, TaskStatus, Subagent, Task, OrchestrationResult,
MultiAgentOrchestrator (task creation, assignment, execution, parallel execution,
stats, reconciliation).
"""

import pytest
from unittest.mock import MagicMock, patch

from tektos.runtime.multi_agent_orchestrator import (
    AgentRole,
    TaskStatus,
    Subagent,
    Task,
    OrchestrationResult,
    MultiAgentOrchestrator,
)


# ── Enums & Data Classes ──────────────────────────────────────────────────────

class TestAgentRole:
    def test_values(self):
        assert AgentRole.WORKER.value == "worker"
        assert AgentRole.COORDINATOR.value == "coordinator"
        assert AgentRole.REVIEWER.value == "reviewer"
        assert AgentRole.SPECIALIST.value == "specialist"


class TestTaskStatus:
    def test_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"


class TestSubagent:
    def test_creation(self):
        s = Subagent(agent_id="test", role=AgentRole.WORKER)
        assert s.agent_id == "test"
        assert s.role == AgentRole.WORKER
        assert s.capabilities == []
        assert s.status == TaskStatus.PENDING
        assert s.current_task == ""
        assert s.result is None
        assert s.error == ""
        assert s.created_at != ""
        assert s.completed_at == ""

    def test_custom_created_at(self):
        s = Subagent(agent_id="test", role=AgentRole.WORKER, created_at="2026-01-01")
        assert s.created_at == "2026-01-01"

    def test_with_capabilities(self):
        s = Subagent(agent_id="test", role=AgentRole.WORKER, capabilities=["read", "write"])
        assert s.capabilities == ["read", "write"]


class TestTask:
    def test_creation(self):
        t = Task(task_id="t1", description="Test task")
        assert t.task_id == "t1"
        assert t.description == "Test task"
        assert t.assigned_agent is None
        assert t.status == TaskStatus.PENDING
        assert t.priority == 0
        assert t.dependencies == []
        assert t.result is None
        assert t.error == ""
        assert t.created_at != ""
        assert t.completed_at == ""

    def test_custom_created_at(self):
        t = Task(task_id="t1", description="Test task", created_at="2026-01-01")
        assert t.created_at == "2026-01-01"

    def test_with_dependencies(self):
        t = Task(task_id="t1", description="Test task", dependencies=["t0"])
        assert t.dependencies == ["t0"]


class TestOrchestrationResult:
    def test_creation(self):
        r = OrchestrationResult(tasks_completed=1, tasks_failed=0, total_duration_seconds=1.0, agent_utilization=0.5)
        assert r.tasks_completed == 1
        assert r.tasks_failed == 0
        assert r.total_duration_seconds == 1.0
        assert r.agent_utilization == 0.5
        assert r.results == {}
        assert r.errors == []


# ── MultiAgentOrchestrator ────────────────────────────────────────────────────

class TestMultiAgentOrchestrator:
    def setup_method(self):
        self.orch = MultiAgentOrchestrator()

    def test_creation_defaults(self):
        assert self.orch.max_concurrent_agents == 5
        assert len(self.orch.agents) == 4
        assert "file_agent" in self.orch.agents
        assert "terminal_agent" in self.orch.agents
        assert "browser_agent" in self.orch.agents
        assert "reviewer_agent" in self.orch.agents
        assert self.orch.tasks == {}
        assert self.orch.task_queue == []

    def test_creation_custom_max(self):
        o = MultiAgentOrchestrator(max_concurrent_agents=10)
        assert o.max_concurrent_agents == 10

    def test_agent_capabilities(self):
        assert "read_file" in self.orch.agents["file_agent"].capabilities
        assert "terminal" in self.orch.agents["terminal_agent"].capabilities
        assert "browser_exec" in self.orch.agents["browser_agent"].capabilities
        assert "read_file" in self.orch.agents["reviewer_agent"].capabilities

    def test_create_task(self):
        task_id = self.orch.create_task("Read file /tmp/test.py")
        assert task_id == "task_1"
        assert task_id in self.orch.tasks
        assert task_id in self.orch.task_queue
        assert self.orch.tasks[task_id].description == "Read file /tmp/test.py"

    def test_create_task_with_priority(self):
        task_id = self.orch.create_task("Test task", priority=5)
        assert self.orch.tasks[task_id].priority == 5

    def test_create_task_with_dependencies(self):
        t1 = self.orch.create_task("Task 1")
        t2 = self.orch.create_task("Task 2", dependencies=[t1])
        assert self.orch.tasks[t2].dependencies == [t1]

    def test_create_multiple_tasks(self):
        t1 = self.orch.create_task("Task 1")
        t2 = self.orch.create_task("Task 2")
        assert t1 == "task_1"
        assert t2 == "task_2"

    def test_assign_task_to_existing_agent(self):
        task_id = self.orch.create_task("Read file /tmp/test.py")
        result = self.orch.assign_task(task_id, "file_agent")
        assert result is True
        assert self.orch.tasks[task_id].assigned_agent == "file_agent"
        assert self.orch.tasks[task_id].status == TaskStatus.RUNNING
        assert self.orch.agents["file_agent"].status == TaskStatus.RUNNING
        assert self.orch.agents["file_agent"].current_task == task_id

    def test_assign_task_to_nonexistent_task(self):
        result = self.orch.assign_task("nonexistent", "file_agent")
        assert result is False

    def test_assign_task_to_nonexistent_agent(self):
        task_id = self.orch.create_task("Test")
        result = self.orch.assign_task(task_id, "nonexistent")
        assert result is False

    def test_assign_task_no_capability_match(self):
        task_id = self.orch.create_task("Some random task with no matching keywords")
        result = self.orch.assign_task(task_id, "file_agent")
        assert result is False

    def test_assign_task_terminal_agent(self):
        task_id = self.orch.create_task("Run command ls -la")
        result = self.orch.assign_task(task_id, "terminal_agent")
        assert result is True

    def test_assign_task_reviewer_agent(self):
        task_id = self.orch.create_task("Review file /tmp/test.py")
        result = self.orch.assign_task(task_id, "reviewer_agent")
        assert result is True

    def test_execute_task_not_found(self):
        result = self.orch.execute_task("nonexistent")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_execute_task_not_assigned(self):
        task_id = self.orch.create_task("Test task")
        result = self.orch.execute_task(task_id)
        assert result["success"] is False
        assert "not assigned" in result["error"]

    def test_execute_task_success(self):
        task_id = self.orch.create_task("Read file /etc/hostname")
        self.orch.assign_task(task_id, "file_agent")
        result = self.orch.execute_task(task_id)
        assert result["success"] is True
        assert self.orch.tasks[task_id].status == TaskStatus.COMPLETED
        assert self.orch.agents["file_agent"].status == TaskStatus.PENDING

    def test_execute_task_failure(self):
        task_id = self.orch.create_task("Read file /nonexistent/path.txt")
        self.orch.assign_task(task_id, "file_agent")
        result = self.orch.execute_task(task_id)
        assert result["success"] is False
        assert self.orch.tasks[task_id].status == TaskStatus.FAILED
        assert self.orch.agents["file_agent"].status == TaskStatus.PENDING

    def test_execute_parallel(self):
        t1 = self.orch.create_task("Read file /etc/hostname")
        t2 = self.orch.create_task("Read file /etc/hostname")
        self.orch.assign_task(t1, "file_agent")
        self.orch.assign_task(t2, "file_agent")
        result = self.orch.execute_parallel([t1, t2])
        assert isinstance(result, OrchestrationResult)
        assert result.tasks_completed == 2
        assert result.tasks_failed == 0
        assert result.total_duration_seconds > 0

    def test_execute_parallel_with_failures(self):
        t1 = self.orch.create_task("Read file /nonexistent/path.txt")
        self.orch.assign_task(t1, "file_agent")
        result = self.orch.execute_parallel([t1])
        assert result.tasks_completed == 0
        assert result.tasks_failed == 1
        assert len(result.errors) == 1

    def test_execute_parallel_no_tasks(self):
        result = self.orch.execute_parallel([])
        assert result.tasks_completed == 0
        assert result.tasks_failed == 0

    def test_get_orchestration_stats(self):
        t1 = self.orch.create_task("Read file /etc/hostname")
        self.orch.assign_task(t1, "file_agent")
        self.orch.execute_task(t1)
        stats = self.orch.get_orchestration_stats()
        assert "agents" in stats
        assert "tasks" in stats
        assert stats["tasks"]["total_tasks"] == 1
        assert stats["tasks"]["completed"] == 1
        assert stats["max_concurrent_agents"] == 5

    def test_reconcile_results(self):
        results = {
            "t1": {"success": True, "result": {"content": "hello"}},
            "t2": {"success": False, "error": "not found"},
        }
        reconciled = self.orch.reconcile_results(results)
        assert reconciled["total_tasks"] == 2
        assert reconciled["successful"] == 1
        assert reconciled["failed"] == 1
        assert len(reconciled["summary"]) == 1
        assert len(reconciled["errors"]) == 1

    def test_reconcile_results_empty(self):
        reconciled = self.orch.reconcile_results({})
        assert reconciled["total_tasks"] == 0
        assert reconciled["successful"] == 0
        assert reconciled["failed"] == 0

    def test_dispatch_file_read(self):
        task_id = self.orch.create_task("Read file /etc/hostname")
        self.orch.assign_task(task_id, "file_agent")
        result = self.orch.execute_task(task_id)
        assert result["success"] is True
        assert result["result"]["type"] == "file_content"

    def test_dispatch_file_write(self):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        task_id = self.orch.create_task(f'Write file "{tmpdir}/test.txt" "Hello World"')
        self.orch.assign_task(task_id, "file_agent")
        result = self.orch.execute_task(task_id)
        assert result["success"] is True
        assert result["result"]["type"] == "file_created"
        assert result["result"]["path"] == f"{tmpdir}/test.txt"
        # Verify file was actually written
        with open(f"{tmpdir}/test.txt") as f:
            assert f.read() == "Hello World"

    def test_dispatch_terminal_run(self):
        task_id = self.orch.create_task('Run command "echo hello"')
        self.orch.assign_task(task_id, "terminal_agent")
        result = self.orch.execute_task(task_id)
        assert result["success"] is True
        assert result["result"]["type"] == "command_output"
        assert "hello" in result["result"]["stdout"]

    def test_dispatch_reviewer(self):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        test_file = f"{tmpdir}/test.py"
        with open(test_file, "w") as f:
            f.write("x = 1\n" * 100)  # Long lines
        task_id = self.orch.create_task(f'Review file "{test_file}"')
        self.orch.assign_task(task_id, "reviewer_agent")
        result = self.orch.execute_task(task_id)
        assert result["success"] is True
        assert result["result"]["type"] == "review_result"
        assert result["result"]["lines"] == 101  # 100 lines of "x = 1\n" plus empty trailing line
