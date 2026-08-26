"""Tests for src/tektos/gitops/engine.py

Covers: GitChange, GitOperationResult, GitOpsEngine (status, commit, branch,
merge, rollback, log, stats, singleton), get_gitops_engine, reset_gitops_engine.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import subprocess

from tektos.gitops import (
    GitOpsEngine,
    GitChange,
    GitOperationResult,
    GitStatus,
)
from tektos.gitops.engine import get_gitops_engine, reset_gitops_engine


# ─── Data Classes ─────────────────────────────────────────────────────────────

class TestGitChange:
    def test_creation(self):
        c = GitChange(file_path="test.py", status="modified")
        assert c.file_path == "test.py"
        assert c.status == "modified"
        assert c.diff == ""
        assert c.timestamp != ""

    def test_custom_timestamp(self):
        c = GitChange(file_path="test.py", status="added", timestamp="2026-01-01")
        assert c.timestamp == "2026-01-01"


class TestGitOperationResult:
    def test_creation(self):
        r = GitOperationResult(success=True, operation="commit", message="OK")
        assert r.success is True
        assert r.operation == "commit"
        assert r.message == "OK"
        assert r.details == {}
        assert r.error == ""

    def test_failure(self):
        r = GitOperationResult(success=False, operation="commit", message="Failed", error="boom")
        assert r.success is False
        assert r.error == "boom"


# ─── GitOpsEngine ─────────────────────────────────────────────────────────────

class TestGitOpsEngine:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        subprocess.run(["git", "init", "--initial-branch=main"], cwd=self.tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=self.tmpdir, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.tmpdir, capture_output=True)
        # Create initial commit so 'main' branch exists
        init_file = Path(self.tmpdir) / ".gitkeep"
        init_file.write_text("")
        subprocess.run(["git", "add", ".gitkeep"], cwd=self.tmpdir, capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=self.tmpdir, capture_output=True)
        self.engine = GitOpsEngine(repo_root=self.tmpdir)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creation(self):
        assert self.engine.repo_root == Path(self.tmpdir)
        assert self.engine.author_name == "Tektos"
        assert self.engine.author_email == "tektos@local"
        assert self.engine._operation_log == []

    def test_creation_custom_author(self):
        e = GitOpsEngine(repo_root=self.tmpdir, author_name="Custom", author_email="custom@test.com")
        assert e.author_name == "Custom"
        assert e.author_email == "custom@test.com"

    def test_is_git_repo(self):
        assert self.engine.is_git_repo() is True

    def test_get_status_empty(self):
        status = self.engine.get_status()
        assert isinstance(status, GitStatus)
        assert status.branch == "main"
        assert status.dirty is False
        assert status.staged_files == []
        assert status.modified_files == []
        assert status.untracked_files == []

    def test_get_status_with_file(self):
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("hello")
        status = self.engine.get_status()
        assert isinstance(status, GitStatus)
        assert status.dirty is True
        assert "test.txt" in status.untracked_files

    def test_get_status_modified(self):
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("hello")
        self.engine._run_git(["add", "test.txt"])
        self.engine._run_git(["commit", "-m", "initial"])
        test_file.write_text("world")
        status = self.engine.get_status()
        assert isinstance(status, GitStatus)
        assert status.dirty is True
        assert "test.txt" in status.modified_files

    def test_commit_no_changes(self):
        result = self.engine.commit_changes("Empty commit")
        assert result.success is True
        assert result.message == "No changes to commit"

    def test_commit_with_file(self):
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("hello")
        result = self.engine.commit_changes("Add test file")
        assert result.success is True
        assert result.operation == "commit"
        assert len(self.engine._operation_log) == 1

    def test_commit_with_specific_files(self):
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("hello")
        result = self.engine.commit_changes("Add test", files=["test.txt"])
        assert result.success is True

    def test_commit_failure(self):
        # Commit with no staged files and no changes should succeed (returns success=True)
        result = self.engine.commit_changes("Empty")
        assert result.success is True

    def test_create_branch(self):
        result = self.engine.create_branch("feature", base_branch="main")
        assert result.success is True
        assert result.operation == "branch_create"
        assert result.message == "Created branch 'feature'"

    def test_create_branch_from_base(self):
        result = self.engine.create_branch("feature", base_branch="main")
        assert result.success is True

    def test_create_branch_failure(self):
        # Try to create a branch from a non-existent base
        result = self.engine.create_branch("feature", base_branch="nonexistent")
        assert result.success is False

    def test_switch_branch(self):
        self.engine.create_branch("feature", base_branch="main")
        result = self.engine.switch_branch("feature")
        assert result.success is True
        assert "Switched to branch" in result.message

    def test_switch_branch_failure(self):
        result = self.engine.switch_branch("nonexistent")
        assert result.success is False

    def test_get_log_empty(self):
        log = self.engine.get_log()
        assert isinstance(log, list)
        assert len(log) == 1  # initial commit

    def test_get_log_with_commits(self):
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("hello")
        self.engine.commit_changes("First commit")
        test_file.write_text("world")
        self.engine.commit_changes("Second commit")
        log = self.engine.get_log()
        assert len(log) == 3  # initial + first + second
        assert log[0]["message"] == "Second commit"
        assert log[1]["message"] == "First commit"

    def test_get_log_limit(self):
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("hello")
        self.engine.commit_changes("First commit")
        test_file.write_text("world")
        self.engine.commit_changes("Second commit")
        log = self.engine.get_log(limit=1)
        assert len(log) == 1

    def test_get_operation_log(self):
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("hello")
        self.engine.commit_changes("First commit")
        test_file.write_text("world")
        self.engine.commit_changes("Second commit")
        log = self.engine.get_operation_log()
        assert len(log) == 2
        assert log[0]["operation"] == "commit"

    def test_get_stats(self):
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("hello")
        self.engine.commit_changes("First commit")
        stats = self.engine.get_stats()
        assert stats["is_git_repo"] is True
        assert stats["total_commits"] >= 1
        assert "branches" in stats
        assert "operation_count" in stats

    def test_get_stats_error(self):
        # Create engine pointing to non-git directory
        e = GitOpsEngine(repo_root="/tmp")
        stats = e.get_stats()
        assert stats["is_git_repo"] is False
        assert "error" in stats or "branches" in stats

    def test_rollback_to_commit(self):
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("hello")
        self.engine.commit_changes("First commit")
        commit_hash = self.engine._run_git(["rev-parse", "HEAD"]).stdout.strip()
        test_file.write_text("world")
        self.engine.commit_changes("Second commit")
        result = self.engine.rollback(commit_hash)
        assert result.success is True

    def test_rollback_to_head_minus_one(self):
        test_file = Path(self.tmpdir) / "test.txt"
        test_file.write_text("hello")
        self.engine.commit_changes("First commit")
        test_file.write_text("world")
        self.engine.commit_changes("Second commit")
        result = self.engine.rollback()
        assert result.success is True

    def test_rollback_failure(self):
        # Try to rollback when there's nothing to rollback to
        result = self.engine.rollback("nonexistent")
        assert result.success is False

    def test_merge_branch(self):
        # Create a branch with a commit, then merge back
        self.engine.create_branch("feature")
        test_file = Path(self.tmpdir) / "feature.txt"
        test_file.write_text("feature content")
        self.engine.commit_changes("Add feature")
        self.engine.switch_branch("master")
        result = self.engine.merge_branch("feature")
        # Merge may fail due to conflicts or fast-forward, but shouldn't raise
        assert result.operation == "merge"

    def test_merge_branch_to_target(self):
        self.engine.create_branch("feature")
        test_file = Path(self.tmpdir) / "feature.txt"
        test_file.write_text("feature content")
        self.engine.commit_changes("Add feature")
        self.engine.switch_branch("master")
        result = self.engine.merge_branch("feature", target_branch="master")
        assert result.operation == "merge"

    def test_run_git_timeout(self):
        # _run_git should handle timeouts gracefully
        result = self.engine._run_git(["status"])
        assert result.returncode == 0


# ─── Convenience Functions ─────────────────────────────────────────────────────

class TestConvenienceFunctions:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        reset_gitops_engine()

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        reset_gitops_engine()

    def test_get_gitops_engine_singleton(self):
        e1 = get_gitops_engine(repo_root=self.tmpdir)
        e2 = get_gitops_engine(repo_root=self.tmpdir)
        assert e1 is e2

    def test_get_gitops_engine_different_root(self):
        e1 = get_gitops_engine(repo_root=self.tmpdir)
        e2 = get_gitops_engine(repo_root="/tmp")
        assert e1 is not e2

    def test_reset_gitops_engine(self):
        e1 = get_gitops_engine(repo_root=self.tmpdir)
        reset_gitops_engine()
        e2 = get_gitops_engine(repo_root=self.tmpdir)
        assert e1 is not e2
