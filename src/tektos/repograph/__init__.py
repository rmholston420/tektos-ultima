"""Repograph — codebase knowledge graph.

Provides structural awareness of the codebase without reading every file.
Enables blast-radius analysis, cross-repository navigation, and architectural
reasoning in milliseconds.

Design:
- AST-driven using tree-sitter (or Python AST fallback)
- Lightweight JSON graph file (fast to build/load/diff)
- Incremental updates on commits or every 15 minutes
- Human-readable Markdown output AND structured JSON queries
- Tektos-native: integrates with event system
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .core import (
    RepographParser,
    RepographGraph,
    PageRankCalculator,
    RepographQuery,
    RepographSync,
    Symbol,
    SymbolKind,
    Dependency,
    DependencyKind,
    FileNode,
)


# ── Flat-file Repograph (from tektos/repograph.py) ──────────────────────────
# This is the Repograph class that main.py imports. It's a simple graph
# data structure, distinct from the tree-sitter-based RepographGraph in core.py.

@dataclass
class GraphNode:
    """A node in the repograph."""
    id: str
    label: str
    type: str  # "file", "module", "function", "class", "dependency"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge in the repograph."""
    source: str
    target: str
    relation: str  # "imports", "depends_on", "calls", "extends"
    metadata: dict[str, Any] = field(default_factory=dict)


class Repograph:
    """Graph-based representation of repository structure and relationships."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._adjacency: dict[str, list[str]] = {}

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph."""
        self._nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge to the graph."""
        self._edges.append(edge)
        self._adjacency.setdefault(edge.source, []).append(edge.target)

    def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> list[str]:
        """Get neighboring nodes."""
        return self._adjacency.get(node_id, [])

    def get_all_nodes(self) -> dict[str, GraphNode]:
        """Get all nodes."""
        return dict(self._nodes)

    def get_all_edges(self) -> list[GraphEdge]:
        """Get all edges."""
        return list(self._edges)

    def get_dependencies(self, node_id: str) -> list[str]:
        """Get dependencies for a node."""
        return [
            edge.target for edge in self._edges
            if edge.source == node_id and edge.relation in ("imports", "depends_on")
        ]

    def get_dependents(self, node_id: str) -> list[str]:
        """Get nodes that depend on this node."""
        return [
            edge.source for edge in self._edges
            if edge.target == node_id and edge.relation in ("imports", "depends_on")
        ]

    def get_node_count(self) -> int:
        """Get the number of nodes."""
        return len(self._nodes)

    def get_edge_count(self) -> int:
        """Get the number of edges."""
        return len(self._edges)

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to memory entry for self-improvement loop."""
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "node_types": {
                node_type: len([n for n in self._nodes.values() if n.type == node_type])
                for node_type in set(n.type for n in self._nodes.values())
            },
        }


_repograph: Repograph | None = None


def get_repograph() -> Repograph:
    """Get or create the repograph."""
    global _repograph
    if _repograph is None:
        _repograph = Repograph()
    return _repograph


__all__ = [
    "RepographParser",
    "RepographGraph",
    "PageRankCalculator",
    "RepographQuery",
    "RepographSync",
    "Symbol",
    "SymbolKind",
    "Dependency",
    "DependencyKind",
    "FileNode",
    "Repograph",
    "get_repograph",
    "GraphNode",
    "GraphEdge",
]
