"""Tests for SandboxProvider (src/tektos/providers/sandbox_provider.py).

Covers all 7 tool handlers, path sandboxing, bash execution, and file operations.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from src.tektos.providers.sandbox_provider import SandboxProvider


@pytest.fixture
def sandbox(tmp_path: Path):
    """Create a SandboxProvider with a temporary root."""
    return SandboxProvider(fs_root=tmp_path, bash_timeout=10, max_output_size=1000)


# ======================================================================
# execute() — dispatch
# ======================================================================

class TestExecuteDispatch:
    def test_execute_unknown_tool(self, sandbox: SandboxProvider):
        assert sandbox.execute("nonexistent", {"foo": "bar"}) == "Unknown tool: nonexistent"

    def test_execute_bash(self, sandbox: SandboxProvider, tmp_path: Path):
        # Create a test file
        test_file = tmp_path / "hello.txt"
        test_file.write_text("hello")
        result = sandbox.execute("bash", {"command": f"cat {test_file}"})
        assert "hello" in result

    def test_execute_bash_missing_command(self, sandbox: SandboxProvider):
        result = sandbox.execute("bash", {"command": ""})
        assert "Error: No command provided" in result


# ======================================================================
# _safe_path — security
# ======================================================================

class TestSafePath:
    def test_safe_path_normal(self, sandbox: SandboxProvider, tmp_path: Path):
        p = sandbox._safe_path("subdir")
        assert p == tmp_path / "subdir"

    def test_safe_path_outside_sandbox(self, sandbox: SandboxProvider, tmp_path: Path):
        p = sandbox._safe_path("../../etc/passwd")
        assert p is None

    def test_safe_path_empty(self, sandbox: SandboxProvider):
        assert sandbox._safe_path("") is None
        assert sandbox._safe_path(None) is None  # type: ignore[arg-type]

    def test_safe_path_traversal_in_middle(self, sandbox: SandboxProvider, tmp_path: Path):
        # Even if inside sandbox, traversal escapes → rejected
        p = sandbox._safe_path("subdir/../../etc")
        assert p is None


# ======================================================================
# _execute_bash
# ======================================================================

class TestExecuteBash:
    def test_bash_success(self, sandbox: SandboxProvider):
        result = sandbox.execute("bash", {"command": "echo hello"})
        assert "hello" in result
        assert "Exit 0" in result
        assert "success" in result

    def test_bash_failure(self, sandbox: SandboxProvider):
        result = sandbox.execute("bash", {"command": "false"})
        assert "Exit 1" in result
        assert "failed" in result

    def test_bash_stderr(self, sandbox: SandboxProvider):
        result = sandbox.execute("bash", {"command": "echo ok && echo error >&2; exit 1"})
        assert "stderr" in result
        assert "error" in result
        assert "failed" in result

    def test_bash_timeout(self, tmp_path: Path):
        s = SandboxProvider(fs_root=tmp_path, bash_timeout=1)
        result = s.execute("bash", {"command": "sleep 5"})
        assert "timed out" in result

    def test_bash_output_truncation(self, tmp_path: Path):
        s = SandboxProvider(fs_root=tmp_path, bash_timeout=10, max_output_size=50)
        result = s.execute("bash", {"command": "python -c 'print(\"A\" * 2000)'"})
        assert "truncated" in result or len(result) <= s.max_output_size + 200


# ======================================================================
# _file_read
# ======================================================================

class TestFileRead:
    def test_file_read_success(self, sandbox: SandboxProvider, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_text("test content")
        result = sandbox.execute("file_read", {"path": "test.txt"})
        assert "test content" in result

    def test_file_read_missing(self, sandbox: SandboxProvider):
        result = sandbox.execute("file_read", {"path": "missing.txt"})
        assert "not found" in result

    def test_file_read_not_a_file(self, sandbox: SandboxProvider, tmp_path: Path):
        d = tmp_path / "adir"
        d.mkdir()
        result = sandbox.execute("file_read", {"path": "adir"})
        assert "Not a file" in result

    def test_file_read_outside_sandbox(self, sandbox: SandboxProvider):
        result = sandbox.execute("file_read", {"path": "../../../etc/passwd"})
        assert "outside sandbox" in result

    def test_file_read_empty(self, sandbox: SandboxProvider, tmp_path: Path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = sandbox.execute("file_read", {"path": "empty.txt"})
        assert result == ""


# ======================================================================
# _file_write
# ======================================================================

class TestFileWrite:
    def test_file_write_new(self, sandbox: SandboxProvider, tmp_path: Path):
        result = sandbox.execute("file_write", {"path": "new.txt", "content": "hello"})
        assert "Written" in result
        assert (tmp_path / "new.txt").read_text() == "hello"

    def test_file_write_append(self, sandbox: SandboxProvider, tmp_path: Path):
        (tmp_path / "a.txt").write_text("first")
        result = sandbox.execute("file_write", {"path": "a.txt", "content": " second", "mode": "append"})
        assert "second" in (tmp_path / "a.txt").read_text()

    def test_file_write_creates_dirs(self, sandbox: SandboxProvider, tmp_path: Path):
        sandbox.execute("file_write", {"path": "deep/nested/dir/f.txt", "content": "x"})
        assert (tmp_path / "deep/nested/dir/f.txt").read_text() == "x"

    def test_file_write_outside_sandbox(self, sandbox: SandboxProvider):
        result = sandbox.execute("file_write", {"path": "../../../etc/hack", "content": "bad"})
        assert "outside sandbox" in result

    def test_file_write_no_path(self, sandbox: SandboxProvider):
        result = sandbox.execute("file_write", {"path": "", "content": "x"})
        assert "No path provided" in result


# ======================================================================
# _file_delete
# ======================================================================

class TestFileDelete:
    def test_delete_file(self, sandbox: SandboxProvider, tmp_path: Path):
        f = tmp_path / "to_delete.txt"
        f.write_text("bye")
        result = sandbox.execute("file_delete", {"path": "to_delete.txt"})
        assert "Deleted file" in result
        assert not f.exists()

    def test_delete_directory(self, sandbox: SandboxProvider, tmp_path: Path):
        d = tmp_path / "rmdir"
        d.mkdir()
        (d / "sub.txt").write_text("x")
        result = sandbox.execute("file_delete", {"path": "rmdir"})
        assert "Deleted directory" in result
        assert not d.exists()

    def test_delete_outside_sandbox(self, sandbox: SandboxProvider):
        result = sandbox.execute("file_delete", {"path": "../../../etc"})
        assert "outside sandbox" in result

    def test_delete_no_path(self, sandbox: SandboxProvider):
        result = sandbox.execute("file_delete", {"path": ""})
        assert "No path provided" in result


# ======================================================================
# _directory_list
# ======================================================================

class TestDirectoryList:
    def test_list_dir(self, sandbox: SandboxProvider, tmp_path: Path):
        (tmp_path / "a.txt").write_text("")
        (tmp_path / "bdir").mkdir()
        result = sandbox.execute("directory_list", {"path": "."})
        assert "FILE a.txt" in result
        assert "DIR bdir" in result

    def test_list_empty_dir(self, sandbox: SandboxProvider, tmp_path: Path):
        d = tmp_path / "empty"
        d.mkdir()
        result = sandbox.execute("directory_list", {"path": "empty"})
        assert "empty directory" in result.lower() or result == ""

    def test_list_not_a_dir(self, sandbox: SandboxProvider, tmp_path: Path):
        f = tmp_path / "notdir.txt"
        f.write_text("x")
        result = sandbox.execute("directory_list", {"path": "notdir.txt"})
        assert "Not a directory" in result

    def test_list_outside_sandbox(self, sandbox: SandboxProvider):
        result = sandbox.execute("directory_list", {"path": "../../../etc"})
        assert "outside sandbox" in result


# ======================================================================
# _directory_create
# ======================================================================

class TestDirectoryCreate:
    def test_create_single_dir(self, sandbox: SandboxProvider, tmp_path: Path):
        result = sandbox.execute("directory_create", {"path": "newdir"})
        assert "Created directory" in result
        assert (tmp_path / "newdir").is_dir()

    def test_create_nested_dirs(self, sandbox: SandboxProvider, tmp_path: Path):
        sandbox.execute("directory_create", {"path": "a/b/c/d"})
        assert (tmp_path / "a/b/c/d").is_dir()

    def test_create_outside_sandbox(self, sandbox: SandboxProvider):
        result = sandbox.execute("directory_create", {"path": "../../../opt"})
        assert "outside sandbox" in result

    def test_create_no_path(self, sandbox: SandboxProvider):
        result = sandbox.execute("directory_create", {"path": ""})
        assert "No path provided" in result


# ======================================================================
# _search
# ======================================================================

class TestSearch:
    def test_search_in_file(self, sandbox: SandboxProvider, tmp_path: Path):
        (tmp_path / "search_me.txt").write_text("hello world\ngoodbye world")
        result = sandbox.execute("search", {"query": "hello", "path": "."})
        assert "hello" in result.lower()

    def test_search_in_dir(self, sandbox: SandboxProvider, tmp_path: Path):
        (tmp_path / "a.txt").write_text("alpha")
        (tmp_path / "b.txt").write_text("beta")
        result = sandbox.execute("search", {"query": "alpha", "path": "."})
        assert "a.txt" in result

    def test_search_case_insensitive(self, sandbox: SandboxProvider, tmp_path: Path):
        (tmp_path / "case.txt").write_text("HELLO")
        result = sandbox.execute("search", {"query": "hello"})
        assert "HELLO" in result

    def test_search_case_sensitive(self, sandbox: SandboxProvider, tmp_path: Path):
        (tmp_path / "case.txt").write_text("hello")
        result = sandbox.execute("search", {"query": "HELLO", "case_sensitive": True})
        assert "No matches" in result

    def test_search_no_matches(self, sandbox: SandboxProvider, tmp_path: Path):
        (tmp_path / "no.txt").write_text("nothing here")
        result = sandbox.execute("search", {"query": "xyz"})
        assert "No matches" in result

    def test_search_max_results(self, sandbox: SandboxProvider, tmp_path: Path):
        for i in range(10):
            (tmp_path / f"f{i}.txt").write_text("match")
        result = sandbox.execute("search", {"query": "match", "max_results": 3})
        assert result.count("match") <= 3

    def test_search_no_query(self, sandbox: SandboxProvider):
        result = sandbox.execute("search", {"query": ""})
        assert "No search query provided" in result
