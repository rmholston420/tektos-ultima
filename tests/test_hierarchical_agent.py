"""Tests for src/tektos/runtime/hierarchical_agent.py

Covers: AgentRole, AgentStatus, AgentTask, AgentResult, HierarchicalAgent,
get_hierarchical_agent, list_hierarchical_agents.
"""

import asyncio
import time

from tektos.runtime.hierarchical_agent import (
    AgentRole,
    AgentStatus,
    AgentTask,
    AgentResult,
    HierarchicalAgent,
    get_hierarchical_agent,
    list_hierarchical_agents,
)


# ─── AgentRole ──────────────────────────────────────────────────────────────────

class TestAgentRole:
    def test_all_roles(self):
        assert AgentRole.ARCHITECT.value == "architect"
        assert AgentRole.PLANNER.value == "planner"
        assert AgentRole.CODER.value == "coder"
        assert AgentRole.REVIEWER.value == "reviewer"
        assert AgentRole.TESTER.value == "tester"
        assert AgentRole.DEPLOYER.value == "deployer"


# ─── AgentStatus ────────────────────────────────────────────────────────────────

class TestAgentStatus:
    def test_all_statuses(self):
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.COMPLETED.value == "completed"
        assert AgentStatus.FAILED.value == "failed"
        assert AgentStatus.PENDING.value == "pending"


# ─── AgentTask ──────────────────────────────────────────────────────────────────

class TestAgentTask:
    def test_creation(self):
        task = AgentTask(
            task_id="t1",
            role=AgentRole.CODER,
            description="Write a function",
        )
        assert task.task_id == "t1"
        assert task.role == AgentRole.CODER
        assert task.description == "Write a function"
        assert task.context == {}
        assert task.dependencies == []
        assert task.status == AgentStatus.PENDING
        assert task.result is None
        assert task.error is None
        assert task.started_at == 0.0
        assert task.completed_at == 0.0

    def test_duration(self):
        task = AgentTask(
            task_id="t1",
            role=AgentRole.CODER,
            description="Test",
        )
        task.started_at = time.time() - 5
        task.completed_at = time.time()
        assert task.duration >= 4.9
        assert task.duration <= 5.1

    def test_duration_no_completed(self):
        task = AgentTask(
            task_id="t1",
            role=AgentRole.CODER,
            description="Test",
        )
        task.started_at = time.time() - 2
        dur = task.duration
        assert dur >= 1.9

    def test_to_dict(self):
        task = AgentTask(
            task_id="t1",
            role=AgentRole.PLANNER,
            description="Plan task",
            context={"key": "value"},
            dependencies=["t0"],
            status=AgentStatus.RUNNING,
            result="done",
            error=None,
            started_at=100.0,
            completed_at=105.0,
        )
        d = task.to_dict()
        assert d["task_id"] == "t1"
        assert d["role"] == "planner"
        assert d["description"] == "Plan task"
        assert d["context"] == {"key": "value"}
        assert d["dependencies"] == ["t0"]
        assert d["status"] == "running"
        assert d["result"] == "done"
        assert d["error"] is None
        assert d["started_at"] == 100.0
        assert d["completed_at"] == 105.0
        assert d["duration"] == 5.0


# ─── AgentResult ────────────────────────────────────────────────────────────────

class TestAgentResult:
    def test_creation_success(self):
        result = AgentResult(
            task_id="t1",
            role=AgentRole.CODER,
            success=True,
            output="Code written",
        )
        assert result.task_id == "t1"
        assert result.role == AgentRole.CODER
        assert result.success is True
        assert result.output == "Code written"
        assert result.metadata == {}
        assert result.error is None

    def test_creation_failure(self):
        result = AgentResult(
            task_id="t1",
            role=AgentRole.TESTER,
            success=False,
            output="",
            error="Test failed",
        )
        assert result.success is False
        assert result.error == "Test failed"

    def test_to_markdown_success(self):
        result = AgentResult(
            task_id="t1",
            role=AgentRole.CODER,
            success=True,
            output="def hello(): pass",
        )
        md = result.to_markdown()
        assert "✓" in md
        assert "Coder Agent" in md
        assert "t1" in md
        assert "def hello(): pass" in md

    def test_to_markdown_failure(self):
        result = AgentResult(
            task_id="t1",
            role=AgentRole.TESTER,
            success=False,
            output="",
            error="AssertionError",
        )
        md = result.to_markdown()
        assert "✗" in md
        assert "Tester Agent" in md
        assert "AssertionError" in md


# ─── HierarchicalAgent ──────────────────────────────────────────────────────────

class TestHierarchicalAgent:
    def setup_method(self):
        self.agent = HierarchicalAgent(max_concurrent_agents=2)

    def test_add_task(self):
        task = AgentTask(task_id="t1", role=AgentRole.CODER, description="Write code")
        self.agent.add_task(task)
        assert "t1" in self.agent._tasks

    def test_execute_task_not_found(self):
        result = asyncio.run(self.agent.execute_task("nonexistent"))
        assert result.success is False
        assert result.error and "not found" in result.error

    def test_execute_task_architect(self):
        task = AgentTask(task_id="t1", role=AgentRole.ARCHITECT, description="Design system")
        self.agent.add_task(task)
        result = asyncio.run(self.agent.execute_task("t1"))
        assert result.success is True
        assert "Architecture design" in result.output

    def test_execute_task_planner(self):
        task = AgentTask(task_id="t1", role=AgentRole.PLANNER, description="Plan steps")
        self.agent.add_task(task)
        result = asyncio.run(self.agent.execute_task("t1"))
        assert result.success is True
        assert "Plan for" in result.output

    def test_execute_task_coder(self):
        task = AgentTask(task_id="t1", role=AgentRole.CODER, description="Write function")
        self.agent.add_task(task)
        result = asyncio.run(self.agent.execute_task("t1"))
        assert result.success is True
        assert "Code for" in result.output

    def test_execute_task_reviewer(self):
        task = AgentTask(task_id="t1", role=AgentRole.REVIEWER, description="Review code")
        self.agent.add_task(task)
        result = asyncio.run(self.agent.execute_task("t1"))
        assert result.success is True
        assert "Review for" in result.output

    def test_execute_task_tester(self):
        task = AgentTask(task_id="t1", role=AgentRole.TESTER, description="Write tests")
        self.agent.add_task(task)
        result = asyncio.run(self.agent.execute_task("t1"))
        assert result.success is True
        assert "Tests for" in result.output

    def test_execute_task_deployer(self):
        task = AgentTask(task_id="t1", role=AgentRole.DEPLOYER, description="Deploy app")
        self.agent.add_task(task)
        result = asyncio.run(self.agent.execute_task("t1"))
        assert result.success is True
        assert "Deployment for" in result.output

    def test_execute_task_with_failed_dependency(self):
        task = AgentTask(
            task_id="t2",
            role=AgentRole.CODER,
            description="Write code",
            dependencies=["t1"],
        )
        self.agent.add_task(task)
        result = asyncio.run(self.agent.execute_task("t2"))
        assert result.success is False
        assert result.error and "Dependency t1 not completed" in result.error

    def test_execute_task_with_exception(self):
        task = AgentTask(task_id="t1", role=AgentRole.CODER, description="Fail")
        self.agent.add_task(task)
        # Override to raise exception
        async def failing_task(task: AgentTask) -> str:
            raise ValueError("Something went wrong")
        self.agent._execute_coder = failing_task
        result = asyncio.run(self.agent.execute_task("t1"))
        assert result.success is False
        assert result.error and "Something went wrong" in result.error

    def test_execute_batch(self):
        self.agent.add_task(AgentTask(task_id="t1", role=AgentRole.CODER, description="Code 1"))
        self.agent.add_task(AgentTask(task_id="t2", role=AgentRole.PLANNER, description="Plan 2"))
        results = asyncio.run(self.agent.execute_batch(["t1", "t2"]))
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_execute_batch_empty(self):
        results = asyncio.run(self.agent.execute_batch([]))
        assert results == []

    def test_execute_batch_limited_concurrency(self):
        # Add more tasks than max_concurrent_agents
        for i in range(5):
            self.agent.add_task(AgentTask(task_id=f"t{i}", role=AgentRole.CODER, description=f"Code {i}"))
        results = asyncio.run(self.agent.execute_batch(["t0", "t1", "t2", "t3", "t4"]))
        # Should only execute up to max_concurrent_agents (2)
        assert len(results) == 2

    def test_get_status(self):
        self.agent.add_task(AgentTask(task_id="t1", role=AgentRole.CODER, description="Code"))
        asyncio.run(self.agent.execute_task("t1"))
        status = self.agent.get_status()
        assert status["total_tasks"] == 1
        assert status["completed_tasks"] == 1
        assert status["failed_tasks"] == 0
        assert "t1" in status["tasks"]

    def test_to_memory_entry(self):
        self.agent.add_task(AgentTask(task_id="t1", role=AgentRole.CODER, description="Code"))
        asyncio.run(self.agent.execute_task("t1"))
        entry = self.agent.to_memory_entry()
        assert entry["total_tasks"] == 1
        assert entry["completed_tasks"] == 1
        assert entry["failed_tasks"] == 0
        assert entry["max_concurrent_agents"] == 2


# ─── Convenience Functions ──────────────────────────────────────────────────────

class TestConvenienceFunctions:
    def test_get_hierarchical_agent_creates_new(self):
        agent = get_hierarchical_agent("test-session-123")
        assert isinstance(agent, HierarchicalAgent)

    def test_get_hierarchical_agent_returns_same(self):
        agent1 = get_hierarchical_agent("test-session-456")
        agent2 = get_hierarchical_agent("test-session-456")
        assert agent1 is agent2

    def test_get_hierarchical_agent_different_sessions(self):
        agent1 = get_hierarchical_agent("test-session-a")
        agent2 = get_hierarchical_agent("test-session-b")
        assert agent1 is not agent2

    def test_list_hierarchical_agents(self):
        # Clean slate
        from tektos.runtime.hierarchical_agent import _agents
        _agents.clear()
        get_hierarchical_agent("list-test-1")
        get_hierarchical_agent("list-test-2")
        sessions = list_hierarchical_agents()
        assert "list-test-1" in sessions
        assert "list-test-2" in sessions
