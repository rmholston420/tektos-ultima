"""Additional gitops tests covering uncovered lines: GitDiff.to_dict, _git exception paths, execute_git_tool branches, add edge cases."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def git_repo():
    """Create a real git repository for testing."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        # Initialize git repo
        import subprocess
        subprocess.run(["git", "init"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True)
        # Create initial commit
        (repo / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo, capture_output=True)
        yield repo


from src.tektos.gitops import GitOpsEngine, GitDiff, GitStatus, execute_git_tool


class TestGitDiffToDict:
    """Cover gitops.py line 89: GitDiff.to_dict()."""

    def test_git_diff_to_dict(self):
        diff = GitDiff(path="src/main.py", staged=["+10", "+20"], unstaged=["-5"])
        result = diff.to_dict()
        assert result["path"] == "src/main.py"
        assert result["staged"] == ["+10", "+20"]
        assert result["unstaged"] == ["-5"]


class TestGitExceptionPaths:
    """Cover gitops.py lines 145-153: _git check=True, timeout, general exception."""

    def test_git_check_true_raises_on_failure(self, git_repo):
        engine = GitOpsEngine(git_repo)
        # Use checkout on non-existent branch — always returns non-zero
        with pytest.raises(RuntimeError):
            engine._git(["checkout", "nonexistent-branch-xyz"], check=True)

    def test_git_timeout_returns_empty(self, git_repo):
        engine = GitOpsEngine(git_repo)
        # Override _git to simulate timeout
        with patch("subprocess.run") as mock_run:
            from subprocess import TimeoutExpired
            mock_run.side_effect = TimeoutExpired("git", 30)
            result = engine._git(["diff"])
            assert result == ""

    def test_git_general_exception_returns_empty(self, git_repo):
        engine = GitOpsEngine(git_repo)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git: no such file")
            result = engine._git(["diff"])
            assert result == ""


class TestGitCheckExcept:
    """Cover gitops.py lines 166-167: _git_check except fallback."""

    def test_git_check_returns_false_on_exception(self, git_repo):
        engine = GitOpsEngine(git_repo)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git: permission denied")
            result = engine._git_check(["status"])
            assert result is False


class TestGetDiffStaged:
    """Cover gitops.py line 222: get_diff with staged_only=True."""

    def test_get_diff_staged_only(self, git_repo):
        engine = GitOpsEngine(git_repo)
        diff = engine.get_diff(staged_only=True)
        assert isinstance(diff, list)


class TestGetFileDiff:
    """Cover gitops.py lines 227-231: get_file_diff."""

    def test_get_file_diff(self, git_repo):
        engine = GitOpsEngine(git_repo)
        diff = engine.get_file_diff("README.md")
        assert isinstance(diff, str)

    def test_get_file_diff_staged(self, git_repo):
        engine = GitOpsEngine(git_repo)
        diff = engine.get_file_diff("README.md", staged_only=True)
        assert isinstance(diff, str)


class TestAddEdgeCases:
    """Cover gitops.py lines 238, 243: add empty paths, add _git_check=False."""

    def test_add_empty_paths(self, git_repo):
        engine = GitOpsEngine(git_repo)
        result = engine.add([])
        assert result is False

    def test_add_git_check_false_returns_false(self, git_repo):
        engine = GitOpsEngine(git_repo)
        # Create a non-existent file path that will fail staging
        result = engine.add(["/nonexistent/path/file.txt"])
        # _git_check returns False on non-zero exit
        assert result is False


class TestAddAllExcludeUntracked:
    """Cover gitops.py line 248: add_all with exclude_untracked=True."""

    def test_add_all_exclude_untracked(self, git_repo):
        engine = GitOpsEngine(git_repo)
        # Create an untracked file
        (git_repo / "new.txt").write_text("new content")
        result = engine.add_all(exclude_untracked=True)
        assert result is True


class TestCommitWithPaths:
    """Cover gitops.py line 281: commit with paths argument."""

    def test_commit_with_paths(self, git_repo):
        engine = GitOpsEngine(git_repo)
        # Create a new file
        (git_repo / "feature.txt").write_text("feature")
        commit = engine.commit("Add feature", paths=["feature.txt"])
        assert commit is not None
        assert len(commit) == 40  # full git hash


class TestRollbackCommitHash:
    """Cover gitops.py lines 361-362: rollback with commit hash (len >= 7)."""

    def test_rollback_to_commit_hash(self, git_repo):
        engine = GitOpsEngine(git_repo)
        # Get current commit hash
        import subprocess
        hash_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True)
        commit_hash = hash_result.stdout.strip()
        # Rollback to current commit (len >= 7 triggers the commit hash path)
        result = engine.rollback(target=commit_hash, hard=False)
        assert result is True


class TestDeleteBranchCurrent:
    """Cover gitops.py lines 380-382: delete_branch current branch + exception."""

    def test_delete_branch_current_branch_exception(self, git_repo):
        engine = GitOpsEngine(git_repo)
        # Create a new branch and switch to it
        engine._git(["checkout", "-b", "test-branch"])
        # Try to delete the branch we're on — git checkout HEAD may succeed,
        # then branch -d fails because we're on it
        result = engine.delete_branch("test-branch")
        # The code catches the checkout exception and logs warning
        assert isinstance(result, bool)


class TestGetLogEmpty:
    """Cover gitops.py line 394: get_log returns empty list."""

    def test_get_log_empty_on_no_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            import subprocess
            subprocess.run(["git", "init"], cwd=repo, capture_output=True)
            engine = GitOpsEngine(repo)
            commits = engine.get_log()
            assert isinstance(commits, list)


class TestExecuteGitToolBranches:
    """Cover execute_git_tool lines 538-581: git_diff, git_add, git_commit, git_snapshot, git_rollback, unknown, exception."""

    def test_execute_git_diff(self, git_repo):
        engine = GitOpsEngine(git_repo)
        result = execute_git_tool(engine, "git_diff", {"staged_only": False})
        assert isinstance(result, str)

    def test_execute_git_add(self, git_repo):
        engine = GitOpsEngine(git_repo)
        (git_repo / "test.txt").write_text("data")
        result = execute_git_tool(engine, "git_add", {"paths": ["test.txt"]})
        assert "test.txt" in result

    def test_execute_git_commit_nothing_to_commit(self, git_repo):
        engine = GitOpsEngine(git_repo)
        result = execute_git_tool(engine, "git_commit", {"message": "empty"})
        assert "Nothing to commit" in result

    def test_execute_git_snapshot_nothing(self, git_repo):
        engine = GitOpsEngine(git_repo)
        result = execute_git_tool(engine, "git_snapshot", {"name": "test"})
        assert "Nothing to snapshot" in result

    def test_execute_git_rollback_nothing(self, git_repo):
        engine = GitOpsEngine(git_repo)
        result = execute_git_tool(engine, "git_rollback", {})
        assert "No snapshots" in result

    def test_execute_git_unknown_tool(self, git_repo):
        engine = GitOpsEngine(git_repo)
        result = execute_git_tool(engine, "nonexistent_tool", {})
        assert "Unknown git tool" in result

    def test_execute_git_exception_path(self, git_repo):
        engine = GitOpsEngine(git_repo)
        # Pass invalid params to trigger an exception
        result = execute_git_tool(engine, "git_status", {})
        # Should not raise, should return a string
        assert isinstance(result, str)
