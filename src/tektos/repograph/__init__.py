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
]
