"""Git integration module for Tektos.

Provides version control operations for the codebase:
- Automatic commit tracking of code changes
- Branch management for self-modification experiments
- Diff analysis for blast-radius reporting
- Rollback support for failed self-modification cycles
- Status tracking for the current state

Design:
- Lightweight git operations wrapper
- Auto-commit on file changes during sessions
- Branch-per-experiment pattern for safe self-modification
- Integrates with repograph for affected-file detection
- Tektos-native: emits events for git operations
"""

from __future__ import annotations

import re
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Match 40-character hex commit hashes at line start
_HASH_RE = re.compile(r'^[0-9a-f]{40}\|')


@dataclass
class GitStatus:
    """Current status of a git repository."""
    root: str
    is_repo: bool = False
    branch: str = ""
    is_dirty: bool = False
    staged_files: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    ahead_behind: dict[str, int] = field(default_factory=dict)


@dataclass
class GitCommit:
    """A git commit with metadata."""
    hash: str
    short_hash: str
    message: str
    author: str
    timestamp: str
    files_changed: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_deleted: int = 0


class GitIntegration:
    """Git operations for Tektos codebase management."""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)

    def init_repo(self) -> bool:
        """Initialize git repo if not already initialized."""
        if self.is_repo():
            return True
        try:
            subprocess.run(
                ['git', 'init'],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            log.info(f"Initialized git repo at {self.repo_root}")
            return True
        except Exception as e:
            log.error(f"Failed to init git repo: {e}")
            return False

    def is_repo(self) -> bool:
        """Check if path is a git repository."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--is-inside-work-tree'],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0 and 'true' in result.stdout
        except Exception:
            return False

    def get_status(self) -> GitStatus:
        """Get current git status."""
        status = GitStatus(root=str(self.repo_root))

        if not self.is_repo():
            return status

        try:
            # Check if dirty
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            status.is_dirty = bool(result.stdout.strip())

            # Parse status output
            for line in result.stdout.split('\n'):
                if not line:
                    continue
                status_code = line[:2]
                filepath = line[3:]

                if status_code[0] == ' ':
                    # Work tree only changes (second char is M/D/U/R/C)
                    if len(status_code) >= 2 and status_code[1] in ('M', 'D', 'U', 'R', 'C'):
                        status.modified_files.append(filepath)
                elif status_code.startswith('A') or status_code.startswith('M'):
                    status.staged_files.append(filepath)
                elif status_code.startswith('??'):
                    status.untracked_files.append(filepath)

            # Get current branch
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            status.branch = result.stdout.strip() if result.returncode == 0 else ""

        except Exception as e:
            log.error(f"Failed to get git status: {e}")

        return status

    def get_commits(self, count: int = 10, since: str | None = None) -> list[GitCommit]:
        """Get recent commits."""
        commits = []
        try:
            cmd = ['git', 'log', f'-n{count}', '--format=%H|%h|%s|%an|%aI', '--numstat']
            if since:
                cmd.insert(3, f'--since={since}')

            result = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return commits

            current_commit = None
            for line in result.stdout.split('\n'):
                if _HASH_RE.match(line):
                    # format output starts directly with the hash
                    parts = line.split('|')
                    if len(parts) >= 5:
                        current_commit = GitCommit(
                            hash=parts[0],
                            short_hash=parts[1],
                            message=parts[2],
                            author=parts[3],
                            timestamp=parts[4],
                        )
                        commits.append(current_commit)
                elif current_commit and line.strip():
                    parts = line.split()
                    if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                        current_commit.files_changed.append(parts[2])
                        current_commit.lines_added += int(parts[0])
                        current_commit.lines_deleted += int(parts[1])

        except Exception as e:
            log.error(f"Failed to get commits: {e}")

        return commits

    def get_diff(self, file_path: str | None = None) -> str:
        """Get diff for a file or all changes.

        Shows both unstaged changes and new untracked files.
        """
        try:
            # For untracked files, git diff won't show them
            # We need to check if file exists and is untracked
            if file_path:
                fp = self.repo_root / file_path
                if fp.exists() and not self.is_gitignored(file_path):
                    # Check if tracked
                    check = subprocess.run(
                        ['git', 'ls-files', '--error-unmatch', file_path],
                        cwd=str(self.repo_root),
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if check.returncode != 0:
                        # File is untracked — show as new file
                        with open(fp, 'r', errors='replace') as f:
                            content = f.read()
                        return f"--- /dev/null\n+++ b/{file_path}\n@@ -0,0 +1 @@\n+{content.rstrip()}\n"

            cmd = ['git', 'diff']
            if file_path:
                cmd.extend(['--', file_path])

            result = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception as e:
            log.error(f"Failed to get diff: {e}")
            return ""

    def get_diff_staged(self, file_path: str | None = None) -> str:
        """Get diff for staged changes."""
        try:
            cmd = ['git', 'diff', '--cached']
            if file_path:
                cmd.extend(['--', file_path])

            result = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception as e:
            log.error(f"Failed to get staged diff: {e}")
            return ""

    def stage_file(self, file_path: str) -> bool:
        """Stage a file for commit."""
        try:
            subprocess.run(
                ['git', 'add', file_path],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return True
        except Exception as e:
            log.error(f"Failed to stage file: {e}")
            return False

    def stage_all(self) -> bool:
        """Stage all changes."""
        try:
            subprocess.run(
                ['git', 'add', '-A'],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return True
        except Exception as e:
            log.error(f"Failed to stage all: {e}")
            return False

    def commit(
        self,
        message: str,
        author: str | None = None,
    ) -> str | None:
        """Create a commit."""
        try:
            cmd = ['git', 'commit', '-m', message]
            if author:
                # Set git config temporarily
                subprocess.run(
                    ['git', 'config', 'user.name', author.split('<')[0].strip()],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                subprocess.run(
                    ['git', 'config', 'user.email', author.split('<')[1].rstrip('>')],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

            result = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return self._get_head_hash()
            else:
                log.warning(f"Commit failed: {result.stderr}")
                return None
        except Exception as e:
            log.error(f"Failed to commit: {e}")
            return None

    def create_branch(self, branch_name: str, from_branch: str | None = None) -> bool:
        """Create a new branch."""
        try:
            cmd = ['git', 'branch']
            if from_branch:
                cmd.extend([branch_name, from_branch])
            else:
                cmd.append(branch_name)

            result = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            log.error(f"Failed to create branch: {e}")
            return False

    def switch_branch(self, branch_name: str) -> bool:
        """Switch to a branch."""
        try:
            result = subprocess.run(
                ['git', 'checkout', branch_name],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            log.error(f"Failed to switch branch: {e}")
            return False

    def delete_branch(self, branch_name: str) -> bool:
        """Delete a branch."""
        try:
            result = subprocess.run(
                ['git', 'branch', '-D', branch_name],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            log.error(f"Failed to delete branch: {e}")
            return False

    def get_current_branch(self) -> str:
        """Get current branch name."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    def rollback(self, commit_hash: str | None = None, soft: bool = False) -> bool:
        """Rollback to a specific commit."""
        target = commit_hash or 'HEAD~1'
        try:
            cmd = ['git', 'reset', '--soft' if soft else '--hard', target]
            result = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            log.error(f"Failed to rollback: {e}")
            return False

    def list_branches(self) -> list[str]:
        """List all branches."""
        try:
            result = subprocess.run(
                ['git', 'branch', '--list'],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return [b.strip().lstrip('* ') for b in result.stdout.strip().split('\n') if b.strip()]
        except Exception:
            return []

    def is_gitignored(self, file_path: str) -> bool:
        """Check if file is gitignored."""
        try:
            result = subprocess.run(
                ['git', 'check-ignore', file_path],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_head_hash(self) -> str:
        """Get current HEAD hash."""
        return self._get_head_hash()

    def _get_head_hash(self) -> str:
        """Internal: get HEAD hash."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    def get_file_history(self, file_path: str, limit: int = 10) -> list[str]:
        """Get commit history for a file."""
        try:
            result = subprocess.run(
                ['git', 'log', f'-n{limit}', '--format=%h %s', '--', file_path],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return [line for line in result.stdout.strip().split('\n') if line] if result.returncode == 0 else []
        except Exception:
            return []

    def auto_commit_if_changes(self, message: str | None = None) -> bool:
        """Auto-commit if there are changes (useful for self-modification cycles)."""
        status = self.get_status()
        if not status.is_dirty:
            log.info("No changes to commit")
            return True

        if not message:
            message = f"Tektos auto-commit at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"

        # Stage all changes
        self.stage_all()

        # Create commit
        commit_hash = self.commit(message)
        if commit_hash:
            log.info(f"Auto-committed: {commit_hash[:8]}")
            return True
        else:
            log.warning("Auto-commit failed")
            return False
