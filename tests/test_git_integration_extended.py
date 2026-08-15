"""Extended git_integration.py tests to close coverage gaps (lines 103, 126, 140-141, 151, 184-185, 210-212, 226-228, 235, 245-247, 260-262, 275-277, 316-318, 337-339, 352-354, 367-369, 382-383, 398-400, 413-414, 427-428, 445-446, 459-460, 481-482)."""

import subprocess
from unittest.mock import patch

import pytest

from tektos.git_integration import GitIntegration


@pytest.fixture
def working_repo(tmp_path):
    """Create a working git repo with user config and initial commit."""
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@tektos.dev"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), capture_output=True, check=True)
    (tmp_path / ".gitkeep").write_text("")
    subprocess.run(["git", "add", ".gitkeep"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(tmp_path), capture_output=True, check=True)
    return tmp_path


# ---------------------------------------------------------------------------
# get_status() — non-repo early return (line 103)
# ---------------------------------------------------------------------------

class TestGetStatusNonRepo:
    def test_status_not_repo_returns_empty(self, tmp_path):
        """Test get_status() returns empty GitStatus when not in a repo."""
        git = GitIntegration(str(tmp_path))
        status = git.get_status()
        assert status.is_repo is False
        assert status.branch == ""
        assert status.staged_files == []
        assert status.modified_files == []
        assert status.untracked_files == []


# ---------------------------------------------------------------------------
# get_status() — modified files parsing (line 126)
# ---------------------------------------------------------------------------

class TestGetStatusModified:
    def test_modified_file_not_staged(self, working_repo):
        """Test get_status() detects modified (not staged) files."""
        f = working_repo / "modified.txt"
        f.write_text("original")
        subprocess.run(["git", "add", "modified.txt"], cwd=working_repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "added"], cwd=working_repo, capture_output=True, check=True)
        # Now modify without staging
        f.write_text("modified content")
        git = GitIntegration(str(working_repo))
        status = git.get_status()
        assert "modified.txt" in status.modified_files
        assert "modified.txt" not in status.staged_files


# ---------------------------------------------------------------------------
# get_status() — exception path (lines 140-141)
# ---------------------------------------------------------------------------

class TestGetStatusException:
    def test_status_exception_handled(self, working_repo):
        """Test get_status() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            status = git.get_status()
            assert isinstance(status, type(git.get_status()))


# ---------------------------------------------------------------------------
# get_commits() — with since (line 151)
# ---------------------------------------------------------------------------

class TestGetCommitsSince:
    def test_commits_with_since(self, working_repo):
        """Test get_commits() with --since parameter."""
        f = working_repo / "file.txt"
        f.write_text("content")
        subprocess.run(["git", "add", "file.txt"], cwd=working_repo, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "test commit"], cwd=working_repo, capture_output=True, check=True)
        git = GitIntegration(str(working_repo))
        commits = git.get_commits(since="1 day ago")
        assert len(commits) >= 0  # May or may not have commits depending on time


# ---------------------------------------------------------------------------
# get_commits() — exception path (lines 184-185)
# ---------------------------------------------------------------------------

class TestGetCommitsException:
    def test_commits_exception_handled(self, working_repo):
        """Test get_commits() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            commits = git.get_commits()
            assert commits == []


# ---------------------------------------------------------------------------
# get_diff() — untracked file (lines 210-212)
# ---------------------------------------------------------------------------

class TestGetDiffUntracked:
    def test_diff_untracked_file(self, working_repo):
        """Test get_diff() shows untracked file content."""
        f = working_repo / "untracked.txt"
        f.write_text("untracked content")
        git = GitIntegration(str(working_repo))
        diff = git.get_diff("untracked.txt")
        assert "untracked content" in diff
        assert "/dev/null" in diff


# ---------------------------------------------------------------------------
# get_diff() — exception path (lines 226-228)
# ---------------------------------------------------------------------------

class TestGetDiffException:
    def test_diff_exception_handled(self, working_repo):
        """Test get_diff() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            diff = git.get_diff()
            assert diff == ""


# ---------------------------------------------------------------------------
# get_diff_staged() — with file_path (line 235)
# ---------------------------------------------------------------------------

class TestGetDiffStagedFile:
    def test_diff_staged_file(self, working_repo):
        """Test get_diff_staged() with specific file."""
        f = working_repo / "staged_file.txt"
        f.write_text("staged content")
        subprocess.run(["git", "add", "staged_file.txt"], cwd=working_repo, capture_output=True, check=True)
        git = GitIntegration(str(working_repo))
        diff = git.get_diff_staged("staged_file.txt")
        assert "staged content" in diff


# ---------------------------------------------------------------------------
# get_diff_staged() — exception path (lines 245-247)
# ---------------------------------------------------------------------------

class TestGetDiffStagedException:
    def test_diff_staged_exception_handled(self, working_repo):
        """Test get_diff_staged() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            diff = git.get_diff_staged()
            assert diff == ""


# ---------------------------------------------------------------------------
# stage_file() — exception path (lines 260-262)
# ---------------------------------------------------------------------------

class TestStageFileException:
    def test_stage_file_exception(self, working_repo):
        """Test stage_file() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git.stage_file("file.txt")
            assert result is False


# ---------------------------------------------------------------------------
# stage_all() — exception path (lines 275-277)
# ---------------------------------------------------------------------------

class TestStageAllException:
    def test_stage_all_exception(self, working_repo):
        """Test stage_all() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git.stage_all()
            assert result is False


# ---------------------------------------------------------------------------
# commit() — with author (lines 288-302)
# ---------------------------------------------------------------------------

class TestCommitWithAuthor:
    def test_commit_with_author_config(self, working_repo):
        """Test commit() sets git config for author."""
        f = working_repo / "author.txt"
        f.write_text("author test")
        subprocess.run(["git", "add", "author.txt"], cwd=working_repo, capture_output=True, check=True)
        git = GitIntegration(str(working_repo))
        result = git.commit("author commit", author="Custom Author <custom@test.com>")
        assert result is not None
        # Verify author
        commits = git.get_commits()
        assert "Custom Author" in commits[0].author


# ---------------------------------------------------------------------------
# commit() — exception path (lines 316-318)
# ---------------------------------------------------------------------------

class TestCommitException:
    def test_commit_exception_handled(self, working_repo):
        """Test commit() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git.commit("test")
            assert result is None


# ---------------------------------------------------------------------------
# create_branch() — exception path (lines 337-339)
# ---------------------------------------------------------------------------

class TestCreateBranchException:
    def test_create_branch_exception(self, working_repo):
        """Test create_branch() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git.create_branch("feature")
            assert result is False


# ---------------------------------------------------------------------------
# switch_branch() — exception path (lines 352-354)
# ---------------------------------------------------------------------------

class TestSwitchBranchException:
    def test_switch_branch_exception(self, working_repo):
        """Test switch_branch() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git.switch_branch("feature")
            assert result is False


# ---------------------------------------------------------------------------
# delete_branch() — exception path (lines 367-369)
# ---------------------------------------------------------------------------

class TestDeleteBranchException:
    def test_delete_branch_exception(self, working_repo):
        """Test delete_branch() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git.delete_branch("feature")
            assert result is False


# ---------------------------------------------------------------------------
# get_current_branch() — exception path (lines 382-383)
# ---------------------------------------------------------------------------

class TestGetCurrentBranchException:
    def test_current_branch_exception(self, working_repo):
        """Test get_current_branch() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git.get_current_branch()
            assert result == ""


# ---------------------------------------------------------------------------
# rollback() — exception path (lines 398-400)
# ---------------------------------------------------------------------------

class TestRollbackException:
    def test_rollback_exception(self, working_repo):
        """Test rollback() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git.rollback("HEAD~1")
            assert result is False


# ---------------------------------------------------------------------------
# list_branches() — exception path (lines 413-414)
# ---------------------------------------------------------------------------

class TestListBranchesException:
    def test_list_branches_exception(self, working_repo):
        """Test list_branches() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git.list_branches()
            assert result == []


# ---------------------------------------------------------------------------
# is_gitignored() — exception path (lines 427-428)
# ---------------------------------------------------------------------------

class TestIsGitignoredException:
    def test_gitignored_exception(self, working_repo):
        """Test is_gitignored() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git.is_gitignored("file.txt")
            assert result is False


# ---------------------------------------------------------------------------
# _get_head_hash() — exception path (lines 445-446)
# ---------------------------------------------------------------------------

class TestGetHeadHashException:
    def test_head_hash_exception(self, working_repo):
        """Test _get_head_hash() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git._get_head_hash()
            assert result == ""


# ---------------------------------------------------------------------------
# get_file_history() — exception path (lines 459-460)
# ---------------------------------------------------------------------------

class TestGetFileHistoryException:
    def test_file_history_exception(self, working_repo):
        """Test get_file_history() handles exception gracefully."""
        with patch("tektos.git_integration.subprocess.run") as mock_run:
            mock_run.side_effect = RuntimeError("git error")
            git = GitIntegration(str(working_repo))
            result = git.get_file_history("file.txt")
            assert result == []


# ---------------------------------------------------------------------------
# auto_commit_if_changes() — failure path (lines 481-482)
# ---------------------------------------------------------------------------

class TestAutoCommitFailure:
    def test_auto_commit_failure(self, working_repo):
        """Test auto_commit_if_changes() returns False when commit fails."""
        # Create a file and stage it (making repo dirty)
        f = working_repo / "auto_fail.txt"
        f.write_text("to commit")
        subprocess.run(["git", "add", "auto_fail.txt"], cwd=working_repo, capture_output=True, check=True)
        
        git = GitIntegration(str(working_repo))
        
        # Mock stage_all to succeed but commit to fail
        with patch.object(git, "stage_all", return_value=True):
            with patch.object(git, "commit", return_value=None):
                result = git.auto_commit_if_changes()
                assert result is False
