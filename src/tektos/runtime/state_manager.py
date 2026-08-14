"""LAST_KNOWN_STATE.md generator and loader for session continuity.

Provides structured state persistence across Hermes agent sessions.
Saved to Hindsight memory, loaded at session start to provide
continuity without context window limitations.

Format:
- Header: Project name, timestamp, session ID
- Objective: Current goal and progress
- State: Current files, running processes, API status
- Decisions: Key architectural and design decisions
- Blockers: What's blocking progress
- Next Steps: Exact commands and files for resuming work
- Context: Token usage, memory state, constraints
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class LastKnownState:
    """Structured state for session continuity.
    
    This is the single source of truth for resuming work after
    a session ends or context is lost.
    """
    project: str
    timestamp: str
    session_id: str | None = None
    
    # Objective and progress
    objective: str = ""
    progress: str = ""
    completion_pct: float = 0.0
    
    # Current state
    current_file: str = ""
    current_command: str = ""
    running_processes: list[str] = field(default_factory=list)
    api_endpoints: dict[str, str] = field(default_factory=dict)
    
    # Decisions and context
    key_decisions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    
    # Next steps
    next_steps: list[str] = field(default_factory=list)
    exact_commands: list[str] = field(default_factory=list)
    
    # Blockers
    blockers: list[str] = field(default_factory=list)
    
    # Task list
    todo_items: list[dict[str, Any]] = field(default_factory=list)
    
    # Environment
    environment: dict[str, str] = field(default_factory=dict)
    
    # Memory state
    memory_context: str = ""
    
    # Files referenced
    referenced_files: list[str] = field(default_factory=list)
    
    def to_markdown(self) -> str:
        """Convert to LAST_KNOWN_STATE.md format."""
        lines = []
        
        # Header
        lines.append(f"# LAST_KNOWN_STATE.md")
        lines.append(f"")
        lines.append(f"**Project:** {self.project}")
        lines.append(f"**Timestamp:** {self.timestamp}")
        lines.append(f"**Session:** {self.session_id or 'N/A'}")
        lines.append(f"")
        
        # Objective
        lines.append(f"## Objective")
        lines.append(f"")
        lines.append(f"{self.objective}")
        lines.append(f"")
        lines.append(f"**Progress:** {self.progress}")
        if self.completion_pct:
            lines.append(f"**Completion:** {self.completion_pct}%")
        lines.append(f"")
        
        # Current State
        lines.append(f"## Current State")
        lines.append(f"")
        if self.current_file:
            lines.append(f"- **Current File:** `{self.current_file}`")
        if self.current_command:
            lines.append(f"- **Current Command:** `{self.current_command}`")
        if self.running_processes:
            lines.append(f"- **Running:** {', '.join(self.running_processes)}")
        if self.api_endpoints:
            lines.append(f"- **APIs:**")
            for endpoint, status in self.api_endpoints.items():
                lines.append(f"  - `{endpoint}`: {status}")
        lines.append(f"")
        
        # Key Decisions
        if self.key_decisions:
            lines.append(f"## Key Decisions")
            lines.append(f"")
            for i, decision in enumerate(self.key_decisions, 1):
                lines.append(f"{i}. {decision}")
            lines.append(f"")
        
        # Constraints
        if self.constraints:
            lines.append(f"## Constraints")
            lines.append(f"")
            for constraint in self.constraints:
                lines.append(f"- {constraint}")
            lines.append(f"")
        
        # Next Steps
        if self.next_steps:
            lines.append(f"## Next Steps")
            lines.append(f"")
            for i, step in enumerate(self.next_steps, 1):
                lines.append(f"{i}. {step}")
            lines.append(f"")
        
        # Exact Commands
        if self.exact_commands:
            lines.append(f"## Exact Commands")
            lines.append(f"")
            for cmd in self.exact_commands:
                lines.append(f"```bash")
                lines.append(f"{cmd}")
                lines.append(f"```")
            lines.append(f"")
        
        # Task List
        if self.todo_items:
            lines.append(f"## Task List")
            lines.append(f"")
            for item in self.todo_items:
                status = "✓" if item.get("status") == "completed" else "○"
                content = item.get("content", "")
                lines.append(f"- [{status}] {content}")
            lines.append(f"")
        
        # Blockers
        if self.blockers:
            lines.append(f"## Blockers")
            lines.append(f"")
            for blocker in self.blockers:
                lines.append(f"- 🚫 {blocker}")
            lines.append(f"")
        
        # Notes
        if self.notes:
            lines.append(f"## Notes")
            lines.append(f"")
            for note in self.notes:
                lines.append(f"- {note}")
            lines.append(f"")
        
        # Memory Context
        if self.memory_context:
            lines.append(f"## Memory Context")
            lines.append(f"")
            lines.append(f"{self.memory_context}")
            lines.append(f"")
        
        # Referenced Files
        if self.referenced_files:
            lines.append(f"## Referenced Files")
            lines.append(f"")
            for f in self.referenced_files:
                lines.append(f"- `{f}`")
            lines.append(f"")
        
        return "\n".join(lines)
    
    @classmethod
    def from_markdown(cls, md: str, project: str) -> "LastKnownState":
        """Parse LAST_KNOWN_STATE.md (simplified reconstruction)."""
        state = cls(
            project=project,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        
        # Extract objective
        if "## Objective" in md:
            obj_section = md.split("## Objective")[1].split("##")[0]
            state.objective = obj_section.strip()
        
        # Extract current file
        if "Current File:" in md:
            state.current_file = md.split("Current File:")[1].split("`")[1]
        
        # Extract next steps
        if "## Next Steps" in md:
            steps_section = md.split("## Next Steps")[1].split("##")[0]
            for line in steps_section.strip().split("\n"):
                if line.strip().startswith(("-", "*")):
                    state.next_steps.append(line.strip("- *").strip())
        
        return state
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LastKnownState":
        """Reconstruct from dict."""
        return cls(**data)


class StateManager:
    """Manages LAST_KNOWN_STATE.md persistence and retrieval.
    
    Handles:
    - Saving state to Hindsight on session end
    - Loading state at session start
    - Updating state incrementally during work
    """
    
    def __init__(self, project: str, workspace: str = "/home/rmholston"):
        self.project = project
        self.workspace = Path(workspace)
        self.state_file = self.workspace / "LAST_KNOWN_STATE.md"
        self.hindsight_tag = "last-known-state"
    
    def load_state(self) -> LastKnownState:
        """Load last known state from Hindsight or file."""
        # Try Hindsight first
        state = self._load_from_hindsight()
        if state:
            return state
        
        # Fall back to file
        if self.state_file.exists():
            md = self.state_file.read_text()
            return LastKnownState.from_markdown(md, self.project)
        
        # No state found
        return LastKnownState(
            project=self.project,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    
    def save_state(self, state: LastKnownState) -> None:
        """Save state to Hindsight and file."""
        # Save to file
        md = state.to_markdown()
        self.state_file.write_text(md)
        
        # Save to Hindsight
        self._save_to_hindsight(state)
    
    def update_state(self, **kwargs) -> LastKnownState:
        """Incrementally update state fields."""
        state = self.load_state()
        
        for key, value in kwargs.items():
            if hasattr(state, key):
                current = getattr(state, key)
                if isinstance(current, list) and isinstance(value, list):
                    current.extend(value)
                else:
                    setattr(state, key, value)
        
        self.save_state(state)
        return state
    
    def _load_from_hindsight(self) -> LastKnownState | None:
        """Load state from Hindsight memory."""
        # This will be implemented via hindsight_recall in the agent
        # For now, return None
        return None
    
    def _save_to_hindsight(self, state: LastKnownState) -> None:
        """Save state to Hindsight memory."""
        # This will be implemented via hindsight_retain in the agent
        # Format: concise summary + full MD as attachment
        pass


def create_default_state(project: str) -> LastKnownState:
    """Create a default state template for a new project."""
    return LastKnownState(
        project=project,
        timestamp=datetime.now(timezone.utc).isoformat(),
        objective="Initialize project",
        progress="Setting up project structure",
        key_decisions=[],
        constraints=[],
        next_steps=[
            "Initialize git repository",
            "Create project structure",
            "Set up development environment",
        ],
        exact_commands=[],
        blockers=[],
        todo_items=[],
        environment={},
        memory_context="",
        referenced_files=[],
    )
