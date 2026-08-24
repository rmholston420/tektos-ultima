"""File-based memory system - CLAUDE.md style persistent context.

This module implements a file-based memory system inspired by Claude Code's
CLAUDE.md approach. It provides:
- Persistent context storage in markdown files
- Automatic context loading on session start
- Incremental updates to memory files
- Cross-session knowledge retention
- Structured memory categories (preferences, corrections, patterns, etc.)
- Embedding-based semantic recall for finding relevant memories
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.tektos.runtime.embedder import EmbedderClient

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """A single memory entry."""

    category: str  # 'preference', 'correction', 'pattern', 'knowledge', 'context'
    content: str
    created_at: str = ""
    updated_at: str = ""
    confidence: float = 1.0
    source: str = ""  # Where this memory came from

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class MemoryFile:
    """A memory file (like CLAUDE.md)."""

    path: str
    entries: list[MemoryEntry] = field(default_factory=list)
    last_modified: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.last_modified:
            self.last_modified = datetime.now(timezone.utc).isoformat()


class FileBasedMemory:
    """File-based memory system with CLAUDE.md style persistence.

    This is the third-highest-ROI improvement because it provides:
    - Cross-session knowledge retention
    - Structured memory categories
    - Automatic context loading
    - Incremental updates
    - Human-readable format
    """

    def __init__(
        self,
        memory_dir: str = "./memory",
        project_root: str = ".",
        embedder_client: EmbedderClient | None = None,
    ) -> None:
        """Initialize the file-based memory system.

        Args:
            memory_dir: Directory to store memory files.
            project_root: Project root directory.
            embedder_client: Optional EmbedderClient for semantic recall.
        """
        self.memory_dir = Path(memory_dir)
        self.project_root = Path(project_root)
        self.memory_files: dict[str, MemoryFile] = {}
        self._init_memory_files()
        self._embedder = embedder_client
        self._embedding_cache: dict[str, list[float]] = {}

    def _init_memory_files(self) -> None:
        """Initialize standard memory files."""
        # Create standard memory files
        standard_files = {
            "preferences": "User preferences and coding style",
            "corrections": "Corrections and feedback from user",
            "patterns": "Recurring patterns and solutions",
            "knowledge": "Technical knowledge and insights",
            "context": "Project context and constraints",
        }

        for filename, description in standard_files.items():
            file_path = self.memory_dir / f"{filename}.md"
            if file_path.exists():
                self.memory_files[filename] = self._load_memory_file(file_path)
            else:
                self.memory_files[filename] = MemoryFile(
                    path=str(file_path),
                    description=description,
                )

    def _load_memory_file(self, file_path: Path) -> MemoryFile:
        """Load a memory file from disk.

        Args:
            file_path: Path to the memory file.

        Returns:
            MemoryFile with loaded entries.
        """
        try:
            content = file_path.read_text(encoding='utf-8')
            entries = self._parse_memory_file(content)
            return MemoryFile(
                path=str(file_path),
                entries=entries,
                last_modified=str(file_path.stat().st_mtime),
            )
        except OSError as e:
            logger.warning(f"Failed to load memory file {file_path}: {e}")
            return MemoryFile(path=str(file_path))

    def _parse_memory_file(self, content: str) -> list[MemoryEntry]:
        """Parse a memory file into entries.

        Args:
            content: File content.

        Returns:
            List of MemoryEntry objects.
        """
        entries = []
        current_category = "context"
        current_content = []

        for line in content.split('\n'):
            if line.startswith('## '):
                # Save previous entry
                if current_content:
                    entries.append(MemoryEntry(
                        category=current_category,
                        content='\n'.join(current_content),
                    ))
                    current_content = []

                # Extract category from heading
                current_category = line[3:].strip().lower()
            elif line.startswith('- '):
                current_content.append(line[2:])
            elif line.strip() and not line.startswith('#'):
                current_content.append(line)

        # Save last entry
        if current_content:
            entries.append(MemoryEntry(
                category=current_category,
                content='\n'.join(current_content),
            ))

        return entries

    def add_memory(self, category: str, content: str, source: str = "") -> None:
        """Add a memory entry.

        Args:
            category: Memory category.
            content: Memory content.
            source: Source of the memory.
        """
        # Find or create memory file for category
        filename = category.lower() + ".md"
        if filename not in self.memory_files:
            self.memory_files[filename] = MemoryFile(
                path=str(self.memory_dir / filename),
                description=f"{category} memory",
            )

        # Add entry
        entry = MemoryEntry(
            category=category,
            content=content,
            source=source,
        )
        self.memory_files[filename].entries.append(entry)
        self.memory_files[filename].last_modified = datetime.now(timezone.utc).isoformat()

        # Save to disk
        self._save_memory_file(self.memory_files[filename])

    def _save_memory_file(self, memory_file: MemoryFile) -> None:
        """Save a memory file to disk.

        Args:
            memory_file: MemoryFile to save.
        """
        try:
            content = self._format_memory_file(memory_file)
            Path(memory_file.path).parent.mkdir(parents=True, exist_ok=True)
            Path(memory_file.path).write_text(content, encoding='utf-8')
        except OSError as e:
            logger.warning(f"Failed to save memory file {memory_file.path}: {e}")

    def _format_memory_file(self, memory_file: MemoryFile) -> str:
        """Format a memory file for disk storage.

        Args:
            memory_file: MemoryFile to format.

        Returns:
            Formatted markdown string.
        """
        lines = [f"# {memory_file.description}\n"]

        # Group entries by category
        categories: dict[str, list[MemoryEntry]] = {}
        for entry in memory_file.entries:
            if entry.category not in categories:
                categories[entry.category] = []
            categories[entry.category].append(entry)

        for category, entries in categories.items():
            lines.append(f"\n## {category.title()}\n")
            for entry in entries:
                lines.append(f"- {entry.content}")

        return "\n".join(lines)

    def get_memory(self, category: str | None = None) -> list[MemoryEntry]:
        """Get memory entries.

        Args:
            category: Optional category filter.

        Returns:
            List of MemoryEntry objects.
        """
        if category:
            filename = category.lower() + ".md"
            if filename in self.memory_files:
                return self.memory_files[filename].entries
            return []

        # Return all entries
        all_entries = []
        for memory_file in self.memory_files.values():
            all_entries.extend(memory_file.entries)
        return all_entries

    def get_context_prompt(self) -> str:
        """Get a context prompt with all memory entries.

        Returns:
            Formatted context prompt for the agent.
        """
        parts = ["# Project Memory\n"]

        for filename, memory_file in self.memory_files.items():
            if memory_file.entries:
                parts.append(f"\n## {memory_file.description}\n")
                for entry in memory_file.entries:
                    parts.append(f"- {entry.content}")

        return "\n".join(parts)

    def update_memory(self, category: str, content: str, source: str = "") -> None:
        """Update existing memory or add new entry.

        Args:
            category: Memory category.
            content: Memory content.
            source: Source of the memory.
        """
        # Check if similar entry exists
        existing_entries = self.get_memory(category)
        for entry in existing_entries:
            if content.lower() in entry.content.lower() or entry.content.lower() in content.lower():
                # Update existing entry
                entry.content = content
                entry.updated_at = datetime.now(timezone.utc).isoformat()
                entry.source = source
                return

        # Add new entry
        self.add_memory(category, content, source)

    def get_memory_stats(self) -> dict[str, Any]:
        """Get statistics about memory usage.

        Returns:
            Dictionary with memory statistics.
        """
        total_entries = sum(len(mf.entries) for mf in self.memory_files.values())
        categories = list(self.memory_files.keys())

        return {
            "total_entries": total_entries,
            "categories": categories,
            "memory_files": len(self.memory_files),
        }

    async def _get_embedding(self, text: str) -> list[float] | None:
        """Get embedding for text, using cache if available.

        Args:
            text: Text to embed.

        Returns:
            Embedding vector, or None if embedder unavailable.
        """
        if self._embedder is None:
            return None
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        try:
            result = await self._embedder.embed(text)
            if result.embeddings:
                vec = result.embeddings[0]
                self._embedding_cache[text] = vec
                return vec
        except Exception as e:
            logger.debug(f"Embedding failed for '{text[:50]}...': {e}")
        return None

    async def semantic_recall(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """Find memory entries most similar to a query using embeddings.

        Args:
            query: Search query text.
            top_k: Number of results to return.

        Returns:
            List of MemoryEntry objects, ordered by relevance.
        """
        if self._embedder is None:
            # Fallback: keyword matching
            return self._keyword_recall(query, top_k)

        # Collect all entries with their text
        all_entries: list[tuple[str, MemoryEntry]] = []
        for entry in self.get_memory():
            text = f"[{entry.category}] {entry.content}"
            all_entries.append((text, entry))

        if not all_entries:
            return []

        # Embed query and all entries
        query_vec = await self._get_embedding(query)
        if query_vec is None:
            return self._keyword_recall(query, top_k)

        # Embed all entries (batch if possible)
        texts = [t for t, _ in all_entries]
        entry_vecs: list[list[float]] = []
        for text in texts:
            vec = await self._get_embedding(text)
            if vec is not None:
                entry_vecs.append(vec)

        if not entry_vecs:
            return self._keyword_recall(query, top_k)

        # Compute cosine similarity
        from src.tektos.runtime.embedder import cosine_similarity
        scored: list[tuple[float, MemoryEntry]] = []
        for i, vec in enumerate(entry_vecs):
            sim = cosine_similarity(query_vec, vec)
            scored.append((sim, all_entries[i][1]))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def _keyword_recall(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """Fallback keyword-based recall when embedder is unavailable.

        Args:
            query: Search query text.
            top_k: Number of results to return.

        Returns:
            List of MemoryEntry objects, ordered by relevance.
        """
        query_lower = query.lower()
        scored: list[tuple[int, MemoryEntry]] = []
        for entry in self.get_memory():
            text = f"{entry.category} {entry.content}".lower()
            score = sum(1 for word in query_lower.split() if word in text)
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]
