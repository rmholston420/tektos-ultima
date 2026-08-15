"""
Tektos-Ultima v1 — Git Integration Tests

Tests GitIntegration class using real git repos in temp dirs:
- init_repo, is_repo
- get_status (dirty/clean, staged/modified/untracked)
- get_commits with --numstat parsing
- get_diff (staged and unstaged)
- stage_file, stage_all
- commit with author parsing
- create_branch, switch_branch, delete_branch
- list_branches, current_branch
- rollback (hard and soft)
- get_head_hash
- get_file_history
- auto_commit_if_changes
- is_gitignored
"""

import subprocess
from pathlib import Path

import pytest

from tektos.git_integration import GitIntegration, GitStatus, GitCommit


@pytest.fixture
def bare_repo(tmp_path):
    """Create a bare git repo at tmp_path (no working tree)."""
    subprocess.run(["git", "init", "--bare"], cwd=str(tmp_path), capture_output=True, check=True)
    return tmp_path


@pytest.fixture
def working_repo(tmp_path):
    """Create a working git repo with user config and initial commit."""
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@tektos.dev"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), capture_output=True, check=True)
    # Make an initial commit so git recognizes the repo
    (tmp_path / ".gitkeep").write_text("")
    subprocess.run(["git", "add", ".gitkeep"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(tmp_path), capture_output=True, check=True)
    return tmp_path


# ---------------------------------------------------------------------------
# init_repo / is_repo
# ---------------------------------------------------------------------------


class TestInitRepo:
    def test_is_repo_returns_true_in_git_repo(self, working_repo):
        git = GitIntegration(str(working_repo))
        assert git.is_repo() is True

    def test_is_repo_returns_false_outside_git_repo(self, tmp_path):
        git = GitIntegration(str(tmp_path))
        assert git.is_repo() is False

    def test_is_repo_returns_false_for_nonexistent(self, tmp_path):
        git = GitIntegration(str(tmp_path / "nonexistent"))
        assert git.is_repo() is False

    def test_init_repo_already_initialized(self, working_repo):
        git = GitIntegration(str(working_repo))
        assert git.init_repo() is True  # should succeed without error


# ---------------------------------------------------------------------------
# GitStatus
# ---------------------------------------------------------------------------


class TestGitStatus:
    def test_initial_status_clean(self, working_repo):
        git = GitIntegration(str(working_repo))
        status = git.get_status()
        assert isinstance(status, GitStatus)
        assert status.is_dirty is False

    def test_status_dirty_after_unstaged_change(self, working_repo):
        f = working_repo / "change.txt"
        f.write_text("dirty content")
        subprocess.run(["git", "add", "change.txt"], cwd=str(working_repo), capture_output=True)
        f.write_text("dirty content modified")
        git = GitIntegration(str(working_repo))
        status = git.get_status()
        assert status.is_dirty is True
        # After amend: staged + modified, code may return staged_files instead
        assert "change.txt" in status.staged_files or "change.txt" in status.modified_files

    def test_status_untracked_file(self, working_repo):
        f = working_repo / "new_file.txt"
        f.write_text("untracked")
        git = GitIntegration(str(working_repo))
        status = git.get_status()
        assert status.is_dirty is True
        assert "new_file.txt" in status.untracked_files

    def test_status_staged_file(self, working_repo):
        f = working_repo / "staged.txt"
        f.write_text("staged content")
        subprocess.run(["git", "add", "staged.txt"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        status = git.get_status()
        assert status.is_dirty is True
        assert "staged.txt" in status.staged_files

    def test_branch_name(self, working_repo):
        git = GitIntegration(str(working_repo))
        status = git.get_status()
        assert status.branch == "master" or status.branch == "main"

    def test_branch_after_switch(self, working_repo):
        f = working_repo / "initial.txt"
        f.write_text("initial")
        subprocess.run(["git", "add", "initial.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        git.create_branch("feature")
        status = git.get_status()
        assert status.branch == "master" or status.branch == "main"


# ---------------------------------------------------------------------------
# get_commits
# ---------------------------------------------------------------------------


class TestGetCommits:
    def test_empty_repo_no_commits(self, tmp_path):
        """A repo with no commits at all returns no commits."""
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@tektos.dev"], cwd=str(tmp_path), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), capture_output=True, check=True)
        git = GitIntegration(str(tmp_path))
        commits = git.get_commits()
        assert commits == []

    def test_commits_after_commit(self, working_repo):
        f = working_repo / "file.txt"
        f.write_text("content")
        subprocess.run(["git", "add", "file.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "first commit"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        commits = git.get_commits()
        assert len(commits) >= 1
        assert commits[0].message == "first commit"

    def test_commit_has_hash_fields(self, working_repo):
        f = working_repo / "file.txt"
        f.write_text("content")
        subprocess.run(["git", "add", "file.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "hash test"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        commits = git.get_commits()
        assert len(commits) >= 1
        c = commits[0]
        assert isinstance(c, GitCommit)
        assert len(c.hash) == 40
        assert len(c.short_hash) == 7

    def test_commit_has_author(self, working_repo):
        f = working_repo / "file.txt"
        f.write_text("content")
        subprocess.run(["git", "add", "file.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "author test"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        commits = git.get_commits()
        assert commits[0].author == "Test User"

    def test_commits_count_limit(self, tmp_path):
        """Count limit returns exactly N commits from a repo with more."""
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "test@tektos.dev"], cwd=str(tmp_path), capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), capture_output=True, check=True)
        for i in range(5):
            f = tmp_path / f"file{i}.txt"
            f.write_text(f"content {i}")
            subprocess.run(["git", "add", f"file{i}.txt"], cwd=str(tmp_path), capture_output=True)
            subprocess.run(["git", "commit", "-m", f"commit {i}"], cwd=str(tmp_path), capture_output=True)
        git = GitIntegration(str(tmp_path))
        commits = git.get_commits(count=3)
        assert len(commits) == 3

    def test_commit_files_changed(self, working_repo):
        f = working_repo / "multi.txt"
        f.write_text("line1\nline2\nline3\n")
        subprocess.run(["git", "add", "multi.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "multi file"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        commits = git.get_commits()
        assert commits[0].files_changed == ["multi.txt"]
        assert commits[0].lines_added == 3

    def test_commit_lines_added_deleted(self, working_repo):
        # First commit
        f = working_repo / "file.txt"
        f.write_text("line1\nline2\nline3\n")
        subprocess.run(["git", "add", "file.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "first"], cwd=str(working_repo), capture_output=True)
        # Second commit — modify and delete
        f.write_text("line1\nline2\nline3\nline4\n")  # +1 line
        subprocess.run(["git", "add", "file.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "second"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        commits = git.get_commits()
        assert len(commits) >= 2
        assert commits[0].lines_added >= 1

    def test_get_commits_non_repo(self, bare_repo):
        """Bare repos return empty commits (no working tree)."""
        git = GitIntegration(str(bare_repo))
        commits = git.get_commits()
        assert commits == []


# ---------------------------------------------------------------------------
# get_diff
# ---------------------------------------------------------------------------


class TestGetDiff:
    def test_diff_empty_on_clean(self, working_repo):
        git = GitIntegration(str(working_repo))
        diff = git.get_diff()
        assert diff == ""

    def test_diff_shows_modified(self, working_repo):
        f = working_repo / "file.txt"
        f.write_text("original")
        subprocess.run(["git", "add", "file.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "original"], cwd=str(working_repo), capture_output=True)
        f.write_text("modified content")
        git = GitIntegration(str(working_repo))
        diff = git.get_diff()
        assert "modified content" in diff

    def test_diff_staged(self, working_repo):
        f = working_repo / "file.txt"
        f.write_text("content")
        subprocess.run(["git", "add", "file.txt"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        diff = git.get_diff_staged()
        assert "content" in diff

    def test_diff_file_specific(self, working_repo):
        f = working_repo / "file.txt"
        f.write_text("original")
        subprocess.run(["git", "add", "file.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "orig"], cwd=str(working_repo), capture_output=True)
        f.write_text("changed")
        git = GitIntegration(str(working_repo))
        diff = git.get_diff("file.txt")
        assert "changed" in diff


# ---------------------------------------------------------------------------
# stage / commit
# ---------------------------------------------------------------------------


class TestStageCommit:
    def test_stage_file(self, working_repo):
        f = working_repo / "stage.txt"
        f.write_text("to stage")
        git = GitIntegration(str(working_repo))
        result = git.stage_file("stage.txt")
        assert result is True
        status = git.get_status()
        assert "stage.txt" in status.staged_files

    def test_stage_all(self, working_repo):
        (working_repo / "a.txt").write_text("a")
        (working_repo / "b.txt").write_text("b")
        git = GitIntegration(str(working_repo))
        result = git.stage_all()
        assert result is True
        status = git.get_status()
        assert "a.txt" in status.staged_files
        assert "b.txt" in status.staged_files

    def test_commit_returns_hash(self, working_repo):
        f = working_repo / "commit.txt"
        f.write_text("commit me")
        subprocess.run(["git", "add", "commit.txt"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        commit_hash = git.commit("test commit")
        assert commit_hash is not None
        assert len(commit_hash) == 40

    def test_commit_no_changes_returns_none(self, working_repo):
        git = GitIntegration(str(working_repo))
        result = git.commit("no changes")
        assert result is None

    def test_commit_with_author(self, working_repo):
        f = working_repo / "author.txt"
        f.write_text("author test")
        subprocess.run(["git", "add", "author.txt"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        git.commit("author commit", author="Other Author <other@test.com>")
        commits = git.get_commits()
        assert commits[0].author == "Other Author"

    def test_commit_twice(self, working_repo):
        f = working_repo / "c.txt"
        subprocess.run(["git", "add", "."], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        h1 = git.commit("first")
        f.write_text("second")
        subprocess.run(["git", "add", "c.txt"], cwd=str(working_repo), capture_output=True)
        h2 = git.commit("second")
        assert h1 != h2

    def test_stage_all_returns_true(self, working_repo):
        (working_repo / "sa.txt").write_text("data")
        git = GitIntegration(str(working_repo))
        assert git.stage_all() is True


# ---------------------------------------------------------------------------
# Branch management
# ---------------------------------------------------------------------------


class TestBranchManagement:
    def test_create_branch(self, working_repo):
        subprocess.run(["git", "commit", "--allow-empty", "-m", "empty"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        result = git.create_branch("feature/test")
        assert result is True

    def test_create_branch_from(self, working_repo):
        subprocess.run(["git", "commit", "--allow-empty", "-m", "empty"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        result = git.create_branch("from-branch", from_branch="master")
        assert result is True

    def test_switch_branch(self, working_repo):
        subprocess.run(["git", "commit", "--allow-empty", "-m", "empty"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        git.create_branch("switchable")
        result = git.switch_branch("switchable")
        assert result is True
        assert git.get_current_branch() == "switchable"

    def test_switch_branch_nonexistent(self, working_repo):
        git = GitIntegration(str(working_repo))
        result = git.switch_branch("nonexistent")
        assert result is False

    def test_delete_branch(self, working_repo):
        subprocess.run(["git", "commit", "--allow-empty", "-m", "empty"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        git.create_branch("deletable")
        result = git.delete_branch("deletable")
        assert result is True

    def test_delete_current_branch_fails(self, working_repo):
        subprocess.run(["git", "commit", "--allow-empty", "-m", "empty"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        result = git.delete_branch("master")
        assert result is False

    def test_list_branches(self, working_repo):
        subprocess.run(["git", "commit", "--allow-empty", "-m", "empty"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        git.create_branch("branch-a")
        git.create_branch("branch-b")
        branches = git.list_branches()
        assert "master" in branches or "main" in branches
        assert "branch-a" in branches
        assert "branch-b" in branches

    def test_list_branches_empty(self, tmp_path):
        """A repo with no commits has no branches."""
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
        git = GitIntegration(str(tmp_path))
        branches = git.list_branches()
        assert len(branches) == 0

    def test_current_branch(self, working_repo):
        git = GitIntegration(str(working_repo))
        branch = git.get_current_branch()
        assert branch is not None


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


class TestRollback:
    def test_rollback_hard(self, working_repo):
        f = working_repo / "rollback.txt"
        f.write_text("before")
        subprocess.run(["git", "add", "rollback.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "before"], cwd=str(working_repo), capture_output=True)
        head_before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(working_repo), capture_output=True, text=True).stdout.strip()
        f.write_text("after")
        subprocess.run(["git", "add", "rollback.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "after"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        result = git.rollback(head_before, soft=False)
        assert result is True
        assert f.read_text() == "before"

    def test_rollback_soft(self, working_repo):
        f = working_repo / "soft.txt"
        f.write_text("before")
        subprocess.run(["git", "add", "soft.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "before"], cwd=str(working_repo), capture_output=True)
        head_before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(working_repo), capture_output=True, text=True).stdout.strip()
        f.write_text("after")
        subprocess.run(["git", "add", "soft.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "after"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        result = git.rollback(head_before, soft=True)
        assert result is True
        # Soft reset keeps changes in staging area
        status = git.get_status()
        assert status.is_dirty is True

    def test_rollback_invalid_hash(self, working_repo):
        git = GitIntegration(str(working_repo))
        result = git.rollback("invalid-nonexistent-hash", soft=False)
        assert result is False


# ---------------------------------------------------------------------------
# Head hash / file history
# ---------------------------------------------------------------------------


class TestHeadAndHistory:
    def test_get_head_hash(self, working_repo):
        subprocess.run(["git", "commit", "--allow-empty", "-m", "empty"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        h = git.get_head_hash()
        assert len(h) == 40

    def test_head_hash_matches_git(self, working_repo):
        subprocess.run(["git", "commit", "--allow-empty", "-m", "empty"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        h = git.get_head_hash()
        actual = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(working_repo), capture_output=True, text=True).stdout.strip()
        assert h == actual

    def test_file_history_empty(self, working_repo):
        git = GitIntegration(str(working_repo))
        history = git.get_file_history("nonexistent.txt")
        assert history == []

    def test_file_history_returns_entries(self, working_repo):
        f = working_repo / "history.txt"
        f.write_text("v1")
        subprocess.run(["git", "add", "history.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "v1"], cwd=str(working_repo), capture_output=True)
        f.write_text("v2")
        subprocess.run(["git", "add", "history.txt"], cwd=str(working_repo), capture_output=True)
        subprocess.run(["git", "commit", "-m", "v2"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        history = git.get_file_history("history.txt")
        assert len(history) >= 2

    def test_file_history_limit(self, working_repo):
        f = working_repo / "limited.txt"
        for i in range(5):
            f.write_text(f"v{i}")
            subprocess.run(["git", "add", "limited.txt"], cwd=str(working_repo), capture_output=True)
            subprocess.run(["git", "commit", "-m", f"v{i}"], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        history = git.get_file_history("limited.txt", limit=2)
        assert len(history) == 2


# ---------------------------------------------------------------------------
# auto_commit / is_gitignored
# ---------------------------------------------------------------------------


class TestAutoCommit:
    def test_auto_commit_no_changes(self, working_repo):
        git = GitIntegration(str(working_repo))
        assert git.auto_commit_if_changes() is True

    def test_auto_commit_with_changes(self, working_repo):
        f = working_repo / "auto.txt"
        f.write_text("auto content")
        subprocess.run(["git", "add", "."], cwd=str(working_repo), capture_output=True)
        git = GitIntegration(str(working_repo))
        result = git.auto_commit_if_changes()
        assert result is True
        # Should be clean now
        status = git.get_status()
        assert status.is_dirty is False

    def test_is_gitignored(self, working_repo):
        git = GitIntegration(str(working_repo))
        (working_repo / ".gitignore").write_text("*.log")
        (working_repo / "test.log").write_text("log")
        assert git.is_gitignored("test.log") is True

    def test_is_gitignored_not_ignored(self, working_repo):
        git = GitIntegration(str(working_repo))
        (working_repo / ".gitignore").write_text("*.log")
        (working_repo / "test.py").write_text("code")
        assert git.is_gitignored("test.py") is False