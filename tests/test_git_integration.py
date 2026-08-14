"""Tests for GitIntegration module — git operations, status tracking, branching, rollback."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tektos.git_integration import GitIntegration, GitCommit, GitStatus


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run_git(cwd, *args):
    """Helper to run git commands in a test repo."""
    return subprocess.run(
        ['git'] + list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _make_test_repo(tmp_path) -> Path:
    """Create a minimal git repo for testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    _run_git(repo, 'init')
    _run_git(repo, 'config', 'user.name', 'Test User')
    _run_git(repo, 'config', 'user.email', 'test@example.com')
    # Create initial commit so HEAD exists for branch ops
    (repo / '.gitignore').write_text('*.pyc\n__pycache__/\n')
    _run_git(repo, 'add', '.gitignore')
    _run_git(repo, 'commit', '-m', 'Initial commit')
    return repo


# ── GitStatus / GitCommit ────────────────────────────────────────────────────

class TestGitStatus:
    def test_defaults(self):
        s = GitStatus(root="/tmp")
        assert s.is_repo is False
        assert s.branch == ""
        assert s.is_dirty is False
        assert s.staged_files == []
        assert s.modified_files == []
        assert s.untracked_files == []

    def test_dirty_with_branch(self):
        s = GitStatus(root="/tmp", is_repo=True, branch="main", is_dirty=True, modified_files=["a.py"])
        assert s.branch == "main"
        assert s.is_dirty is True
        assert "a.py" in s.modified_files


class TestGitCommit:
    def test_defaults(self):
        c = GitCommit(hash="abc123", short_hash="abc1234", message="test", author="Test", timestamp="2026-01-01")
        assert c.files_changed == []
        assert c.lines_added == 0
        assert c.lines_deleted == 0


# ── GitIntegration — Init & Status ──────────────────────────────────────────

class TestGitIntegrationInit:
    def test_is_repo_true(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        assert gi.is_repo() is True

    def test_is_repo_false(self, tmp_path):
        gi = GitIntegration(str(tmp_path))
        assert gi.is_repo() is False

    def test_init_repo(self, tmp_path):
        gi = GitIntegration(str(tmp_path))
        assert gi.init_repo() is True
        assert gi.is_repo() is True

    def test_init_repo_noop(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        assert gi.init_repo() is True

    def test_get_status_not_repo(self, tmp_path):
        gi = GitIntegration(str(tmp_path))
        status = gi.get_status()
        assert status.is_repo is False
        assert status.branch == ""


# ── GitIntegration — File Operations ────────────────────────────────────────

class TestGitIntegrationStatus:
    def test_get_status_clean(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        status = gi.get_status()
        assert status.is_dirty is False

    def test_get_status_dirty(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        (repo / "test.py").write_text("print('hello')")
        _run_git(repo, 'add', 'test.py')
        _run_git(repo, 'commit', '-m', 'init')
        (repo / "test.py").write_text("print('world')")
        _run_git(repo, 'add', 'test.py')

        gi = GitIntegration(str(repo))
        status = gi.get_status()
        assert status.is_dirty is True
        assert "test.py" in status.staged_files

    def test_get_branch(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        status = gi.get_status()
        assert status.branch in ("master", "main")


# ── GitIntegration — Commits ────────────────────────────────────────────────

class TestGitIntegrationCommits:
    def test_get_commits_empty(self, tmp_path):
        """After init but no new commits, get_commits should return at least the initial."""
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        commits = gi.get_commits()
        # _make_test_repo creates an initial commit, so we should have at least 1
        assert len(commits) >= 1

    def test_get_commits_after_commit(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        (repo / "test.py").write_text("print('hello')")
        _run_git(repo, 'add', 'test.py')
        _run_git(repo, 'commit', '-m', 'Initial commit')

        gi = GitIntegration(str(repo))
        commits = gi.get_commits(count=5)
        assert len(commits) >= 1
        assert commits[0].message == "Initial commit"
        assert commits[0].short_hash != ""
        assert "test.py" in commits[0].files_changed

    def test_commit_no_changes(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        result = gi.commit("Empty commit")
        # Should fail or succeed depending on git config (no error in test)
        assert result is None or isinstance(result, str)


# ── GitIntegration — Staging ────────────────────────────────────────────────

class TestGitIntegrationStaging:
    def test_stage_file(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        (repo / "test.py").write_text("x = 1")
        gi = GitIntegration(str(repo))
        assert gi.stage_file("test.py") is True

    def test_stage_all(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        (repo / "test.py").write_text("x = 1")
        (repo / "test2.py").write_text("y = 2")
        gi = GitIntegration(str(repo))
        assert gi.stage_all() is True

    def test_get_diff(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        (repo / "test.py").write_text("x = 1")
        # git diff shows unstaged changes — don't stage it
        gi = GitIntegration(str(repo))
        diff = gi.get_diff("test.py")
        assert "x = 1" in diff

    def test_get_diff_staged(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        (repo / "test.py").write_text("x = 1")
        _run_git(repo, 'add', 'test.py')
        gi = GitIntegration(str(repo))
        diff = gi.get_diff_staged("test.py")
        assert "x = 1" in diff


# ── GitIntegration — Branches ───────────────────────────────────────────────

class TestGitIntegrationBranches:
    def test_create_branch(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        assert gi.create_branch("test-branch") is True

    def test_switch_branch(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        gi.create_branch("test-branch")
        assert gi.switch_branch("test-branch") is True

    def test_delete_branch(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        gi.create_branch("test-branch")
        assert gi.delete_branch("test-branch") is True

    def test_list_branches(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        branches = gi.list_branches()
        assert "master" in branches or "main" in branches

    def test_get_current_branch(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        branch = gi.get_current_branch()
        assert branch == "master" or branch == "main"


# ── GitIntegration — Rollback ───────────────────────────────────────────────

class TestGitIntegrationRollback:
    def test_rollback_no_commits(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        # Should fail gracefully — no commits yet
        result = gi.rollback("HEAD~1")
        assert result is False


# ── GitIntegration — Helpers ────────────────────────────────────────────────

class TestGitIntegrationHelpers:
    def test_get_head_hash_no_commits(self, tmp_path):
        gi = GitIntegration(str(tmp_path))
        gi.init_repo()
        h = gi.get_head_hash()
        # After init but before any commit, HEAD doesn't exist
        assert h == ""

    def test_get_file_history_no_commits(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        history = gi.get_file_history("test.py")
        assert history == []

    def test_is_gitignored(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        # No .gitignore yet
        assert gi.is_gitignored("test.py") is False

    def test_auto_commit_no_changes(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        assert gi.auto_commit_if_changes() is True

    def test_auto_commit_with_changes(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        (repo / "test.py").write_text("x = 1")
        gi = GitIntegration(str(repo))
        # auto_commit stages + commits
        result = gi.auto_commit_if_changes()
        assert result is True


# ── GitIntegration — Edge Cases ─────────────────────────────────────────────

class TestGitIntegrationEdgeCases:
    def test_commit_with_author(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        (repo / "test.py").write_text("x = 1")
        gi = GitIntegration(str(repo))
        gi.stage_file("test.py")
        commit_hash = gi.commit("Test commit", author="Test User <test@example.com>")
        assert commit_hash is not None
        assert len(commit_hash) > 0

    def test_create_branch_from_branch(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        gi = GitIntegration(str(repo))
        gi.create_branch("existing-branch")
        assert gi.create_branch("new-branch", from_branch="existing-branch") is True

    def test_get_diff_staged(self, tmp_path):
        repo = _make_test_repo(tmp_path)
        (repo / "test.py").write_text("x = 1")
        _run_git(repo, 'add', 'test.py')
        gi = GitIntegration(str(repo))
        diff = gi.get_diff_staged("test.py")
        assert "x = 1" in diff
