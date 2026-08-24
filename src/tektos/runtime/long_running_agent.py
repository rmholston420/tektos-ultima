"""Long-Running Agent Support — Checkpointing and State Persistence.

Implements checkpointing and state persistence for long-running agents,
enabling agents to run for hours or days with automatic recovery from
interruptions.

Key features:
- Checkpoint/resume capability
- State persistence across interruptions
- Background execution with progress tracking
- Automatic recovery from failures
- Progress reporting and monitoring

SOTA Reference: LangGraph checkpointing, Microsoft Agent Framework,
OpenHands long-running agents.
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


class AgentState(Enum):
    """Agent execution states."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CHECKPOINTED = "checkpointed"


@dataclass
class AgentCheckpoint:
    """A checkpoint of agent state for persistence and resume."""
    checkpoint_id: str
    session_id: str
    state: AgentState
    timestamp: float
    context: dict[str, Any]
    memory: dict[str, Any]
    tool_results: list[dict[str, Any]]
    next_action: str | None = None
    error: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "state": self.state.value,
            "timestamp": self.timestamp,
            "context": self.context,
            "memory": self.memory,
            "tool_results": self.tool_results,
            "next_action": self.next_action,
            "error": self.error,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCheckpoint:
        """Create checkpoint from dictionary."""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            session_id=data["session_id"],
            state=AgentState(data["state"]),
            timestamp=data["timestamp"],
            context=data.get("context", {}),
            memory=data.get("memory", {}),
            tool_results=data.get("tool_results", []),
            next_action=data.get("next_action"),
            error=data.get("error"),
        )


@dataclass
class AgentProgress:
    """Progress tracking for long-running agents."""
    session_id: str
    started_at: float
    last_checkpoint_at: float
    total_steps: int = 0
    completed_steps: int = 0
    current_step: str = ""
    status: str = "running"
    error: str | None = None
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100
    
    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time in seconds."""
        return time.time() - self.started_at
    
    @property
    def elapsed_minutes(self) -> float:
        """Calculate elapsed time in minutes."""
        return self.elapsed_seconds / 60
    
    def to_markdown(self) -> str:
        """Convert to markdown for display."""
        return (
            f"**Session**: {self.session_id}\n"
            f"**Status**: {self.status}\n"
            f"**Progress**: {self.progress_percent:.1f}% ({self.completed_steps}/{self.total_steps} steps)\n"
            f"**Current Step**: {self.current_step}\n"
            f"**Elapsed**: {self.elapsed_minutes:.1f} minutes\n"
            f"**Last Checkpoint**: {self.last_checkpoint_at}\n"
            f"{'**Error**: ' + self.error if self.error else ''}"
        )


class CheckpointManager:
    """Manages checkpoints for long-running agents.
    
    Handles checkpoint creation, loading, and cleanup.
    """
    
    def __init__(self, checkpoint_dir: str = "./checkpoints"):
        """Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoints.
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoints: dict[str, list[AgentCheckpoint]] = {}
    
    async def save_checkpoint(self, checkpoint: AgentCheckpoint) -> str:
        """Save a checkpoint to disk.
        
        Args:
            checkpoint: The checkpoint to save.
        
        Returns:
            Checkpoint file path.
        """
        # Create session directory
        session_dir = self.checkpoint_dir / checkpoint.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save checkpoint
        filepath = session_dir / f"{checkpoint.checkpoint_id}.json"
        with open(filepath, 'w') as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        
        # Update in-memory index
        if checkpoint.session_id not in self._checkpoints:
            self._checkpoints[checkpoint.session_id] = []
        self._checkpoints[checkpoint.session_id].append(checkpoint)
        
        log.info(f"[Checkpoint] Saved checkpoint {checkpoint.checkpoint_id} "
                f"for session {checkpoint.session_id}")
        
        return str(filepath)
    
    async def load_checkpoint(self, session_id: str,
                              checkpoint_id: str | None = None) -> AgentCheckpoint | None:
        """Load a checkpoint from disk.
        
        Args:
            session_id: Session ID to load checkpoint for.
            checkpoint_id: Specific checkpoint ID (or None for latest).
        
        Returns:
            Loaded checkpoint, or None if not found.
        """
        session_dir = self.checkpoint_dir / session_id
        if not session_dir.exists():
            return None
        
        if checkpoint_id:
            # Load specific checkpoint
            filepath = session_dir / f"{checkpoint_id}.json"
            if filepath.exists():
                with open(filepath, 'r') as f:
                    data = json.load(f)
                return AgentCheckpoint.from_dict(data)
        else:
            # Load latest checkpoint
            checkpoints = sorted(
                session_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if checkpoints:
                with open(checkpoints[0], 'r') as f:
                    data = json.load(f)
                return AgentCheckpoint.from_dict(data)
        
        return None
    
    async def list_checkpoints(self, session_id: str) -> list[AgentCheckpoint]:
        """List all checkpoints for a session.
        
        Args:
            session_id: Session ID to list checkpoints for.
        
        Returns:
            List of checkpoints sorted by timestamp (newest first).
        """
        session_dir = self.checkpoint_dir / session_id
        if not session_dir.exists():
            return []
        
        checkpoints = []
        for filepath in sorted(session_dir.glob("*.json"),
                               key=lambda p: p.stat().st_mtime,
                               reverse=True):
            with open(filepath, 'r') as f:
                data = json.load(f)
            checkpoints.append(AgentCheckpoint.from_dict(data))
        
        return checkpoints
    
    async def cleanup_old_checkpoints(self, session_id: str,
                                      keep_last: int = 5) -> int:
        """Clean up old checkpoints, keeping only the most recent.
        
        Args:
            session_id: Session ID to clean up.
            keep_last: Number of recent checkpoints to keep.
        
        Returns:
            Number of checkpoints removed.
        """
        session_dir = self.checkpoint_dir / session_id
        if not session_dir.exists():
            return 0
        
        checkpoints = sorted(
            session_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        
        removed = 0
        for filepath in checkpoints[keep_last:]:
            filepath.unlink()
            removed += 1
        
        if removed:
            log.info(f"[Checkpoint] Cleaned up {removed} old checkpoints "
                    f"for session {session_id}")
        
        return removed
    
    async def delete_session_checkpoints(self, session_id: str) -> int:
        """Delete all checkpoints for a session.
        
        Args:
            session_id: Session ID to delete checkpoints for.
        
        Returns:
            Number of checkpoints removed.
        """
        session_dir = self.checkpoint_dir / session_id
        if not session_dir.exists():
            return 0
        
        checkpoints = list(session_dir.glob("*.json"))
        for filepath in checkpoints:
            filepath.unlink()
        
        # Remove session directory if empty
        if not list(session_dir.glob("*")):
            session_dir.rmdir()
        
        log.info(f"[Checkpoint] Deleted {len(checkpoints)} checkpoints "
                f"for session {session_id}")
        
        return len(checkpoints)


class LongRunningAgent:
    """Long-running agent with checkpointing and state persistence.
    
    Enables agents to run for hours or days with automatic recovery
    from interruptions.
    """
    
    def __init__(self, session_id: str, checkpoint_dir: str = "./checkpoints"):
        """Initialize long-running agent.
        
        Args:
            session_id: Session ID for this agent.
            checkpoint_dir: Directory to store checkpoints.
        """
        self.session_id = session_id
        self.checkpoint_manager = CheckpointManager(checkpoint_dir=checkpoint_dir)
        self.state = AgentState.IDLE
        self.progress = AgentProgress(
            session_id=session_id,
            started_at=time.time(),
            last_checkpoint_at=time.time(),
        )
        self._context: dict[str, Any] = {}
        self._memory: dict[str, Any] = {}
        self._tool_results: list[dict[str, Any]] = []
        self._checkpoint_interval: float = 300.0  # 5 minutes
        self._last_checkpoint_time: float = time.time()
        self._running: bool = False
    
    async def start(self) -> None:
        """Start the long-running agent."""
        self.state = AgentState.RUNNING
        self._running = True
        self.progress.status = "running"
        log.info(f"[LongRunningAgent] Started session {self.session_id}")
    
    async def stop(self, reason: str = "completed") -> None:
        """Stop the long-running agent.
        
        Args:
            reason: Reason for stopping.
        """
        self._running = False
        self.state = AgentState.COMPLETED if reason == "completed" else AgentState.FAILED
        self.progress.status = reason
        log.info(f"[LongRunningAgent] Stopped session {self.session_id}: {reason}")
    
    async def pause(self) -> None:
        """Pause the long-running agent and create checkpoint."""
        self.state = AgentState.PAUSED
        self.progress.status = "paused"
        await self._create_checkpoint()
        log.info(f"[LongRunningAgent] Paused session {self.session_id}")
    
    async def resume(self) -> bool:
        """Resume the long-running agent from last checkpoint.
        
        Returns:
            True if resumed successfully, False if no checkpoint found.
        """
        checkpoint = await self.checkpoint_manager.load_checkpoint(self.session_id)
        if checkpoint:
            self.state = checkpoint.state
            self._context = checkpoint.context
            self._memory = checkpoint.memory
            self._tool_results = checkpoint.tool_results
            self.progress.status = "running"
            log.info(f"[LongRunningAgent] Resumed session {self.session_id} "
                    f"from checkpoint {checkpoint.checkpoint_id}")
            return True
        else:
            log.warning(f"[LongRunningAgent] No checkpoint found for session {self.session_id}")
            return False
    
    async def _create_checkpoint(self) -> None:
        """Create a checkpoint of current state."""
        checkpoint = AgentCheckpoint(
            checkpoint_id=f"ckpt_{int(time.time())}",
            session_id=self.session_id,
            state=self.state,
            timestamp=time.time(),
            context=self._context.copy(),
            memory=self._memory.copy(),
            tool_results=self._tool_results.copy(),
            next_action=self.progress.current_step,
            error=self.progress.error,
        )
        
        await self.checkpoint_manager.save_checkpoint(checkpoint)
        self._last_checkpoint_time = time.time()
        self.progress.last_checkpoint_at = time.time()
    
    async def checkpoint_if_needed(self) -> None:
        """Create checkpoint if interval has elapsed."""
        if time.time() - self._last_checkpoint_time > self._checkpoint_interval:
            await self._create_checkpoint()
    
    def update_progress(self, current_step: str, completed: bool = False) -> None:
        """Update agent progress.
        
        Args:
            current_step: Current step description.
            completed: Whether the step was completed.
        """
        self.progress.current_step = current_step
        if completed:
            self.progress.completed_steps += 1
        self.progress.total_steps += 1
    
    def set_context(self, key: str, value: Any) -> None:
        """Set context value.
        
        Args:
            key: Context key.
            value: Context value.
        """
        self._context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get context value.
        
        Args:
            key: Context key.
            default: Default value if key not found.
        
        Returns:
            Context value.
        """
        return self._context.get(key, default)
    
    def add_tool_result(self, tool_name: str, result: dict[str, Any]) -> None:
        """Add tool result to history.
        
        Args:
            tool_name: Name of the tool.
            result: Tool result.
        """
        self._tool_results.append({
            "tool_name": tool_name,
            "result": result,
            "timestamp": time.time(),
        })
    
    def set_error(self, error: str) -> None:
        """Set error state.
        
        Args:
            error: Error message.
        """
        self.progress.error = error
        self.state = AgentState.FAILED
        self.progress.status = "failed"
    
    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "progress_percent": self.progress.progress_percent,
            "elapsed_minutes": self.progress.elapsed_minutes,
            "total_steps": self.progress.total_steps,
            "completed_steps": self.progress.completed_steps,
            "checkpoint_count": len(self.checkpoint_manager._checkpoints.get(self.session_id, [])),
        }


# ── Convenience Functions ───────────────────────────────────────────────────

_agents: dict[str, LongRunningAgent] = {}


def get_long_running_agent(session_id: str,
                           checkpoint_dir: str = "./checkpoints") -> LongRunningAgent:
    """Get or create a long-running agent.
    
    Args:
        session_id: Session ID for this agent.
        checkpoint_dir: Directory to store checkpoints.
    
    Returns:
        LongRunningAgent instance.
    """
    if session_id not in _agents:
        _agents[session_id] = LongRunningAgent(
            session_id=session_id,
            checkpoint_dir=checkpoint_dir,
        )
    return _agents[session_id]


def list_long_running_agents() -> list[str]:
    """List all active long-running agent session IDs.
    
    Returns:
        List of session IDs.
    """
    return list(_agents.keys())
