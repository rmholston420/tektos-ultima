"""Tests for src/tektos/runtime/long_running_agent.py

Covers: AgentState, AgentCheckpoint, AgentProgress, CheckpointManager,
LongRunningAgent, get_long_running_agent, list_long_running_agents.
"""

import asyncio
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tektos.runtime.long_running_agent import (
    AgentState,
    AgentCheckpoint,
    AgentProgress,
    CheckpointManager,
    LongRunningAgent,
    get_long_running_agent,
    list_long_running_agents,
)


# ─── AgentState ───────────────────────────────────────────────────────────────

class TestAgentState:
    def test_values(self):
        assert AgentState.IDLE.value == "idle"
        assert AgentState.RUNNING.value == "running"
        assert AgentState.PAUSED.value == "paused"
        assert AgentState.COMPLETED.value == "completed"
        assert AgentState.FAILED.value == "failed"
        assert AgentState.CHECKPOINTED.value == "checkpointed"


# ─── AgentCheckpoint ──────────────────────────────────────────────────────────

class TestAgentCheckpoint:
    def test_creation(self):
        ckpt = AgentCheckpoint(
            checkpoint_id="ckpt_1",
            session_id="session_1",
            state=AgentState.RUNNING,
            timestamp=1234567890.0,
            context={"key": "value"},
            memory={"mem": "data"},
            tool_results=[{"tool": "read", "result": "ok"}],
        )
        assert ckpt.checkpoint_id == "ckpt_1"
        assert ckpt.session_id == "session_1"
        assert ckpt.state == AgentState.RUNNING
        assert ckpt.timestamp == 1234567890.0
        assert ckpt.context == {"key": "value"}
        assert ckpt.memory == {"mem": "data"}
        assert len(ckpt.tool_results) == 1
        assert ckpt.next_action is None
        assert ckpt.error is None

    def test_to_dict(self):
        ckpt = AgentCheckpoint(
            checkpoint_id="ckpt_1",
            session_id="session_1",
            state=AgentState.PAUSED,
            timestamp=1234567890.0,
            context={"k": "v"},
            memory={},
            tool_results=[],
            next_action="read_file",
            error=None,
        )
        d = ckpt.to_dict()
        assert d["checkpoint_id"] == "ckpt_1"
        assert d["session_id"] == "session_1"
        assert d["state"] == "paused"
        assert d["timestamp"] == 1234567890.0
        assert d["context"] == {"k": "v"}
        assert d["memory"] == {}
        assert d["tool_results"] == []
        assert d["next_action"] == "read_file"
        assert d["error"] is None

    def test_from_dict(self):
        data = {
            "checkpoint_id": "ckpt_1",
            "session_id": "session_1",
            "state": "completed",
            "timestamp": 1234567890.0,
            "context": {"k": "v"},
            "memory": {"m": "d"},
            "tool_results": [{"t": "r"}],
            "next_action": "write",
            "error": None,
        }
        ckpt = AgentCheckpoint.from_dict(data)
        assert ckpt.checkpoint_id == "ckpt_1"
        assert ckpt.session_id == "session_1"
        assert ckpt.state == AgentState.COMPLETED
        assert ckpt.timestamp == 1234567890.0
        assert ckpt.context == {"k": "v"}
        assert ckpt.memory == {"m": "d"}
        assert ckpt.tool_results == [{"t": "r"}]
        assert ckpt.next_action == "write"
        assert ckpt.error is None

    def test_from_dict_defaults(self):
        data = {
            "checkpoint_id": "ckpt_1",
            "session_id": "session_1",
            "state": "idle",
            "timestamp": 1234567890.0,
        }
        ckpt = AgentCheckpoint.from_dict(data)
        assert ckpt.context == {}
        assert ckpt.memory == {}
        assert ckpt.tool_results == []
        assert ckpt.next_action is None
        assert ckpt.error is None


# ─── AgentProgress ────────────────────────────────────────────────────────────

class TestAgentProgress:
    def test_creation(self):
        p = AgentProgress(
            session_id="session_1",
            started_at=1000.0,
            last_checkpoint_at=1000.0,
        )
        assert p.session_id == "session_1"
        assert p.started_at == 1000.0
        assert p.last_checkpoint_at == 1000.0
        assert p.total_steps == 0
        assert p.completed_steps == 0
        assert p.current_step == ""
        assert p.status == "running"
        assert p.error is None

    def test_progress_percent_zero_total(self):
        p = AgentProgress(session_id="s1", started_at=1000.0, last_checkpoint_at=1000.0)
        assert p.progress_percent == 0.0

    def test_progress_percent_partial(self):
        p = AgentProgress(session_id="s1", started_at=1000.0, last_checkpoint_at=1000.0)
        p.total_steps = 10
        p.completed_steps = 5
        assert p.progress_percent == 50.0

    def test_progress_percent_complete(self):
        p = AgentProgress(session_id="s1", started_at=1000.0, last_checkpoint_at=1000.0)
        p.total_steps = 10
        p.completed_steps = 10
        assert p.progress_percent == 100.0

    def test_elapsed_seconds(self):
        p = AgentProgress(session_id="s1", started_at=1000.0, last_checkpoint_at=1000.0)
        elapsed = p.elapsed_seconds
        assert elapsed >= 0

    def test_elapsed_minutes(self):
        p = AgentProgress(session_id="s1", started_at=1000.0, last_checkpoint_at=1000.0)
        elapsed_min = p.elapsed_minutes
        assert elapsed_min >= 0

    def test_to_markdown(self):
        p = AgentProgress(
            session_id="session_1",
            started_at=time.time() - 120,
            last_checkpoint_at=time.time() - 60,
            total_steps=10,
            completed_steps=5,
            current_step="reading file",
            status="running",
        )
        md = p.to_markdown()
        assert "**Session**: session_1" in md
        assert "**Status**: running" in md
        assert "**Progress**:" in md
        assert "5/10" in md
        assert "**Current Step**: reading file" in md
        assert "**Elapsed**:" in md

    def test_to_markdown_with_error(self):
        p = AgentProgress(
            session_id="session_1",
            started_at=time.time(),
            last_checkpoint_at=time.time(),
            error="Something went wrong",
            status="failed",
        )
        md = p.to_markdown()
        assert "**Error**: Something went wrong" in md


# ─── CheckpointManager ────────────────────────────────────────────────────────

class TestCheckpointManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = CheckpointManager(checkpoint_dir=self.tmpdir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creation(self):
        assert self.manager.checkpoint_dir == Path(self.tmpdir)
        assert self.manager._checkpoints == {}

    def test_checkpoint_dir_created(self):
        assert Path(self.tmpdir).exists()

    @pytest.mark.asyncio
    async def test_save_and_load_checkpoint(self):
        ckpt = AgentCheckpoint(
            checkpoint_id="ckpt_1",
            session_id="session_1",
            state=AgentState.RUNNING,
            timestamp=time.time(),
            context={"key": "value"},
            memory={},
            tool_results=[],
        )
        filepath = await self.manager.save_checkpoint(ckpt)
        assert filepath.endswith("ckpt_1.json")
        assert Path(filepath).exists()

        loaded = await self.manager.load_checkpoint("session_1", "ckpt_1")
        assert loaded is not None
        assert loaded.checkpoint_id == "ckpt_1"
        assert loaded.context == {"key": "value"}

    @pytest.mark.asyncio
    async def test_load_latest_checkpoint(self):
        ckpt1 = AgentCheckpoint(
            checkpoint_id="ckpt_1",
            session_id="session_1",
            state=AgentState.RUNNING,
            timestamp=time.time() - 10,
            context={},
            memory={},
            tool_results=[],
        )
        ckpt2 = AgentCheckpoint(
            checkpoint_id="ckpt_2",
            session_id="session_1",
            state=AgentState.PAUSED,
            timestamp=time.time(),
            context={"latest": True},
            memory={},
            tool_results=[],
        )
        await self.manager.save_checkpoint(ckpt1)
        await self.manager.save_checkpoint(ckpt2)

        loaded = await self.manager.load_checkpoint("session_1")
        assert loaded is not None
        assert loaded.checkpoint_id == "ckpt_2"

    @pytest.mark.asyncio
    async def test_load_nonexistent_session(self):
        loaded = await self.manager.load_checkpoint("nonexistent")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_nonexistent_checkpoint(self):
        loaded = await self.manager.load_checkpoint("session_1", "nonexistent")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_list_checkpoints(self):
        ckpt1 = AgentCheckpoint(
            checkpoint_id="ckpt_1",
            session_id="session_1",
            state=AgentState.RUNNING,
            timestamp=time.time() - 10,
            context={},
            memory={},
            tool_results=[],
        )
        ckpt2 = AgentCheckpoint(
            checkpoint_id="ckpt_2",
            session_id="session_1",
            state=AgentState.PAUSED,
            timestamp=time.time(),
            context={},
            memory={},
            tool_results=[],
        )
        await self.manager.save_checkpoint(ckpt1)
        await self.manager.save_checkpoint(ckpt2)

        checkpoints = await self.manager.list_checkpoints("session_1")
        assert len(checkpoints) == 2
        assert checkpoints[0].checkpoint_id == "ckpt_2"

    @pytest.mark.asyncio
    async def test_list_checkpoints_empty(self):
        checkpoints = await self.manager.list_checkpoints("nonexistent")
        assert checkpoints == []

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints(self):
        for i in range(7):
            ckpt = AgentCheckpoint(
                checkpoint_id=f"ckpt_{i}",
                session_id="session_1",
                state=AgentState.RUNNING,
                timestamp=time.time() - (7 - i),
                context={},
                memory={},
                tool_results=[],
            )
            await self.manager.save_checkpoint(ckpt)

        removed = await self.manager.cleanup_old_checkpoints("session_1", keep_last=5)
        assert removed == 2

    @pytest.mark.asyncio
    async def test_cleanup_nothing_to_remove(self):
        ckpt = AgentCheckpoint(
            checkpoint_id="ckpt_1",
            session_id="session_1",
            state=AgentState.RUNNING,
            timestamp=time.time(),
            context={},
            memory={},
            tool_results=[],
        )
        await self.manager.save_checkpoint(ckpt)
        removed = await self.manager.cleanup_old_checkpoints("session_1", keep_last=5)
        assert removed == 0

    @pytest.mark.asyncio
    async def test_delete_session_checkpoints(self):
        for i in range(3):
            ckpt = AgentCheckpoint(
                checkpoint_id=f"ckpt_{i}",
                session_id="session_1",
                state=AgentState.RUNNING,
                timestamp=time.time(),
                context={},
                memory={},
                tool_results=[],
            )
            await self.manager.save_checkpoint(ckpt)

        removed = await self.manager.delete_session_checkpoints("session_1")
        assert removed == 3

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self):
        removed = await self.manager.delete_session_checkpoints("nonexistent")
        assert removed == 0


# ─── LongRunningAgent ─────────────────────────────────────────────────────────

class TestLongRunningAgent:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.agent = LongRunningAgent(
            session_id="session_1",
            checkpoint_dir=self.tmpdir,
        )

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creation(self):
        assert self.agent.session_id == "session_1"
        assert self.agent.state == AgentState.IDLE
        assert self.agent._context == {}
        assert self.agent._memory == {}
        assert self.agent._tool_results == []
        assert self.agent._checkpoint_interval == 300.0
        assert self.agent._running is False

    @pytest.mark.asyncio
    async def test_start(self):
        await self.agent.start()
        assert self.agent.state == AgentState.RUNNING
        assert self.agent._running is True
        assert self.agent.progress.status == "running"

    @pytest.mark.asyncio
    async def test_stop_completed(self):
        await self.agent.start()
        await self.agent.stop(reason="completed")
        assert self.agent.state == AgentState.COMPLETED
        assert self.agent.progress.status == "completed"

    @pytest.mark.asyncio
    async def test_stop_failed(self):
        await self.agent.start()
        await self.agent.stop(reason="error")
        assert self.agent.state == AgentState.FAILED
        assert self.agent.progress.status == "error"

    @pytest.mark.asyncio
    async def test_pause(self):
        await self.agent.start()
        await self.agent.pause()
        assert self.agent.state == AgentState.PAUSED
        assert self.agent.progress.status == "paused"

    @pytest.mark.asyncio
    async def test_resume_no_checkpoint(self):
        result = await self.agent.resume()
        assert result is False

    @pytest.mark.asyncio
    async def test_resume_with_checkpoint(self):
        await self.agent.start()
        self.agent._context = {"key": "value"}
        self.agent._memory = {"mem": "data"}
        self.agent._tool_results = [{"tool": "read"}]
        await self.agent.pause()

        # Create a new agent and resume
        new_agent = LongRunningAgent(
            session_id="session_1",
            checkpoint_dir=self.tmpdir,
        )
        result = await new_agent.resume()
        assert result is True
        assert new_agent._context == {"key": "value"}
        assert new_agent._memory == {"mem": "data"}
        assert len(new_agent._tool_results) == 1

    @pytest.mark.asyncio
    async def test_checkpoint_if_needed(self):
        self.agent._checkpoint_interval = 0.1  # Very short interval
        self.agent._last_checkpoint_time = time.time() - 10  # Force interval to have elapsed
        await self.agent.start()
        await self.agent.checkpoint_if_needed()
        # Verify checkpoint was saved to disk
        session_dir = Path(self.tmpdir) / "session_1"
        assert session_dir.exists()
        json_files = list(session_dir.glob("*.json"))
        assert len(json_files) >= 1

    @pytest.mark.asyncio
    async def test_checkpoint_if_needed_not_elapsed(self):
        self.agent._checkpoint_interval = 999999  # Very long interval
        await self.agent.start()
        await self.agent.checkpoint_if_needed()
        # Should not have created a checkpoint
        checkpoints = await self.agent.checkpoint_manager.list_checkpoints("session_1")
        assert len(checkpoints) == 0

    def test_update_progress(self):
        self.agent.update_progress("step 1")
        assert self.agent.progress.current_step == "step 1"
        assert self.agent.progress.total_steps == 1

    def test_update_progress_completed(self):
        self.agent.update_progress("step 1", completed=True)
        assert self.agent.progress.completed_steps == 1
        assert self.agent.progress.total_steps == 1

    def test_set_context(self):
        self.agent.set_context("key", "value")
        assert self.agent.get_context("key") == "value"

    def test_get_context_default(self):
        assert self.agent.get_context("nonexistent", "default") == "default"

    def test_add_tool_result(self):
        self.agent.add_tool_result("read_file", {"content": "hello"})
        assert len(self.agent._tool_results) == 1
        assert self.agent._tool_results[0]["tool_name"] == "read_file"

    def test_set_error(self):
        self.agent.set_error("Something went wrong")
        assert self.agent.progress.error == "Something went wrong"
        assert self.agent.state == AgentState.FAILED
        assert self.agent.progress.status == "failed"

    def test_to_memory_entry(self):
        self.agent.update_progress("step 1", completed=True)
        entry = self.agent.to_memory_entry()
        assert entry["session_id"] == "session_1"
        assert entry["state"] == "idle"
        assert entry["progress_percent"] == 100.0
        assert entry["total_steps"] == 1
        assert entry["completed_steps"] == 1


# ─── Convenience Functions ────────────────────────────────────────────────────

class TestConvenienceFunctions:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        # Reset singleton
        import tektos.runtime.long_running_agent as m
        m._agents.clear()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        import tektos.runtime.long_running_agent as m
        m._agents.clear()

    def test_get_long_running_agent(self):
        a1 = get_long_running_agent("session_1", checkpoint_dir=self.tmpdir)
        a2 = get_long_running_agent("session_1", checkpoint_dir=self.tmpdir)
        assert a1 is a2

    def test_get_long_running_agent_different_sessions(self):
        a1 = get_long_running_agent("session_1", checkpoint_dir=self.tmpdir)
        a2 = get_long_running_agent("session_2", checkpoint_dir=self.tmpdir)
        assert a1 is not a2

    def test_list_long_running_agents(self):
        get_long_running_agent("session_1", checkpoint_dir=self.tmpdir)
        get_long_running_agent("session_2", checkpoint_dir=self.tmpdir)
        agents = list_long_running_agents()
        assert "session_1" in agents
        assert "session_2" in agents
        assert len(agents) == 2
