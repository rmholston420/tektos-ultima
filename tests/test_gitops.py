"""Tests for gitops.py — GitOpsEngine, GitStatus, GitDiff, GitSnapshot."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from tektos.gitops import (
    GitDiff,
    GitOpsEngine,
    GitSnapshot,
    GitStatus,
)


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True, check=True)
    return repo


@pytest.fixture
def engine(git_repo):
    """Create a GitOpsEngine pointing at the test repo."""
    return GitOpsEngine(repo_path=git_repo)


class TestGitStatus:
    """Tests for GitStatus dataclass."""

    def test_create_status(self):
        status = GitStatus(
            path="/tmp/repo",
            branch="main",
            dirty=False,
            staged_files=["a.py"],
            modified_files=["b.py"],
            untracked_files=["c.py"],
            ahead=1,
            behind=0,
            latest_commit="abc123",
            latest_commit_msg="test commit",
        )
        assert status.path == "/tmp/repo"
        assert status.branch == "main"
        assert status.dirty is False

    def test_to_dict(self):
        status = GitStatus(
            path="/tmp/repo",
            branch="main",
            dirty=True,
            staged_files=["a.py"],
            modified_files=["b.py"],
            untracked_files=["c.py"],
            ahead=1,
            behind=0,
            latest_commit="abc123",
            latest_commit_msg="test commit",
        )
        d = status.to_dict()
        assert d["path"] == "/tmp/repo"
        assert d["dirty"] is True
        assert d["staged_files"] == ["a.py"]
        assert d["ahead"] == 1


class TestGitDiff:
    """Tests for GitDiff dataclass."""

    def test_create_diff(self):
        diff = GitDiff(
            path="/tmp/repo",
            staged=["a.py"],
            unstaged=["b.py"],
        )
        assert diff.path == "/tmp/repo"
        assert diff.staged == ["a.py"]

    def test_to_dict(self):
        diff = GitDiff(
            path="/tmp/repo",
            staged=["a.py"],
            unstaged=["b.py"],
        )
        d = diff.to_dict()
        assert d["staged"] == ["a.py"]
        assert d["unstaged"] == ["b.py"]


class TestGitSnapshot:
    """Tests for GitSnapshot dataclass."""

    def test_create_snapshot(self):
        snap = GitSnapshot(
            name="before-change",
            commit="abc123",
            branch="main",
            message="Safety snapshot",
            timestamp="2026-01-01T00:00:00Z",
            is_safety=True,
        )
        assert snap.name == "before-change"
        assert snap.is_safety is True

    def test_to_dict(self):
        snap = GitSnapshot(
            name="snap-1",
            commit="abc123",
            branch="main",
            message="test",
            timestamp="2026-01-01T00:00:00Z",
        )
        d = snap.to_dict()
        assert d["name"] == "snap-1"
        assert d["is_safety"] is False


class TestGitOpsEngine:
    """Tests for GitOpsEngine."""

    def test_init(self, git_repo):
        engine = GitOpsEngine(repo_path=git_repo)
        assert engine.repo_path == git_repo.resolve()
        assert engine._snapshot_log == []

    def test_get_status_clean_repo(self, engine, git_repo):
        status = engine.get_status()
        # Branch may be "HEAD" (detached) or "master"/"main"
        assert status.dirty is False
        assert status.staged_files == []
        assert status.modified_files == []

    def test_add_and_commit(self, engine, git_repo):
        # Create a file
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")

        assert engine.add(["test.txt"]) is True
        commit_hash = engine.commit("Add test.txt")
        assert commit_hash is not None
        assert len(commit_hash) > 0

    def test_add_all(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")

        assert engine.add_all() is True

    def test_commit_no_changes(self, engine):
        result = engine.commit("empty commit")
        assert result is None

    def test_get_diff(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add(["test.txt"])
        engine.commit("Add test.txt")

        # Modify the file
        test_file.write_text("world")
        diff = engine.get_diff()
        assert isinstance(diff, list)

    def test_get_file_diff(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add(["test.txt"])
        engine.commit("Add test.txt")

        test_file.write_text("world")
        diff = engine.get_file_diff("test.txt")
        assert "world" in diff or "hello" in diff

    def test_create_snapshot(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add_all()
        engine.commit("Add test.txt")

        # Modify the file to have changes to snapshot
        test_file.write_text("world")

        snap = engine.create_snapshot("before-change", "Safety snapshot")
        assert snap is not None
        assert snap.name == "before-change"
        assert snap.is_safety is False

    def test_create_snapshot_no_changes(self, engine):
        snap = engine.create_snapshot("empty")
        assert snap is None

    def test_list_snapshots(self, engine, git_repo):
        assert engine.list_snapshots() == []

        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add_all()
        engine.commit("Add test.txt")

        # Modify to have changes to snapshot
        test_file.write_text("world")
        engine.create_snapshot("snap-1")

        snaps = engine.list_snapshots()
        assert len(snaps) == 1
        assert snaps[0].name == "snap-1"

    def test_rollback_no_snapshots(self, engine):
        assert engine.rollback() is False

    def test_create_branch(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add_all()
        engine.commit("Add test.txt")

        assert engine.create_branch("feature-1") is True

    def test_switch_branch(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add_all()
        engine.commit("Add test.txt")

        engine.create_branch("feature-1")
        assert engine.switch_branch("feature-1") is True

    def test_delete_branch(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add_all()
        engine.commit("Add test.txt")

        engine.create_branch("feature-1")
        # Switch back to master before deleting
        engine.switch_branch("master")
        assert engine.delete_branch("feature-1") is True

    def test_get_log(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add_all()
        engine.commit("Add test.txt")

        log = engine.get_log(limit=5)
        assert len(log) >= 1
        assert log[0]["message"] == "Add test.txt"
        assert "hash" in log[0]
        assert "author" in log[0]
        assert "date" in log[0]

    def test_get_log_empty(self, engine):
        log = engine.get_log()
        assert log == []

    def test_get_status_dirty(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add_all()
        engine.commit("Add test.txt")

        test_file.write_text("world")
        status = engine.get_status()
        assert status.dirty is True

    def test_get_status_untracked(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add_all()
        engine.commit("Add test.txt")

        untracked = git_repo / "new.txt"
        untracked.write_text("new")
        status = engine.get_status()
        assert "new.txt" in status.untracked_files

    def test_commit_with_paths(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")

        commit_hash = engine.commit("Add test.txt", paths=["test.txt"])
        assert commit_hash is not None

    def test_rollback_to_commit(self, engine, git_repo):
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add_all()
        engine.commit("Add test.txt")

        commit_hash = engine._git(["rev-parse", "HEAD"])
        assert engine.rollback(target=commit_hash, hard=False) is True

    def test_event_emission(self, git_repo):
        """Test that events are emitted via event bus."""
        mock_bus = {"events": []}

        class MockBus:
            def emit(self, event_type, payload):
                mock_bus["events"].append((event_type, payload))

        engine = GitOpsEngine(repo_path=git_repo, event_bus=MockBus())
        test_file = git_repo / "test.txt"
        test_file.write_text("hello")
        engine.add_all()
        engine.commit("Add test.txt")

        assert len(mock_bus["events"]) > 0
        assert any("committed" in e[0] for e in mock_bus["events"])
