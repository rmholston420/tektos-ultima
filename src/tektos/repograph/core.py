"""Repograph — AST-driven codebase knowledge graph.

Uses tree-sitter to parse source files into semantic structure,
building a dependency graph of symbols, imports, calls, and types.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class SymbolKind(Enum):
    """Types of code symbols."""
    MODULE = auto()
    FUNCTION = auto()
    CLASS = auto()
    METHOD = auto()
    VARIABLE = auto()
    TYPE = auto()
    IMPORT = auto()
    CALL = auto()


class DependencyKind(Enum):
    """Types of relationships between symbols."""
    IMPORT = auto()      # file A imports file B
    CALL = auto()        # function A calls function B
    INHERIT = auto()     # class A inherits from class B
    TYPE_REF = auto()    # type annotation references another type
    ASSIGN = auto()      # assignment creates a dependency
    COMPOSE = auto()     # composition/aggregation relationship


@dataclass
class Symbol:
    """A single symbol (function, class, method, etc.)."""
    name: str
    kind: str  # SymbolKind as string for JSON serialization
    file: str
    line: int
    column: int
    visibility: str  # public, protected, private
    signature: str = ""
    docstring: str = ""
    module: str = ""  # dotted module path


@dataclass
class Dependency:
    """A dependency between two symbols."""
    source: str  # e.g., "src/tektos/runtime/session.py::LiveSession.create_session"
    target: str  # e.g., "src/tektos/store/event_store.py::EventStore.record_event"
    kind: str    # DependencyKind as string


@dataclass
class FileNode:
    """A file in the repository."""
    path: str
    language: str
    lines: int
    symbols: list[dict] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)
    importance: float = 0.0


class RepographParser:
    """Parse source files using tree-sitter (or fallback to AST module)."""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self._python_parser = None
        self._ts_parser = None

    def parse_file(self, filepath: Path) -> list[Symbol]:
        """Parse a single file and return symbols."""
        symbols = []
        try:
            if filepath.suffix == '.py':
                symbols = self._parse_python(filepath)
            elif filepath.suffix in ('.ts', '.tsx', '.js', '.jsx'):
                symbols = self._parse_typescript(filepath)
            # Add more language parsers as needed
        except Exception as e:
            log.warning(f"Failed to parse {filepath}: {e}")
        return symbols

    def _parse_python(self, filepath: Path) -> list[Symbol]:
        """Parse a Python file using the AST module (tree-sitter optional)."""
        symbols = []
        try:
            import ast
            import textwrap

            source = filepath.read_text()
            source = textwrap.dedent(source)
            tree = ast.parse(source, filename=str(filepath))

            # Process top-level definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    symbols.append(Symbol(
                        name=node.name,
                        kind=SymbolKind.FUNCTION.name,
                        file=str(filepath.relative_to(self.repo_root)),
                        line=node.lineno,
                        column=node.col_offset,
                        visibility="public" if not node.name.startswith('_') else "private",
                        signature=self._get_function_signature(node),
                        docstring=ast.get_docstring(node) or "",
                        module=self._get_module_name(filepath)
                    ))
                elif isinstance(node, ast.ClassDef):
                    symbols.append(Symbol(
                        name=node.name,
                        kind=SymbolKind.CLASS.name,
                        file=str(filepath.relative_to(self.repo_root)),
                        line=node.lineno,
                        column=node.col_offset,
                        visibility="public" if not node.name.startswith('_') else "private",
                        signature=f"class {node.name}",
                        docstring=ast.get_docstring(node) or "",
                        module=self._get_module_name(filepath)
                    ))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        symbols.append(Symbol(
                            name=alias.name,
                            kind=SymbolKind.IMPORT.name,
                            file=str(filepath.relative_to(self.repo_root)),
                            line=node.lineno,
                            column=node.col_offset,
                            visibility="public",
                            signature=f"import {alias.name}",
                            module=self._get_module_name(filepath)
                        ))
                elif isinstance(node, ast.ImportFrom):
                    symbols.append(Symbol(
                        name=f"from {node.module}",
                        kind=SymbolKind.IMPORT.name,
                        file=str(filepath.relative_to(self.repo_root)),
                        line=node.lineno,
                        column=node.col_offset,
                        visibility="public",
                        signature=f"from {node.module} import ...",
                        module=self._get_module_name(filepath)
                    ))

            # Add module symbol
            symbols.insert(0, Symbol(
                name=self._get_module_name(filepath),
                kind=SymbolKind.MODULE.name,
                file=str(filepath.relative_to(self.repo_root)),
                line=1,
                column=0,
                visibility="public",
                signature=f"module {filepath.name}",
                module=self._get_module_name(filepath)
            ))

        except Exception as e:
            log.error(f"Error parsing Python file {filepath}: {e}")

        return symbols

    def _parse_typescript(self, filepath: Path) -> list[Symbol]:
        """Parse TypeScript/JavaScript files (basic implementation)."""
        symbols = []
        try:
            source = filepath.read_text()
            lines = source.split('\n')

            for i, line in enumerate(lines, 1):
                # Functions
                if 'function ' in line or 'async function ' in line:
                    name = self._extract_name(line, 'function')
                    if name:
                        symbols.append(Symbol(
                            name=name,
                            kind=SymbolKind.FUNCTION.name,
                            file=str(filepath.relative_to(self.repo_root)),
                            line=i,
                            column=line.find(name),
                            visibility="public",
                            signature=line.strip(),
                            module=self._get_module_name(filepath)
                        ))
                # Classes
                elif line.strip().startswith('class '):
                    name = line.strip().split('class ')[1].split('(')[0].split(':')[0].split('{')[0].strip()
                    symbols.append(Symbol(
                        name=name,
                        kind=SymbolKind.CLASS.name,
                        file=str(filepath.relative_to(self.repo_root)),
                        line=i,
                        column=line.find('class'),
                        visibility="public",
                        signature=line.strip(),
                        module=self._get_module_name(filepath)
                    ))

        except Exception as e:
            log.error(f"Error parsing TypeScript file {filepath}: {e}")

        return symbols

    def _get_function_signature(self, node) -> str:
        """Extract function signature from AST node."""
        import ast
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.dump(arg.annotation)}"
            args.append(arg_str)
        return f"def {node.name}({', '.join(args)})"

    def _extract_name(self, line: str, keyword: str) -> str:
        """Extract name after a keyword (function, class, etc.)."""
        parts = line.split(keyword, 1)
        if len(parts) > 1:
            return parts[1].strip().split('(')[0].split(':')[0].strip()
        return ""

    def _get_module_name(self, filepath: Path) -> str:
        """Convert file path to dotted module name."""
        parts = filepath.relative_to(self.repo_root).with_suffix('').parts
        return '.'.join(parts)


class RepographGraph:
    """Build and maintain the dependency graph."""

    def __init__(self):
        self.nodes: dict[str, FileNode] = {}  # path -> FileNode
        self.edges: list[Dependency] = []  # list of dependencies
        self.symbols: dict[str, Symbol] = {}  # "file::symbol_name" -> Symbol

    def add_file(self, filepath: str, language: str, symbols: list[Symbol], imports: list[str]):
        """Add a file to the graph."""
        self.nodes[filepath] = FileNode(
            path=filepath,
            language=language,
            lines=0,  # Will be set by sync
            symbols=[asdict(s) for s in symbols],
            imports=imports,
        )
        for sym in symbols:
            key = f"{filepath}::{sym.name}"
            self.symbols[key] = sym

    def add_dependency(self, source: str, target: str, kind: DependencyKind):
        """Add a dependency edge."""
        self.edges.append(Dependency(
            source=source,
            target=target,
            kind=kind.name
        ))

    def find_dependencies(self, filepath: str) -> list[str]:
        """Find files that depend on the given file."""
        dependents = []
        for edge in self.edges:
            if edge.target == filepath or filepath in edge.target:
                dependents.append(edge.source)
        return list(set(dependents))

    def find_dependents(self, filepath: str) -> list[str]:
        """Find files that the given file depends on."""
        dependents = []
        for edge in self.edges:
            if edge.source == filepath or filepath in edge.source:
                dependents.append(edge.target)
        return list(set(dependents))

    def get_callers(self, symbol_name: str) -> list[str]:
        """Find all symbols that call the given symbol."""
        callers = []
        for edge in self.edges:
            if symbol_name in edge.target and edge.kind == DependencyKind.CALL.name:
                callers.append(edge.source)
        return callers

    def get_callees(self, symbol_name: str) -> list[str]:
        """Find all symbols called by the given symbol."""
        callees = []
        for edge in self.edges:
            if symbol_name in edge.source and edge.kind == DependencyKind.CALL.name:
                callees.append(edge.target)
        return callees

    def serialize(self) -> dict[str, Any]:
        """Serialize the graph to a dict."""
        return {
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "edges": [asdict(e) for e in self.edges],
            "symbols": {k: asdict(v) for k, v in self.symbols.items()},
        }

    def save(self, path: Path):
        """Save graph to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.serialize()
        data["metadata"] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "total_symbols": len(self.symbols),
        }
        path.write_text(json.dumps(data, indent=2))


class PageRankCalculator:
    """Calculate PageRank-style importance scores for symbols."""

    def __init__(self, graph: RepographGraph, damping: float = 0.85):
        self.graph = graph
        self.damping = damping

    def calculate(self) -> dict[str, float]:
        """Calculate PageRank for all symbols."""
        # Initialize scores
        scores = {node: 1.0 / len(self.graph.nodes) for node in self.graph.nodes}

        # Iterate PageRank algorithm
        for _ in range(10):  # 10 iterations should converge
            new_scores = {}
            for node in self.graph.nodes:
                rank = (1 - self.damping) / len(self.graph.nodes)
                # Find incoming edges
                for edge in self.graph.edges:
                    if node in edge.target:
                        source_score = scores.get(edge.source, 0)
                        # Divide by out-degree of source
                        out_degree = sum(1 for e in self.graph.edges if e.source == edge.source)
                        rank += self.damping * source_score / max(out_degree, 1)
                new_scores[node] = rank
            scores = new_scores

        return scores

    def apply_scores(self):
        """Apply importance scores to nodes."""
        scores = self.calculate()
        for node in self.graph.nodes:
            self.graph.nodes[node].importance = scores.get(node, 0)


class RepographQuery:
    """Query interface for the repograph."""

    def __init__(self, graph: RepographGraph):
        self.graph = graph

    def find_symbol(self, name: str) -> list[Symbol]:
        """Find all symbols with the given name."""
        return [s for s in self.graph.symbols.values() if s.name == name]

    def find_callers(self, symbol_name: str) -> list[str]:
        """Find all symbols that call the given symbol."""
        return self.graph.get_callers(symbol_name)

    def find_dependents(self, symbol_name: str) -> list[str]:
        """Find all symbols called by the given symbol."""
        return self.graph.get_callees(symbol_name)

    def blast_radius(self, filepath: str) -> list[str]:
        """Find all files affected by changes to the given file."""
        affected = set()
        queue = [filepath]
        while queue:
            current = queue.pop(0)
            if current in affected:
                continue
            affected.add(current)
            # Find files that DEPEND ON this file (i.e., files that call/import this file)
            for dependent in self.graph.find_dependencies(current):
                if dependent not in affected:
                    queue.append(dependent)
        return list(affected - {filepath})

    def find_imports(self, filepath: str) -> list[str]:
        """Find all imports in a file."""
        node = self.graph.nodes.get(filepath)
        return node.imports if node else []

    def call_chain(self, symbol_name: str, max_depth: int = 5) -> list[str]:
        """Trace the call chain starting from a symbol."""
        chain = [symbol_name]
        visited = {symbol_name}
        current_level = [symbol_name]

        for _ in range(max_depth):
            next_level = []
            for symbol in current_level:
                callees = self.graph.get_callees(symbol)
                for callee in callees:
                    if callee not in visited:
                        visited.add(callee)
                        next_level.append(callee)
                        chain.append(callee)
            if not next_level:
                break
            current_level = next_level

        return chain

    def to_markdown(self) -> str:
        """Generate a human-readable Markdown report."""
        lines = [
            "# Repograph Report",
            "",
            f"**Total Nodes:** {len(self.graph.nodes)}",
            f"**Total Edges:** {len(self.graph.edges)}",
            f"**Total Symbols:** {len(self.graph.symbols)}",
            "",
            "## Nodes by Language",
            "",
        ]

        lang_counts = {}
        for node in self.graph.nodes.values():
            lang_counts[node.language] = lang_counts.get(node.language, 0) + 1

        for lang, count in sorted(lang_counts.items()):
            lines.append(f"- {lang}: {count}")

        lines.extend(["", "## Top Symbols by Importance", ""])
        sorted_nodes = sorted(self.graph.nodes.items(), key=lambda x: x[1].importance, reverse=True)
        for path, node in sorted_nodes[:20]:  # Top 20
            lines.append(f"- {node.importance:.4f} | {path}")

        return '\n'.join(lines)


class RepographSync:
    """Incremental sync for the repograph."""

    def __init__(self, graph: RepographGraph, repo_root: str):
        self.graph = graph
        self.repo_root = Path(repo_root)

    def get_diff(self) -> list[str]:
        """Get list of changed files from git diff."""
        try:
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD'],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return [f.strip() for f in result.stdout.split('\n') if f.strip()]
        except Exception as e:
            log.warning(f"Failed to get git diff: {e}")
        return []

    def rebuild_for_changes(self, changed_files: list[str], parser: RepographParser):
        """Rebuild graph for changed files and their dependents."""
        for filepath in changed_files:
            full_path = self.repo_root / filepath
            if full_path.exists():
                symbols = parser.parse_file(full_path)
                self.graph.add_file(
                    filepath=filepath,
                    language=self._detect_language(full_path),
                    symbols=symbols,
                    imports=[]  # Will be populated by parser
                )

    def _detect_language(self, filepath: Path) -> str:
        """Detect file language from extension."""
        ext_map = {
            '.py': 'python',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.js': 'javascript',
            '.jsx': 'javascript',
        }
        return ext_map.get(filepath.suffix, 'unknown')

    def full_rebuild(self, parser: RepographParser):
        """Rebuild the entire graph."""
        self.graph = RepographGraph()
        for filepath in self.repo_root.rglob('*.py'):
            try:
                symbols = parser.parse_file(filepath)
                self.graph.add_file(
                    filepath=str(filepath.relative_to(self.repo_root)),
                    language='python',
                    symbols=symbols,
                    imports=[]
                )
            except Exception as e:
                log.warning(f"Failed to rebuild {filepath}: {e}")
