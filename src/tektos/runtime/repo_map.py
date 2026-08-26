"""RepoMap - Maintain a map of the repository structure and dependencies."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class FileNode:
    """A node in the repository map."""
    path: str
    type: str  # "file", "directory", "symlink"
    size: int = 0
    dependencies: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class RepoMap:
    """Maintains a map of the repository structure and dependencies."""

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = project_root
        self._nodes: dict[str, FileNode] = {}
        self._build_map()

    def _build_map(self) -> None:
        """Build the repository map by scanning the project root."""
        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden directories and common non-source dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', '.git', 'venv', '.venv')]
            
            for file in files:
                if file.endswith('.py') or file.endswith('.js') or file.endswith('.ts'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.project_root)
                    
                    node = FileNode(
                        path=rel_path,
                        type="file",
                        size=os.path.getsize(full_path),
                    )
                    
                    # Extract imports for Python files
                    if file.endswith('.py'):
                        try:
                            with open(full_path, 'r') as f:
                                content = f.read(10000)  # Read first 10KB
                            for line in content.split('\n'):
                                line = line.strip()
                                if line.startswith('import ') or line.startswith('from '):
                                    node.imports.append(line)
                        except Exception:
                            pass
                    
                    self._nodes[rel_path] = node

    def get_node(self, path: str) -> FileNode | None:
        """Get a node by path."""
        return self._nodes.get(path)

    def get_all_nodes(self) -> dict[str, FileNode]:
        """Get all nodes."""
        return dict(self._nodes)

    def get_dependencies(self, path: str) -> list[str]:
        """Get dependencies for a file."""
        node = self._nodes.get(path)
        return node.dependencies if node else []

    def get_imports(self, path: str) -> list[str]:
        """Get imports for a file."""
        node = self._nodes.get(path)
        return node.imports if node else []

    def get_file_count(self) -> int:
        """Get the number of files in the map."""
        return len(self._nodes)

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "total_files": len(self._nodes),
            "project_root": self.project_root,
            "recent_files": list(self._nodes.keys())[-20:],
        }


_repo_map: RepoMap | None = None


def get_repo_map(project_root: str = ".") -> RepoMap:
    """Get or create the repo map."""
    global _repo_map
    if _repo_map is None or _repo_map.project_root != project_root:
        _repo_map = RepoMap(project_root=project_root)
    return _repo_map
