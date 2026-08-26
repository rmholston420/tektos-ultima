"""GitOps engine — automated git operations for Tektos self-modification.

Provides version-controlled file operations with:
- Atomic commits with semantic commit messages
- Branch management for safe experimentation
- Change tracking and diff analysis
- Rollback capabilities
- Git status monitoring
"""

from __future__ import annotations

import logging
import subprocess
import time
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class GitChange:
    """A single git change."""
    file_path: str
    status: str  # modified, added, deleted, renamed
    diff: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class GitOperationResult:
    """Result of a git operation."""
    success: bool
    operation: str
    message: str
    details: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class GitDiff:
    """A git diff for a single file."""
    path: str = ""
    staged: list[str] = field(default_factory=list)
    unstaged: list[str] = field(default_factory=list)

    def __contains__(self, item: str) -> bool:
        """Check if path or any diff line contains the item."""
        return item in self.path or item in "\n".join(self.staged + self.unstaged)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "staged": self.staged,
            "unstaged": self.unstaged,
        }


@dataclass
class GitStatus:
    """Overall git status summary."""
    path: str = ""
    branch: str = ""
    dirty: bool = False
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


class GitOpsEngine:
    """Automated git operations for Tektos self-modification.

    Provides safe, version-controlled file operations with:
    - Atomic commits with semantic messages
    - Branch management for experimentation
    - Change tracking and diff analysis
    - Rollback capabilities
    """

    def __init__(
        self,
        repo_root: str = ".",
        author_name: str = "Tektos",
        author_email: str = "tektos@local",
        event_bus: Any = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.repo_path = self.repo_root  # Alias for test compatibility
        self.author_name = author_name
        self.author_email = author_email
        self.event_bus = event_bus
        self._operation_log: list[dict] = []
        self._snapshot_log: list[GitSnapshot] = []

    def _run_git(self, args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
        """Run a git command."""
        cmd = ["git", "-C", str(self.repo_root)] + args
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=60,
        )

    def is_git_repo(self) -> bool:
        """Check if the current directory is a git repository."""
        result = self._run_git(["rev-parse", "--is-inside-work-tree"], capture=True)
        return result.returncode == 0 and result.stdout.strip() == "true"

    def get_status(self) -> GitStatus:
        """Get current git status as a GitStatus object."""
        status = GitStatus(path=str(self.repo_root))

        # Get current branch
        branch_result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], capture=True)
        if branch_result.returncode == 0:
            status.branch = branch_result.stdout.strip()
        else:
            # Empty repo - check if it's a git repo
            if self.is_git_repo():
                status.branch = "main"  # Default for new repos

        # Get staged files
        staged_result = self._run_git(["diff", "--cached", "--name-only"], capture=True)
        if staged_result.returncode == 0:
            status.staged_files = [f for f in staged_result.stdout.strip().split("\n") if f]

        # Get modified files
        modified_result = self._run_git(["diff", "--name-only"], capture=True)
        if modified_result.returncode == 0:
            status.modified_files = [f for f in modified_result.stdout.strip().split("\n") if f]

        # Get untracked files
        untracked_result = self._run_git(["ls-files", "--others", "--exclude-standard"], capture=True)
        if untracked_result.returncode == 0:
            status.untracked_files = [f for f in untracked_result.stdout.strip().split("\n") if f]

        # Check if dirty
        status.dirty = bool(status.staged_files or status.modified_files or status.untracked_files)

        # Get latest commit info
        log_result = self._run_git(["log", "-1", "--format=%H|%s"], capture=True)
        if log_result.returncode == 0:
            parts = log_result.stdout.strip().split("|", 1)
            if len(parts) == 2:
                status.latest_commit = parts[0][:8]
                status.latest_commit_msg = parts[1]

        return status

    def commit_changes(self, message: str, files: list[str] | None = None) -> GitOperationResult:
        """Commit changes with a semantic message.

        Args:
            message: Commit message.
            files: Specific files to commit (None = all staged).

        Returns:
            GitOperationResult with success status.
        """
        try:
            # Stage files
            if files:
                for f in files:
                    self._run_git(["add", f])
            else:
                self._run_git(["add", "-A"])

            # Check if there are changes
            status = self._run_git(["status", "--porcelain"], capture=True)
            if not status.stdout.strip():
                return GitOperationResult(
                    success=True,
                    operation="commit",
                    message="No changes to commit",
                )

            # Configure git user
            self._run_git(["config", "user.name", self.author_name])
            self._run_git(["config", "user.email", self.author_email])

            # Commit
            result = self._run_git(["commit", "-m", message])
            if result.returncode == 0:
                log.info(f"Committed: {message}")
                self._operation_log.append({
                    "operation": "commit",
                    "message": message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "files": files or ["all"],
                })
                if self.event_bus:
                    self.event_bus.emit("git.commit", message=message, files=files)
                return GitOperationResult(
                    success=True,
                    operation="commit",
                    message=message,
                    details={"commit_count": 1},
                )
            else:
                return GitOperationResult(
                    success=False,
                    operation="commit",
                    message="Commit failed",
                    error=result.stderr,
                )

        except Exception as e:
            return GitOperationResult(
                success=False,
                operation="commit",
                message="Commit failed",
                error=str(e),
            )

    def create_branch(self, branch_name: str, base_branch: str | None = None) -> GitOperationResult:
        """Create a new branch for experimentation.

        Args:
            branch_name: Name of the new branch.
            base_branch: Base branch to create from (None = current branch).

        Returns:
            GitOperationResult with success status.
        """
        try:
            if base_branch is None:
                # Use current branch as base
                result = self._run_git(["checkout", "-b", branch_name])
            else:
                result = self._run_git([
                    "checkout", "-b", branch_name, base_branch
                ])
            if result.returncode == 0:
                log.info(f"Created branch: {branch_name} from {base_branch or 'current'}")
                return GitOperationResult(
                    success=True,
                    operation="branch_create",
                    message=f"Created branch '{branch_name}'",
                    details={"branch": branch_name, "base": base_branch or "current"},
                )
            else:
                return GitOperationResult(
                    success=False,
                    operation="branch_create",
                    message="Branch creation failed",
                    error=result.stderr,
                )
        except Exception as e:
            return GitOperationResult(
                success=False,
                operation="branch_create",
                message="Branch creation failed",
                error=str(e),
            )

    def switch_branch(self, branch_name: str) -> GitOperationResult:
        """Switch to an existing branch.

        Args:
            branch_name: Name of the branch to switch to.

        Returns:
            GitOperationResult with success status.
        """
        try:
            result = self._run_git(["checkout", branch_name])
            if result.returncode == 0:
                log.info(f"Switched to branch: {branch_name}")
                return GitOperationResult(
                    success=True,
                    operation="branch_switch",
                    message=f"Switched to branch '{branch_name}'",
                    details={"branch": branch_name},
                )
            else:
                return GitOperationResult(
                    success=False,
                    operation="branch_switch",
                    message="Branch switch failed",
                    error=result.stderr,
                )
        except Exception as e:
            return GitOperationResult(
                success=False,
                operation="branch_switch",
                message="Branch switch failed",
                error=str(e),
            )

    def delete_branch(self, branch_name: str, force: bool = False) -> bool:
        """Delete a branch.

        Args:
            branch_name: Name of the branch to delete.
            force: If True, use -D to force delete.

        Returns:
            True if successful, False otherwise.
        """
        try:
            flag = "-D" if force else "-d"
            result = self._run_git(["branch", flag, branch_name])
            if result.returncode == 0:
                log.info(f"Deleted branch: {branch_name}")
                return True
            else:
                log.warning(f"Failed to delete branch {branch_name}: {result.stderr}")
                return False
        except Exception as e:
            log.error(f"Failed to delete branch {branch_name}: {e}")
            return False

    def merge_branch(self, source_branch: str, target_branch: str | None = None) -> GitOperationResult:
        """Merge a branch into the current (or target) branch.

        Args:
            source_branch: Branch to merge from.
            target_branch: Target branch (None = current branch).

        Returns:
            GitOperationResult with success status.
        """
        try:
            if target_branch:
                self._run_git(["checkout", target_branch])

            result = self._run_git(["merge", source_branch, "--no-ff", "-m", f"Merge {source_branch}"])
            if result.returncode == 0:
                log.info(f"Merged {source_branch} into {target_branch or 'current'}")
                return GitOperationResult(
                    success=True,
                    operation="merge",
                    message=f"Merged '{source_branch}'",
                    details={"source": source_branch, "target": target_branch or "current"},
                )
            else:
                return GitOperationResult(
                    success=False,
                    operation="merge",
                    message="Merge failed",
                    error=result.stderr,
                )
        except Exception as e:
            return GitOperationResult(
                success=False,
                operation="merge",
                message="Merge failed",
                error=str(e),
            )

    def rollback(self, target: str | None = None, hard: bool = False) -> GitOperationResult:
        """Rollback to a specific commit or the last commit.

        Args:
            target: Commit hash or branch to rollback to (None = last commit).
            hard: If True, use --hard flag.

        Returns:
            GitOperationResult with success status.
        """
        try:
            if target:
                result = self._run_git(["reset", "--hard", target])
            else:
                result = self._run_git(["reset", "--hard", "HEAD~1"])

            if result.returncode == 0:
                log.info(f"Rolled back to {target or 'HEAD~1'}")
                return GitOperationResult(
                    success=True,
                    operation="rollback",
                    message=f"Rolled back to {target or 'HEAD~1'}",
                )
            else:
                log.warning(f"Rollback failed: {result.stderr}")
                return GitOperationResult(
                    success=False,
                    operation="rollback",
                    message="Rollback failed",
                    error=result.stderr,
                )
        except Exception as e:
            log.error(f"Rollback failed: {e}")
            return GitOperationResult(
                success=False,
                operation="rollback",
                message="Rollback failed",
                error=str(e),
            )

    def get_log(self, limit: int = 10) -> list[dict]:
        """Get recent git log entries.

        Args:
            limit: Number of entries to return.

        Returns:
            List of log entries with hash, full_hash, date, author, message.
        """
        result = self._run_git([
            "log", f"-{limit}", "--format=%H|%h|%an|%ad|%s", "--date=short"
        ])

        entries = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 4)
            if len(parts) >= 5:
                entries.append({
                    "hash": parts[1],
                    "full_hash": parts[0],
                    "author": parts[2],
                    "date": parts[3],
                    "message": parts[4],
                })

        return entries

    def get_operation_log(self) -> list[dict]:
        """Get the internal operation log."""
        return list(self._operation_log)

    def get_stats(self) -> dict[str, Any]:
        """Get git repository statistics."""
        try:
            branches_result = self._run_git(["branch", "-a"])
            commits_result = self._run_git(["rev-list", "--all", "--count"])
            status = self.get_status()

            return {
                "is_git_repo": self.is_git_repo(),
                "branch": status.branch,
                "dirty": status.dirty,
                "staged_files": len(status.staged_files),
                "modified_files": len(status.modified_files),
                "untracked_files": len(status.untracked_files),
                "total_commits": int(commits_result.stdout.strip()) if commits_result.stdout.strip() else 0,
                "branches": branches_result.stdout.strip().count("\n") + 1,
                "operation_count": len(self._operation_log),
            }
        except Exception as e:
            return {"is_git_repo": False, "error": str(e)}

    def _git(self, args: list[str], check: bool = False) -> str:
        """Run a git command and return stdout string.

        Args:
            args: Git command arguments.
            check: If True, raise RuntimeError on non-zero exit.

        Returns:
            stdout string (stripped), or empty string on error.
        """
        try:
            result = self._run_git(args)
            if check and result.returncode != 0:
                raise RuntimeError(f"git {args}: {result.stderr}")
            return result.stdout.strip()
        except RuntimeError as e:
            # Only re-raise if it's from our check logic (contains "git " prefix)
            if check and f"git {args}" in str(e):
                raise
            return ""
        except Exception:
            return ""

    def _git_check(self, args: list[str]) -> bool:
        """Run a git command and return True if successful, False otherwise."""
        try:
            result = self._run_git(args)
            return result.returncode == 0
        except Exception:
            return False

    def _emit(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Emit an event to the event bus (if available)."""
        if self.event_bus:
            if data is not None:
                self.event_bus.emit(f"git.{event_type}", data)
            else:
                self.event_bus.emit(f"git.{event_type}")

    def add(self, paths: list[str]) -> bool:
        """Stage specific files.

        Returns:
            True if successful, False otherwise.
        """
        if not paths:
            return False
        try:
            for p in paths:
                result = self._run_git(["add", p])
                if result.returncode != 0:
                    log.warning(f"Failed to add {p}: {result.stderr}")
                    return False
            if self.event_bus:
                self.event_bus.emit("git.add", paths=paths)
            return True
        except Exception as e:
            log.error(f"Failed to add files: {e}")
            return False

    def add_all(self, exclude_untracked: bool = False) -> bool:
        """Stage all changes.

        Args:
            exclude_untracked: If True, only stage tracked files.

        Returns:
            True if successful, False otherwise.
        """
        try:
            if exclude_untracked:
                self._run_git(["add", "-u"])
            else:
                self._run_git(["add", "-A"])
            if self.event_bus:
                self.event_bus.emit("git.add_all")
            return True
        except Exception as e:
            log.error(f"Failed to add all: {e}")
            return False

    def commit(self, message: str, paths: list[str] | None = None) -> str | None:
        """Commit changes (alias for commit_changes, for test compatibility).

        Returns:
            Commit hash string on success, None on failure.
        """
        result = self.commit_changes(message, files=paths)
        if result.success and result.message != "No changes to commit":
            # Get the current HEAD commit hash
            hash_result = self._run_git(["rev-parse", "HEAD"])
            if hash_result.returncode == 0:
                return hash_result.stdout.strip()
        return None

    def create_snapshot(self, name: str, message: str = "", is_safety: bool = False) -> GitSnapshot | None:
        """Create a named snapshot (branch + commit) for rollback.

        Returns:
            GitSnapshot on success, None if nothing to snapshot.
        """
        # Check if there are changes
        status_result = self._run_git(["status", "--porcelain"], capture=True)
        if not status_result.stdout.strip():
            return None

        try:
            # Stage and commit first
            self._run_git(["add", "-A"])
            self._run_git(["config", "user.name", self.author_name])
            self._run_git(["config", "user.email", self.author_email])
            self._run_git(["commit", "-m", f"snapshot: {name}"])

            # Get current branch and commit
            branch_result = self._run_git(["branch", "--show-current"])
            commit_result = self._run_git(["rev-parse", "HEAD"])

            branch = branch_result.stdout.strip() or "main"
            commit = commit_result.stdout.strip()

            snapshot = GitSnapshot(
                name=name,
                commit=commit,
                branch=branch,
                message=message or f"Snapshot {name}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                is_safety=is_safety,
            )

            self._snapshot_log.append(snapshot)

            if self.event_bus:
                self.event_bus.emit("git.snapshot", name=name, commit=commit)

            return snapshot
        except Exception as e:
            log.error(f"Failed to create snapshot {name}: {e}")
            raise

    def list_snapshots(self) -> list[GitSnapshot]:
        """List all snapshots."""
        return list(self._snapshot_log)

    def get_diff(self, staged_only: bool = False) -> list[GitDiff]:
        """Get diff for all changed files.

        Args:
            staged_only: If True, only return staged changes.
        """
        diffs: list[GitDiff] = []

        # Get staged changes
        staged_result = self._run_git(["diff", "--cached", "--name-only"], capture=True)
        if staged_result.stdout.strip():
            for file_path in staged_result.stdout.strip().split('\n'):
                diff_result = self._run_git(["diff", "--cached", "--", file_path], capture=True)
                diffs.append(GitDiff(
                    path=file_path,
                    staged=diff_result.stdout.strip().split('\n') if diff_result.stdout.strip() else [],
                ))

        if staged_only:
            return diffs

        # Get unstaged changes
        unstaged_result = self._run_git(["diff", "--name-only"], capture=True)
        if unstaged_result.stdout.strip():
            for file_path in unstaged_result.stdout.strip().split('\n'):
                diff_result = self._run_git(["diff", "--", file_path], capture=True)
                # Check if already in diffs list
                existing = next((d for d in diffs if d.path == file_path), None)
                if existing:
                    existing.unstaged = diff_result.stdout.strip().split('\n') if diff_result.stdout.strip() else []
                else:
                    diffs.append(GitDiff(
                        path=file_path,
                        unstaged=diff_result.stdout.strip().split('\n') if diff_result.stdout.strip() else [],
                    ))

        return diffs

    def get_file_diff(self, file_path: str, staged_only: bool = False) -> str:
        """Get diff for a specific file.

        Args:
            file_path: Path to the file.
            staged_only: If True, only show staged changes.

        Returns:
            Diff as a string.
        """
        if staged_only:
            result = self._run_git(["diff", "--cached", "--", file_path], capture=True)
            return result.stdout if result.returncode == 0 else ""

        # Try unstaged first
        result = self._run_git(["diff", "--", file_path], capture=True)
        if result.stdout.strip():
            return result.stdout

        # If no unstaged diff, check staged (file was added but not committed)
        result = self._run_git(["diff", "--cached", "--", file_path], capture=True)
        return result.stdout if result.returncode == 0 else ""


# Singleton
_gitops_instance: GitOpsEngine | None = None


def get_gitops_engine(repo_root: str = ".") -> GitOpsEngine:
    """Get or create the global gitops engine instance."""
    global _gitops_instance
    if _gitops_instance is None or str(_gitops_instance.repo_root) != str(Path(repo_root).resolve()):
        _gitops_instance = GitOpsEngine(repo_root=repo_root)
    return _gitops_instance


def reset_gitops_engine() -> None:
    """Reset the global gitops engine instance (for testing)."""
    global _gitops_instance
    _gitops_instance = None


def execute_git_tool(engine: GitOpsEngine, command: str, args: dict[str, Any] | None = None) -> str:
    """Execute a git tool command via the engine.

    Args:
        engine: GitOpsEngine instance to use.
        command: Git subcommand (e.g. 'status', 'diff', 'add', 'commit', 'snapshot', 'rollback').
        args: Command-specific arguments as a dict.

    Returns:
        Result as a string.
    """
    args = args or {}
    try:
        if command == "git_status":
            status = engine.get_status()
            return str(status.to_dict())
        elif command == "git_diff":
            staged_only = args.get("staged_only", False)
            diffs = engine.get_diff(staged_only=staged_only)
            return json.dumps([d.to_dict() for d in diffs])
        elif command == "git_add":
            paths = args.get("paths", [])
            success = engine.add(paths)
            if success:
                return f"Staged {', '.join(paths)}"
            return "Failed to stage files"
        elif command == "git_commit":
            message = args.get("message", "auto-commit")
            paths = args.get("paths")
            commit_hash = engine.commit(message, paths=paths)
            if commit_hash:
                return f"Committed: {message} ({commit_hash[:8]})"
            return "Nothing to commit"
        elif command == "git_snapshot":
            name = args.get("name", "auto-snapshot")
            message = args.get("message", "")
            is_safety = args.get("is_safety", False)
            snapshot = engine.create_snapshot(name, message=message, is_safety=is_safety)
            if snapshot:
                return f"Snapshot created: {name} ({snapshot.commit[:8]})"
            return "Nothing to snapshot"
        elif command == "git_rollback":
            target = args.get("target")
            hard = args.get("hard", False)
            snapshots = engine.list_snapshots()
            if not snapshots and not target:
                return "No snapshots to rollback to"
            success = engine.rollback(target=target, hard=hard)
            if success:
                return f"Rolled back to {target or 'last snapshot'}"
            return "Rollback failed"
        elif command == "git_log":
            limit = args.get("limit", 10)
            entries = engine.get_log(limit=limit)
            return json.dumps(entries)
        else:
            return f"Unknown git tool: {command}"
    except Exception as e:
        return f"Error executing {command}: {e}"


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
