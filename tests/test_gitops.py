"""Tests for GitOps engine — version control, snapshots, rollback.

Tests status, diff, add/commit, snapshot creation, rollback,
branch management, and sandbox tool integration.
"""

import json
import os
import tempfile

import pytest

from tektos.gitops import GitOpsEngine, execute_git_tool, GitSnapshot


# ─── Helpers ────────────────────────────────────────────────────────────────


def _create_test_repo() -> str:
    """Create a temporary git repository for testing."""
    tmpdir = tempfile.mkdtemp()
    os.system(f"cd {tmpdir} && git init -q")
    os.system(f"cd {tmpdir} && git config user.email 'test@test.com'")
    os.system(f"cd {tmpdir} && git config user.name 'Test User'")
    # Create initial commit
    with open(os.path.join(tmpdir, "README.md"), "w") as f:
        f.write("# Test Repo")
    os.system(f"cd {tmpdir} && git add README.md && git commit -q -m 'Initial commit'")
    return tmpdir


# ─── Status Tests ───────────────────────────────────────────────────────────


class TestGitStatus:
    def test_clean_repo_status(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            status = engine.get_status()
            assert status.branch == "master" or status.branch == "main"
            assert not status.dirty
            assert status.latest_commit_msg == "Initial commit"
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_dirty_repo_status(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            # Modify a file
            with open(os.path.join(path, "README.md"), "a") as f:
                f.write("\n# Modified")
            status = engine.get_status()
            assert status.dirty is True
            assert "README.md" in status.modified_files
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_untracked_files(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            # Create untracked file
            with open(os.path.join(path, "new_file.txt"), "w") as f:
                f.write("new content")
            status = engine.get_status()
            assert "new_file.txt" in status.untracked_files
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)


# ─── Diff Tests ─────────────────────────────────────────────────────────────


class TestGitDiff:
    def test_clean_diff_empty(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            diff = engine.get_diff()
            assert diff == [""]  # empty diff
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_modified_file_diff(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            with open(os.path.join(path, "README.md"), "a") as f:
                f.write("\n+ New line")
            diff = engine.get_diff()
            assert any("+ New line" in line for line in diff)
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)


# ─── Stage & Commit Tests ───────────────────────────────────────────────────


class TestGitStageAndCommit:
    def test_add_files(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            with open(os.path.join(path, "test.txt"), "w") as f:
                f.write("test")
            result = engine.add(["test.txt"])
            assert result is True
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_commit_changes(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            with open(os.path.join(path, "test.txt"), "w") as f:
                f.write("test content")
            engine.add(["test.txt"])
            commit = engine.commit("Add test file")
            assert commit is not None
            assert len(commit) >= 40  # full SHA

            # Verify in log
            log = engine.get_log(limit=5)
            assert any("Add test file" in c["message"] for c in log)
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_nothing_to_commit(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            commit = engine.commit("Nothing to do")
            assert commit is None
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)


# ─── Snapshot Tests ─────────────────────────────────────────────────────────


class TestSnapshots:
    def test_create_snapshot(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            with open(os.path.join(path, "snapshot_test.txt"), "w") as f:
                f.write("snapshot data")
            engine.add_all()
            snapshot = engine.create_snapshot("test-snapshot", "Test snapshot")
            assert snapshot is not None
            assert snapshot.name == "test-snapshot"
            assert snapshot.commit is not None
            assert len(engine.list_snapshots()) == 1
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_safety_snapshot(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            with open(os.path.join(path, "safety.txt"), "w") as f:
                f.write("safety data")
            engine.add_all()
            snapshot = engine.create_snapshot("safety-1", "Safety point", is_safety=True)
            assert snapshot is not None
            assert snapshot.is_safety is True
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_nothing_to_snapshot(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            snapshot = engine.create_snapshot("empty")
            assert snapshot is None
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)


# ─── Rollback Tests ─────────────────────────────────────────────────────────


class TestRollback:
    def test_rollback_to_snapshot(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)

            # Create first snapshot
            with open(os.path.join(path, "v1.txt"), "w") as f:
                f.write("version 1")
            engine.add_all()
            snap1 = engine.create_snapshot("v1", "Version 1")

            # Make more changes
            with open(os.path.join(path, "v2.txt"), "w") as f:
                f.write("version 2")
            engine.add_all()
            engine.commit("Version 2")

            # Rollback to v1 snapshot
            result = engine.rollback(snap1.commit)
            assert result is True
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_rollback_no_snapshots(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            result = engine.rollback()
            assert result is False
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)


# ─── Branch Management Tests ────────────────────────────────────────────────


class TestBranchManagement:
    def test_create_branch(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            result = engine.create_branch("feature/test")
            assert result is True
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_switch_branch(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            engine.create_branch("feature/test")
            result = engine.switch_branch("feature/test")
            assert result is True
            status = engine.get_status()
            assert status.branch == "feature/test"
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_delete_branch(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            engine.create_branch("feature/test")
            engine.switch_branch("master")
            result = engine.delete_branch("feature/test")
            assert result is True
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)


# ─── Log Tests ──────────────────────────────────────────────────────────────


class TestGitLog:
    def test_get_log(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            log = engine.get_log(limit=5)
            assert len(log) >= 1
            assert log[0]["message"] == "Initial commit"
            assert len(log[0]["hash"]) == 8
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)


# ─── Sandbox Tool Integration Tests ─────────────────────────────────────────


class TestGitTools:
    def test_git_status_tool(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            result = execute_git_tool(engine, "git_status", {})
            data = json.loads(result)
            assert "branch" in data
            assert "dirty" in data
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_git_commit_tool(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            with open(os.path.join(path, "tool_test.txt"), "w") as f:
                f.write("tool test")
            engine.add(["tool_test.txt"])
            result = execute_git_tool(engine, "git_commit", {"message": "Tool commit"})
            assert "Committed" in result
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_git_snapshot_tool(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            with open(os.path.join(path, "snap_tool.txt"), "w") as f:
                f.write("snap")
            engine.add(["snap_tool.txt"])
            result = execute_git_tool(engine, "git_snapshot", {"name": "tool-snap"})
            data = json.loads(result)
            assert data["name"] == "tool-snap"
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_git_rollback_tool(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            result = execute_git_tool(engine, "git_rollback", {})
            assert "No snapshots" in result
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_git_log_tool(self):
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)
            result = execute_git_tool(engine, "git_log", {"limit": 5})
            commits = json.loads(result)
            assert len(commits) >= 1
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)


# ─── Integration Tests ──────────────────────────────────────────────────────


class TestGitOpsIntegration:
    def test_full_lifecycle(self):
        """Complete gitops lifecycle: status → add → commit → snapshot → log → rollback."""
        path = _create_test_repo()
        try:
            engine = GitOpsEngine(path)

            # 1. Status
            status = engine.get_status()
            assert not status.dirty

            # 2. Make changes and commit
            with open(os.path.join(path, "feature.py"), "w") as f:
                f.write("# Feature code")
            engine.add(["feature.py"])
            commit = engine.commit("Add feature.py")
            assert commit is not None

            # 3. Log
            log = engine.get_log(limit=5)
            assert any("Add feature.py" in c["message"] for c in log)

            # 4. Make changes then snapshot
            with open(os.path.join(path, "checkpoint.py"), "w") as f:
                f.write("# checkpoint")
            engine.add(["checkpoint.py"])
            snapshot = engine.create_snapshot("feature-start", "Before feature work", is_safety=True)
            assert snapshot is not None

            # 5. Make another change
            with open(os.path.join(path, "feature2.py"), "w") as f:
                f.write("# More feature")
            engine.add(["feature2.py"])
            engine.commit("Add more feature")

            # 6. Rollback to snapshot
            result = engine.rollback(snapshot.commit)
            assert result is True
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)

    def test_event_bus_emits(self):
        path = _create_test_repo()
        try:
            received = []
            fake_bus = type("FakeBus", (), {"emit": lambda _, et, pl: received.append((et, pl))})()
            engine = GitOpsEngine(path, event_bus=fake_bus)

            with open(os.path.join(path, "event_test.txt"), "w") as f:
                f.write("event")
            engine.add(["event_test.txt"])
            engine.commit("Event test")

            # Should have received git.added and git.committed events
            event_types = [r[0] for r in received]
            assert "git.added" in event_types
            assert "git.committed" in event_types
        finally:
            import shutil
            shutil.rmtree(path, ignore_errors=True)
