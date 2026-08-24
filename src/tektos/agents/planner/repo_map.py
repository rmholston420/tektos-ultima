"""Repository map generator using Tree-sitter for codebase understanding.

This module provides AST-based codebase analysis, giving the agent
deep understanding of the project structure, dependencies, and code
relationships — similar to how Claude Code and Aider use tree-sitter
for repo map generation.

Key features:
- AST parsing of Python files
- Dependency graph construction
- Symbol extraction (classes, functions, methods)
- File structure mapping
- Context-aware file relevance scoring
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tree_sitter_python as tspython
    import tree_sitter as ts

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class SymbolInfo:
    """Information about a code symbol (class, function, method)."""

    name: str
    kind: str  # 'class', 'function', 'method', 'variable', 'import'
    file_path: str
    line_start: int
    line_end: int
    parameters: list[str] = field(default_factory=list)
    return_type: str = ""
    docstring: str = ""
    dependencies: list[str] = field(default_factory=list)


@dataclass
class FileInfo:
    """Information about a source file."""

    path: str
    language: str
    size_bytes: int
    line_count: int
    symbols: list[SymbolInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    last_modified: str = ""


@dataclass
class RepoMap:
    """Complete repository map with AST-based analysis."""

    root_path: str
    files: dict[str, FileInfo] = field(default_factory=dict)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    symbol_index: dict[str, list[SymbolInfo]] = field(default_factory=dict)
    total_files: int = 0
    total_symbols: int = 0
    languages: dict[str, int] = field(default_factory=dict)


class RepoMapGenerator:
    """Generate a comprehensive repository map using Tree-sitter AST parsing.

    This is the highest-ROI improvement for Tektos because it gives the
    agent deep understanding of the codebase structure, enabling:
    - Smart file selection (only read relevant files)
    - Dependency-aware planning (understand import relationships)
    - Symbol-aware code generation (know what classes/functions exist)
    - Context-efficient operations (avoid reading irrelevant files)
    """

    def __init__(self, root_path: str, max_files: int = 500) -> None:
        """Initialize the repo map generator.

        Args:
            root_path: Root directory of the repository.
            max_files: Maximum number of files to analyze.
        """
        self.root_path = Path(root_path)
        self.max_files = max_files
        self.parser: Any = None
        self._init_parser()

    def _init_parser(self) -> None:
        """Initialize the Tree-sitter parser."""
        if not TREE_SITTER_AVAILABLE:
            logger.warning("Tree-sitter not available, using fallback parser")
            return

        try:
            # tree-sitter-python provides the Python grammar
            _tspython = tspython  # type: ignore[attr-defined]
            _ts = ts  # type: ignore[assignment]
            # Try different API versions
            try:
                grammar = _tspython.language()
            except AttributeError:
                grammar = _tspython.language_python()  # type: ignore[attr-defined]
            language = _ts.Language(grammar)
            self.parser = _ts.Parser(language)
        except Exception as e:
            logger.warning(f"Failed to initialize Tree-sitter parser: {e}")
            self.parser = None

    def generate_map(self) -> RepoMap:
        """Generate a complete repository map.

        Returns:
            RepoMap containing the full codebase analysis.
        """
        repo_map = RepoMap(root_path=str(self.root_path))

        # Find all Python files
        python_files = sorted(self.root_path.rglob("*.py"))
        other_files = sorted(self.root_path.rglob("*"))

        # Filter to relevant files (exclude venv, .git, __pycache__, etc.)
        relevant_files = [
            f for f in python_files
            if not any(part.startswith('.') or part == '__pycache__' or part == 'venv'
                      for part in f.parts)
        ][:self.max_files]

        repo_map.total_files = len(relevant_files)

        # Analyze each file
        for file_path in relevant_files:
            try:
                file_info = self._analyze_file(file_path)
                if file_info:
                    rel_path = str(file_path.relative_to(self.root_path))
                    repo_map.files[rel_path] = file_info
                    repo_map.languages[file_info.language] = (
                        repo_map.languages.get(file_info.language, 0) + 1
                    )

                    # Build symbol index
                    for symbol in file_info.symbols:
                        if symbol.name not in repo_map.symbol_index:
                            repo_map.symbol_index[symbol.name] = []
                        repo_map.symbol_index[symbol.name].append(symbol)

                    repo_map.total_symbols += len(file_info.symbols)

            except Exception as e:
                logger.debug(f"Failed to analyze {file_path}: {e}")

        # Build dependency graph
        self._build_dependency_graph(repo_map)

        # Store the map for later access
        self._last_map = repo_map

        return repo_map

    def _analyze_file(self, file_path: Path) -> FileInfo | None:
        """Analyze a single file using Tree-sitter AST.

        Args:
            file_path: Path to the file to analyze.

        Returns:
            FileInfo with AST-based analysis, or None if analysis failed.
        """
        try:
            content = file_path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            return None

        file_info = FileInfo(
            path=str(file_path),
            language="python",
            size_bytes=file_path.stat().st_size,
            line_count=len(content.split('\n')),
            last_modified=str(file_path.stat().st_mtime),
        )

        # Parse with Tree-sitter if available
        if self.parser and TREE_SITTER_AVAILABLE:
            try:
                tree = self.parser.parse(bytes(content, 'utf-8'))
                self._extract_symbols(tree, file_info, content)
                self._extract_imports(tree, file_info)
            except Exception as e:
                logger.debug(f"Tree-sitter parse failed for {file_path}: {e}")
                # Fallback to regex-based extraction
                self._extract_symbols_regex(file_info, content)
        else:
            # Fallback to regex-based extraction
            self._extract_symbols_regex(file_info, content)

        return file_info

    def _extract_symbols(self, tree: Any, file_info: FileInfo, content: str) -> None:
        """Extract symbols from Tree-sitter AST.

        Args:
            tree: Parsed AST tree.
            file_info: FileInfo to populate.
            content: Original file content.
        """
        lines = content.split('\n')

        def traverse(node: Any) -> None:
            if node.type == 'class_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = name_node.text.decode('utf-8')
                    file_info.symbols.append(SymbolInfo(
                        name=name,
                        kind='class',
                        file_path=file_info.path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        docstring=self._get_docstring(node, lines),
                    ))

            elif node.type == 'function_definition':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = name_node.text.decode('utf-8')
                    params = []
                    params_node = node.child_by_field_name('parameters')
                    if params_node:
                        for param in params_node.children:
                            if param.type == 'identifier':
                                params.append(param.text.decode('utf-8'))

                    return_type = ""
                    annotation = node.child_by_field_name('return_type')
                    if annotation:
                        return_type = annotation.text.decode('utf-8')

                    file_info.symbols.append(SymbolInfo(
                        name=name,
                        kind='function' if not name.startswith('__') else 'method',
                        file_path=file_info.path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        parameters=params,
                        return_type=return_type,
                        docstring=self._get_docstring(node, lines),
                    ))

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)

    def _extract_imports(self, tree: Any, file_info: FileInfo) -> None:
        """Extract import statements from AST.

        Args:
            tree: Parsed AST tree.
            file_info: FileInfo to populate.
        """
        def traverse(node: Any) -> None:
            if node.type == 'import_statement':
                for child in node.children:
                    if child.type == 'dotted_name':
                        file_info.imports.append(child.text.decode('utf-8'))
            elif node.type == 'import_from_statement':
                module = child_by_field_name('module_name')
                if module:
                    file_info.imports.append(f"from {module.text.decode('utf-8')}")

            for child in node.children:
                traverse(child)

        traverse(tree.root_node)

    def _extract_symbols_regex(self, file_info: FileInfo, content: str) -> None:
        """Fallback regex-based symbol extraction.

        Args:
            file_info: FileInfo to populate.
            content: File content.
        """
        lines = content.split('\n')

        # Extract classes
        for match in re.finditer(r'^class\s+(\w+)', content, re.MULTILINE):
            line_num = content[:match.start()].count('\n') + 1
            file_info.symbols.append(SymbolInfo(
                name=match.group(1),
                kind='class',
                file_path=file_info.path,
                line_start=line_num,
                line_end=line_num + 1,
            ))

        # Extract functions
        for match in re.finditer(r'^def\s+(\w+)\(([^)]*)\)', content, re.MULTILINE):
            line_num = content[:match.start()].count('\n') + 1
            params = [p.strip().split(':')[0].split('=')[0].strip()
                     for p in match.group(2).split(',') if p.strip()]
            file_info.symbols.append(SymbolInfo(
                name=match.group(1),
                kind='function' if not match.group(1).startswith('__') else 'method',
                file_path=file_info.path,
                line_start=line_num,
                line_end=line_num + 1,
                parameters=params,
            ))

        # Extract imports
        for match in re.finditer(r'^(?:from\s+(\S+)\s+)?import\s+(.+)$', content, re.MULTILINE):
            module = match.group(1) or match.group(2).split(',')[0]
            file_info.imports.append(module.strip())

    def _get_docstring(self, node: Any, lines: list[str]) -> str:
        """Extract docstring from a node.

        Args:
            node: AST node.
            lines: File lines.

        Returns:
            Docstring text.
        """
        # Look for first child that is a string literal (docstring)
        for child in node.children:
            if child.type in ('string', 'string_literal'):
                return child.text.decode('utf-8', errors='replace').strip()
        return ""

    def _build_dependency_graph(self, repo_map: RepoMap) -> None:
        """Build a dependency graph from import relationships.

        Args:
            repo_map: RepoMap to populate.
        """
        for file_path, file_info in repo_map.files.items():
            deps = []
            for imp in file_info.imports:
                # Simple heuristic: convert import to file path
                if imp.startswith('src.'):
                    dep_path = imp.replace('.', '/') + '.py'
                    if dep_path in repo_map.files:
                        deps.append(dep_path)
                elif imp.startswith('src/'):
                    if imp + '.py' in repo_map.files:
                        deps.append(imp + '.py')
            repo_map.dependency_graph[file_path] = deps

    def get_relevant_files(self, query: str, top_k: int = 10) -> list[str]:
        """Find files relevant to a query using symbol matching.

        Args:
            query: Search query (class name, function name, etc.).
            top_k: Number of relevant files to return.

        Returns:
            List of relevant file paths.
        """
        query_lower = query.lower()
        scores: dict[str, float] = {}

        # Check symbol index (from the last generated map)
        if hasattr(self, '_last_map') and self._last_map:
            for symbol_name, symbols in self._last_map.symbol_index.items():
                if query_lower in symbol_name.lower():
                    for symbol in symbols:
                        file_path = symbol.file_path
                        scores[file_path] = scores.get(file_path, 0) + 1.0

            # Check file content for direct mentions
            for file_path, file_info in self._last_map.files.items():
                try:
                    content = Path(file_info.path).read_text(encoding='utf-8', errors='replace')
                    if query_lower in content.lower():
                        scores[file_path] = scores.get(file_path, 0) + 0.5
                except OSError:
                    pass

        # Sort by score and return top_k
        sorted_files = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [f[0] for f in sorted_files[:top_k]]

    def get_file_summary(self, file_path: str) -> str:
        """Get a summary of a file's structure.

        Args:
            file_path: Path to the file.

        Returns:
            Formatted summary of the file.
        """
        if file_path not in self.files:
            return f"File not found: {file_path}"

        file_info = self.files[file_path]
        summary = f"## {file_path}\n"
        summary += f"- Language: {file_info.language}\n"
        summary += f"- Lines: {file_info.line_count}\n"
        summary += f"- Size: {file_info.size_bytes} bytes\n"
        summary += f"- Symbols: {len(file_info.symbols)}\n"
        summary += f"- Imports: {len(file_info.imports)}\n"

        if file_info.symbols:
            summary += "\n### Symbols\n"
            for symbol in file_info.symbols[:20]:  # Limit to 20 symbols
                summary += f"- {symbol.kind}: {symbol.name} (line {symbol.line_start})\n"

        return summary

    def get_dependency_chain(self, file_path: str, max_depth: int = 3) -> list[str]:
        """Get the dependency chain for a file.

        Args:
            file_path: Path to the file.
            max_depth: Maximum depth to traverse.

        Returns:
            List of file paths in dependency order.
        """
        visited = set()
        chain = []

        def traverse(path: str, depth: int) -> None:
            if depth > max_depth or path in visited:
                return
            visited.add(path)
            chain.append(path)

            for dep in self.dependency_graph.get(path, []):
                traverse(dep, depth + 1)

        traverse(file_path, 0)
        return chain

    def generate_context_prompt(self, query: str) -> str:
        """Generate a context prompt with relevant file information.

        This is the key integration point — the agent can call this
        method to get a concise summary of the relevant parts of the
        codebase before starting work.

        Args:
            query: The task or query to find relevant context for.

        Returns:
            Formatted context prompt for the agent.
        """
        relevant_files = self.get_relevant_files(query, top_k=5)
        context_parts = []

        for file_path in relevant_files:
            summary = self.get_file_summary(file_path)
            context_parts.append(summary)

        if not context_parts:
            return f"No relevant files found for query: {query}"

        return (
            f"# Codebase Context for: {query}\n\n"
            + "\n\n".join(context_parts)
            + "\n\n# End Context\n"
        )
