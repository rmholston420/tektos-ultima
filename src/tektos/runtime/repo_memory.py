"""Repo Memory — Persistent project instructions for AI agents.

Implements the CLAUDE.md / AGENTS.md / GEMINI.md pattern adopted by
Claude Code, Cursor, Windsurf, and other leading coding agents.

These files act as persistent instructions that shape how the agent
understands and operates within a repository. They are loaded once at
startup and injected into the system prompt for every session.

Supported files (in priority order):
- CLAUDE.md — Claude Code's standard
- AGENTS.md — Generic agent instructions
- GEMINI.md — Gemini CLI standard
- .cursorrules — Cursor's standard
- .windsurfrules — Windsurf's standard
- AGENTS.md — Hermes Agent's standard

Each file can contain:
- Project structure overview
- Coding conventions and style guide
- Build/test commands
- Architecture decisions
- Common pitfalls
- Tool usage patterns
- Domain-specific knowledge

The system loads all found files, deduplicates content, and merges
them into a single context block that's injected into every LLM call.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Standard repo memory file names (in priority order)
REPO_MEMORY_FILES = [
    "CLAUDE.md",
    "AGENTS.md",
    "GEMINI.md",
    ".cursorrules",
    ".windsurfrules",
    "AGENTS.md",
]

# Maximum total size for repo memory (tokens, roughly 4 chars per token)
MAX_REPO_MEMORY_TOKENS = 8192  # ~32KB max


@dataclass
class RepoMemoryEntry:
    """A single repo memory file entry."""
    filename: str
    content: str
    source: str  # Which file it came from
    priority: int  # Load priority (lower = higher priority)
    token_count: int = 0
    
    def __post_init__(self):
        # Estimate token count (rough: 4 chars per token)
        self.token_count = len(self.content) // 4


@dataclass
class RepoMemory:
    """Manages repo memory files (CLAUDE.md, AGENTS.md, etc.).
    
    Loads, parses, and merges project-specific instructions that shape
    how the agent operates within a repository.
    """
    
    project_root: str = "."
    _entries: list[RepoMemoryEntry] = field(default_factory=list)
    _merged_context: str = ""
    _loaded: bool = False
    
    def load(self) -> None:
        """Load all repo memory files from the project root.
        
        Files are loaded in priority order and merged into a single
        context block. Duplicate content is deduplicated.
        """
        self._entries = []
        project_path = Path(self.project_root)
        
        for priority, filename in enumerate(REPO_MEMORY_FILES):
            filepath = project_path / filename
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8")
                    if content.strip():
                        entry = RepoMemoryEntry(
                            filename=filename,
                            content=content,
                            source=str(filepath),
                            priority=priority,
                        )
                        self._entries.append(entry)
                        log.info(f"[RepoMemory] Loaded {filename} ({entry.token_count} tokens)")
                except Exception as exc:
                    log.warning(f"[RepoMemory] Failed to load {filename}: {exc}")
        
        # Sort by priority
        self._entries.sort(key=lambda e: e.priority)
        
        # Merge into single context
        self._merge_context()
        self._loaded = True
        
        log.info(f"[RepoMemory] Loaded {len(self._entries)} files, "
                f"{sum(e.token_count for e in self._entries)} total tokens")
    
    def _merge_context(self) -> None:
        """Merge all entries into a single context block.
        
        Deduplicates content and enforces token limits.
        """
        if not self._entries:
            self._merged_context = ""
            return
        
        # Merge entries with headers
        sections = []
        seen_content = set()
        
        for entry in self._entries:
            # Skip if content is too similar to what we already have
            content_hash = hash(entry.content[:500])
            if content_hash in seen_content:
                log.debug(f"[RepoMemory] Skipping duplicate: {entry.filename}")
                continue
            seen_content.add(content_hash)
            
            # Add header
            sections.append(f"\n# {entry.filename}\n")
            sections.append(entry.content)
        
        # Combine and enforce token limit
        merged = "\n".join(sections)
        
        # Truncate if over limit (rough estimate)
        if len(merged) // 4 > MAX_REPO_MEMORY_TOKENS:
            # Keep first N tokens worth of content
            max_chars = MAX_REPO_MEMORY_TOKENS * 4
            merged = merged[:max_chars]
            merged += "\n\n# ... [truncated - repo memory exceeds token limit]"
            log.warning(f"[RepoMemory] Truncated to {MAX_REPO_MEMORY_TOKENS} tokens")
        
        self._merged_context = merged
    
    @property
    def context_prompt(self) -> str:
        """Get the merged repo memory as a context prompt.
        
        Returns:
            Formatted context string for injection into system prompt.
        """
        if not self._loaded:
            self.load()
        
        if not self._merged_context:
            return ""
        
        return f"\n\n# Repository Memory\n{self._merged_context}"
    
    def get_context_prompt(self) -> str:
        """Alias for context_prompt property."""
        return self.context_prompt
    
    def reload(self) -> None:
        """Reload all repo memory files (for hot-reload support)."""
        self._loaded = False
        self.load()
    
    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "files_loaded": len(self._entries),
            "total_tokens": sum(e.token_count for e in self._entries),
            "merged_size": len(self._merged_context),
            "files": [e.filename for e in self._entries],
        }
    
    def __bool__(self) -> bool:
        return bool(self._entries)


# ── Convenience Functions ───────────────────────────────────────────────────

_repo_memory: RepoMemory | None = None


def get_repo_memory(project_root: str = ".") -> RepoMemory:
    """Get or create the repo memory manager.
    
    Args:
        project_root: Path to the project root directory.
    
    Returns:
        RepoMemory instance.
    """
    global _repo_memory
    if _repo_memory is None or _repo_memory.project_root != project_root:
        _repo_memory = RepoMemory(project_root=project_root)
        _repo_memory.load()
    return _repo_memory


def load_repo_memory(project_root: str = ".") -> RepoMemory:
    """Load repo memory from the given project root.
    
    Args:
        project_root: Path to the project root directory.
    
    Returns:
        Loaded RepoMemory instance.
    """
    return get_repo_memory(project_root)
