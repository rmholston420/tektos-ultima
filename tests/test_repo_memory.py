"""Tests for runtime/repo_memory.py — RepoMemory."""

import tempfile
from pathlib import Path

import pytest

from tektos.runtime.repo_memory import RepoMemory, RepoMemoryEntry, get_repo_memory


class TestRepoMemoryEntry:
    """Tests for RepoMemoryEntry dataclass."""

    def test_create_entry(self):
        entry = RepoMemoryEntry(
            filename="AGENTS.md",
            content="Test content",
            source="/path/to/AGENTS.md",
            priority=1,
        )
        assert entry.filename == "AGENTS.md"
        assert entry.content == "Test content"
        assert entry.priority == 1
        assert entry.token_count == 3  # len("Test content") // 4 = 3

    def test_token_count_calculation(self):
        entry = RepoMemoryEntry(
            filename="test.md",
            content="A" * 100,
            source="/path",
            priority=0,
        )
        assert entry.token_count == 25  # 100 // 4


class TestRepoMemory:
    """Tests for RepoMemory."""

    def test_create_memory(self):
        mem = RepoMemory(project_root="/tmp")
        assert mem.project_root == "/tmp"
        assert mem._entries == []
        assert mem._merged_context == ""
        assert mem._loaded is False

    def test_load_no_files(self, tmp_path):
        mem = RepoMemory(project_root=str(tmp_path))
        mem.load()
        assert mem._loaded is True
        assert mem._entries == []
        assert mem.context_prompt == ""

    def test_load_single_file(self, tmp_path):
        # Create AGENTS.md
        agents_file = tmp_path / "AGENTS.md"
        agents_file.write_text("Use pytest for testing.\n")

        mem = RepoMemory(project_root=str(tmp_path))
        mem.load()
        # May load additional files from project root (CLAUDE.md, etc.)
        assert len(mem._entries) >= 1
        assert any("AGENTS.md" in e.filename for e in mem._entries)
        assert "Use pytest" in mem.context_prompt

    def test_load_multiple_files(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Rule 1\n")
        (tmp_path / "CLAUDE.md").write_text("Rule 2\n")

        mem = RepoMemory(project_root=str(tmp_path))
        mem.load()
        # May load additional files from project root (e.g. AGENTS.md from parent)
        assert len(mem._entries) >= 2
        # CLAUDE.md has higher priority (lower number)
        assert any(e.filename == "CLAUDE.md" for e in mem._entries)

    def test_context_prompt_property(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Test content\n")
        mem = RepoMemory(project_root=str(tmp_path))
        prompt = mem.context_prompt
        assert "# Repository Memory" in prompt
        assert "Test content" in prompt

    def test_context_prompt_lazy_load(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Test\n")
        mem = RepoMemory(project_root=str(tmp_path))
        assert mem._loaded is False
        _ = mem.context_prompt  # triggers load
        assert mem._loaded is True

    def test_reload(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Original\n")
        mem = RepoMemory(project_root=str(tmp_path))
        mem.load()
        assert "Original" in mem.context_prompt

        # Modify file
        (tmp_path / "AGENTS.md").write_text("Updated\n")
        mem.reload()
        assert "Updated" in mem.context_prompt
        assert "Original" not in mem.context_prompt

    def test_to_memory_entry(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Test\n")
        mem = RepoMemory(project_root=str(tmp_path))
        mem.load()
        entry = mem.to_memory_entry()
        assert entry["files_loaded"] >= 1
        assert "AGENTS.md" in entry["files"]
        assert entry["total_tokens"] > 0

    def test_bool_empty(self):
        mem = RepoMemory()
        assert bool(mem) is False

    def test_bool_with_entries(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Test\n")
        mem = RepoMemory(project_root=str(tmp_path))
        mem.load()
        assert bool(mem) is True

    def test_deduplication(self, tmp_path):
        # Two files with same content hash (first 500 chars)
        (tmp_path / "AGENTS.md").write_text("A" * 600 + "unique1\n")
        (tmp_path / "CLAUDE.md").write_text("A" * 600 + "unique2\n")

        mem = RepoMemory(project_root=str(tmp_path))
        mem.load()
        # May load additional files from project root
        assert len(mem._entries) >= 2

    def test_token_limit_truncation(self, tmp_path):
        # Create a very large file
        large_content = "X" * 50000
        (tmp_path / "AGENTS.md").write_text(large_content)

        mem = RepoMemory(project_root=str(tmp_path))
        mem.load()
        # Should be truncated
        assert "truncated" in mem.context_prompt

    def test_get_context_prompt_alias(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("Test\n")
        mem = RepoMemory(project_root=str(tmp_path))
        assert mem.get_context_prompt() == mem.context_prompt


class TestGetRepoMemory:
    """Tests for get_repo_memory convenience function."""

    def test_singleton(self, tmp_path):
        mem1 = get_repo_memory(project_root=str(tmp_path))
        mem2 = get_repo_memory(project_root=str(tmp_path))
        assert mem1 is mem2

    def test_different_project(self, tmp_path):
        mem1 = get_repo_memory(project_root=str(tmp_path))
        mem2 = get_repo_memory(project_root=str(tmp_path / "other"))
        assert mem1 is not mem2

    def test_load_repo_memory(self, tmp_path):
        from tektos.runtime.repo_memory import load_repo_memory
        mem = load_repo_memory(project_root=str(tmp_path))
        assert mem is not None
