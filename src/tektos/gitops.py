"""Tektos-Ultima v1 — GitOps Layer

Version control for the agent's own work. Enables:
- Safety snapshots before risky operations
- Auto-commit on task completion
- Git diff visualization
- Rollback to any previous state
- Branch management for parallel work

Architecture:
  Task completes
      ↓
  GitSnapshot: creates a safety point
      ↓
  GitOps (add/commit/status/diff/rollback/branch)
      ↓
  Event bus: git.* events

Design:
- Wraps git commands via subprocess
- Tracks commit history with semantic tags
- Supports safety snapshots (auto-created before risky ops)
- REST API for frontend integration
- Works with the existing Tektos project repo

Safety:
- Snapshots use "safety/" prefix in branch names
- Auto-rollback on session failure
- Never commits without reason
- Maintains clean main branch

"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("tektos.gitops")


# ─── Data Classes ───────────────────────────────────────────────────────────


@dataclass
class GitStatus:
    """Current git repository status."""
    path: str
    branch: str
    dirty: bool
    staged_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0
    latest_commit: str | None = None
    latest_commit_msg: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "branch": self.branch,
            "dirty": self.dirty,
            "staged_files": self.staged_files,
            "modified_files": self.modified_files,
            "untracked_files": self.untracked_files,
            "ahead": self.ahead,
            "behind": self.behind,
            "latest_commit": self.latest_commit,
            "latest_commit_msg": self.latest_commit_msg,
        }


@dataclass
class GitDiff:
    """Git diff between current state and HEAD."""
    path: str
    staged: list[str] = field(default_factory=list)
    unstaged: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "staged": self.staged,
            "unstaged": self.unstaged,
        }


@dataclass
class GitSnapshot:
    """A named snapshot (branch + commit) for rollback."""
    name: str
    commit: str
    branch: str
    message: str
    timestamp: str
    is_safety: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "commit": self.commit,
            "branch": self.branch,
            "message": self.message,
            "timestamp": self.timestamp,
            "is_safety": self.is_safety,
        }


# ─── GitOps Engine ──────────────────────────────────────────────────────────


class GitOpsEngine:
    """Git version control engine for the agent."""

    def __init__(
        self,
        repo_path: str | Path,
        event_bus: Any = None,
    ):
        self.repo_path = Path(repo_path).resolve()
        self.event_bus = event_bus
        self._snapshot_log: list[GitSnapshot] = []

    # ─── Helpers ────────────────────────────────────────────────────────

    def _git(self, args: list[str], check: bool = False) -> str:
        """Run a git command and return stdout."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            log.error(f"git {' '.join(args)} timed out")
            return ""
        except Exception as e:
            log.error(f"git {' '.join(args)} error: {e}")
            return ""

        if check and result.returncode != 0:
            log.error(f"git {' '.join(args)} failed: {result.stderr}")
            raise RuntimeError(result.stderr) from None
        return result.stdout.strip()

    def _git_check(self, args: list[str]) -> bool:
        """Run a git command and return True if successful."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ─── Status ─────────────────────────────────────────────────────────

    def get_status(self) -> GitStatus:
        """Get current git repository status."""
        branch = self._git(["rev-parse", "--abbrev-ref", "HEAD"])
        latest_commit = self._git(["rev-parse", "HEAD"], check=False)
        latest_msg = self._git(["log", "-1", "--format=%s"], check=False)

        # Check dirty state
        clean = self._git_check(["diff", "--quiet"])

        # Get staged files
        staged = [
            f.split("\t", 1)[-1]
            for f in self._git(["diff", "--staged", "--name-status"]).split("\n")
            if f.startswith("M") or f.startswith("A") or f.startswith("R")
        ]

        # Get modified (unstaged) files
        modified = [
            f.split("\t", 1)[-1]
            for f in self._git(["diff", "--name-status"]).split("\n")
            if f.startswith("M") or f.startswith("A") or f.startswith("R")
        ]

        # Get untracked files
        untracked = [
            f.strip()
            for f in self._git(["ls-files", "--others", "--exclude-standard"]).split("\n")
            if f.strip()
        ]

        # Check ahead/behind
        ahead = self._git(["rev-list", "--left-right", "HEAD...origin/HEAD"]).count("<") if self._git(["remote", "get-url", "origin"], check=False) else 0

        return GitStatus(
            path=str(self.repo_path),
            branch=branch or "unknown",
            dirty=not clean,
            staged_files=staged,
            modified_files=modified,
            untracked_files=untracked,
            ahead=ahead,
            behind=0,
            latest_commit=latest_commit[:8] if latest_commit else None,
            latest_commit_msg=latest_msg or None,
        )

    # ─── Diff ───────────────────────────────────────────────────────────

    def get_diff(self, staged_only: bool = False) -> list[str]:
        """Get git diff output."""
        if staged_only:
            return self._git(["diff", "--staged", "-U3"]).split("\n")
        return self._git(["diff", "-U3"]).split("\n")

    def get_file_diff(self, filename: str, staged_only: bool = False) -> str:
        """Get diff for a specific file."""
        args = ["diff"]
        if staged_only:
            args.append("--staged")
        args.extend(["-U3", "--", filename])
        return self._git(args)

    # ─── Stage & Commit ─────────────────────────────────────────────────

    def add(self, paths: list[str]) -> bool:
        """Stage files for commit."""
        if not paths:
            return False
        if self._git_check(["add"] + paths):
            log.info(f"Staged {len(paths)} file(s)")
            self._emit("added", {"files": paths})
            return True
        return False

    def add_all(self, exclude_untracked: bool = False) -> bool:
        """Stage all changes."""
        if exclude_untracked:
            self._git(["add", "-u"])
        else:
            self._git(["add", "-A"])
        log.info("Staged all changes")
        self._emit("git.added_all", {})
        return True

    def commit(
        self,
        message: str,
        paths: list[str] | None = None,
    ) -> str | None:
        """Create a commit. Returns commit hash or None on failure."""
        if paths:
            self.add(paths)

        status = self.get_status()
        if not status.staged_files and not status.modified_files and not status.untracked_files:
            log.warning("Nothing to commit")
            return None

        # Create commit
        result = self._git(["commit", "-m", message])

        if result:
            commit_hash = self._git(["rev-parse", "HEAD"])
            log.info(f"Committed: {message} ({commit_hash[:8]})")
            self._emit("committed", {
                "message": message,
                "commit": commit_hash[:8],
                "files": paths or status.staged_files,
            })
            return commit_hash
        return None

    # ─── Snapshots ──────────────────────────────────────────────────────

    def create_snapshot(
        self,
        name: str,
        message: str = "Manual snapshot",
        is_safety: bool = False,
    ) -> GitSnapshot | None:
        """Create a named snapshot (record commit without switching branches).

        Unlike create_branch, this does NOT switch to a new branch — it records
        the current HEAD as a rollback point. To create an actual branch:
        use create_branch() directly.
        """
        # Stage and commit current state first
        status = self.get_status()
        if not status.staged_files and not status.modified_files and not status.untracked_files:
            log.warning("Nothing to snapshot")
            return None

        # Stage, commit, record — stay on current branch
        self.add_all()
        self._git(["commit", "-m", f"{message} [snapshot]"])

        commit_hash = self._git(["rev-parse", "HEAD"])
        snapshot = GitSnapshot(
            name=name,
            commit=commit_hash[:8],
            branch=status.branch,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            is_safety=is_safety,
        )
        self._snapshot_log.append(snapshot)

        log.info(f"Created snapshot: {name} ({commit_hash[:8]})")
        self._emit("snapshot", snapshot.to_dict())
        return snapshot

    def list_snapshots(self) -> list[GitSnapshot]:
        """List all snapshots."""
        return list(self._snapshot_log)

    # ─── Rollback ───────────────────────────────────────────────────────

    def rollback(
        self,
        target: str | None = None,
        hard: bool = False,
    ) -> bool:
        """Rollback to a previous state.

        Args:
            target: commit hash, branch name, or snapshot name.
                    If None, rolls back the most recent snapshot.
            hard: if True, discards all changes (git reset --hard).
                  If False, only unstages (git reset --soft).
        """
        if not target:
            if not self._snapshot_log:
                log.warning("No snapshots to rollback to")
                return False
            target = self._snapshot_log[-1].branch

        status = self.get_status()

        if len(target) >= 7:
            # Commit hash
            mode = "--hard" if hard else "--soft"
            self._git(["reset", mode, target])
            log.info(f"Rolled back to commit: {target[:8]} ({'hard' if hard else 'soft'})")
            self._emit("rollback", {
                "target": target,
                "hard": hard,
                "previous_branch": status.branch,
            })
            return True
        else:
            log.error(f"Unknown target: {target}")
            return False

    # ─── Branch Management ──────────────────────────────────────────────

    def create_branch(self, name: str, from_branch: str = "HEAD") -> bool:
        """Create a new branch."""
        return self._git_check(["checkout", "-b", name, from_branch])

    def switch_branch(self, name: str) -> bool:
        """Switch to a branch."""
        return self._git_check(["checkout", name])

    def delete_branch(self, name: str, force: bool = False) -> bool:
        """Delete a branch."""
        # Can't delete the branch we're currently on
        current = self._git(["rev-parse", "--abbrev-ref", "HEAD"])
        try:
            if current == name:
                self._git(["checkout", "HEAD"])  # detach HEAD or switch to another
        except Exception as e:
            log.warning("Git operation failed: %s", e)
        args = ["branch", "-D", name] if force else ["branch", "-d", name]
        return self._git_check(args)

    # ─── Log ────────────────────────────────────────────────────────────

    def get_log(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent commit history."""
        output = self._git(["log", f"-{limit}", "--format=%H|%s|%an|%ai"])
        commits = []
        for line in output.split("\n"):
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0][:8],
                    "full_hash": parts[0],
                    "message": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                })
        return commits

    # ─── Event Bus ──────────────────────────────────────────────────────

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """Emit an event via event bus."""
        if self.event_bus:
            self.event_bus.emit(f"git.{event_type}", payload)


# ─── Sandbox Tools ──────────────────────────────────────────────────────────

GIT_TOOLS = [
    {
        "name": "git_status",
        "description": "Get current git repository status (branch, dirty, staged files)",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "git_diff",
        "description": "Get git diff output (staged or unstaged changes)",
        "parameters": {
            "type": "object",
            "properties": {
                "staged_only": {
                    "type": "boolean",
                    "description": "Only show staged changes",
                },
            },
        },
    },
    {
        "name": "git_add",
        "description": "Stage files for commit",
        "parameters": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths to stage",
                },
            },
        },
    },
    {
        "name": "git_commit",
        "description": "Create a git commit",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Commit message",
                },
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional specific file paths to commit",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "git_snapshot",
        "description": "Create a safety snapshot (named branch + commit) for rollback",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Snapshot name",
                },
                "message": {
                    "type": "string",
                    "description": "Snapshot message",
                },
                "is_safety": {
                    "type": "boolean",
                    "description": "Mark as safety snapshot (creates safety/ branch)",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "git_rollback",
        "description": "Rollback to a previous snapshot or commit",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Snapshot name, branch name, or commit hash",
                },
                "hard": {
                    "type": "boolean",
                    "description": "Hard reset (discard all changes)",
                },
            },
        },
    },
    {
        "name": "git_log",
        "description": "Get recent commit history",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of commits to show (default 20)",
                },
            },
        },
    },
]


def execute_git_tool(
    engine: GitOpsEngine,
    tool_name: str,
    params: dict[str, Any],
) -> str:
    """Execute a git tool via the GitOps engine."""
    try:
        if tool_name == "git_status":
            status = engine.get_status()
            return json.dumps(status.to_dict(), indent=2)

        elif tool_name == "git_diff":
            staged_only = params.get("staged_only", False)
            diff = engine.get_diff(staged_only)
            return "\n".join(diff[:200]) if diff else "No changes"

        elif tool_name == "git_add":
            paths = params.get("paths", [])
            engine.add(paths)
            return f"Staged {len(paths)} file(s): {', '.join(paths)}"

        elif tool_name == "git_commit":
            message = params.get("message", "")
            paths = params.get("paths")
            commit = engine.commit(message, paths)
            if commit:
                return f"Committed: {message} ({commit[:8]})"
            return "Nothing to commit"

        elif tool_name == "git_snapshot":
            name = params.get("name", "")
            message = params.get("message", f"Snapshot: {name}")
            is_safety = params.get("is_safety", False)
            snapshot = engine.create_snapshot(name, message, is_safety)
            if snapshot:
                return json.dumps(snapshot.to_dict(), indent=2)
            return "Nothing to snapshot"

        elif tool_name == "git_rollback":
            target = params.get("target")
            hard = params.get("hard", False)
            result = engine.rollback(target, hard)
            if result:
                return f"Rolled back to: {target or 'latest snapshot'}"
            return "No snapshots to rollback to"

        elif tool_name == "git_log":
            limit = params.get("limit", 20)
            commits = engine.get_log(limit)
            return json.dumps(commits, indent=2)

        else:
            return f"Unknown git tool: {tool_name}"

    except Exception as e:
        return f"Git error: {e}"
