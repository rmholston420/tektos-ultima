"""
Tektos-Ultima v1 — Repograph Tests

Tests AST-driven codebase knowledge graph:
- SymbolKind and DependencyKind enums
- Symbol, Dependency, FileNode dataclasses
- RepographParser Python parsing (functions, classes, imports)
- RepographGraph CRUD, serialization, save
- PageRankCalculator
- RepographQuery (find_symbol, blast_radius, call_chain, etc.)
- RepographSync (diff detection, language detection, rebuild)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tektos.repograph.core import (
    DependencyKind,
    PageRankCalculator,
    RepographGraph,
    RepographParser,
    RepographQuery,
    RepographSync,
    Symbol,
    SymbolKind,
    FileNode,
    Dependency,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_symbol_kinds(self):
        kinds = [e.name for e in SymbolKind]
        assert "MODULE" in kinds
        assert "FUNCTION" in kinds
        assert "CLASS" in kinds
        assert "METHOD" in kinds
        assert "VARIABLE" in kinds
        assert "TYPE" in kinds
        assert "IMPORT" in kinds
        assert "CALL" in kinds

    def test_dependency_kinds(self):
        kinds = [e.name for e in DependencyKind]
        assert "IMPORT" in kinds
        assert "CALL" in kinds
        assert "INHERIT" in kinds
        assert "TYPE_REF" in kinds
        assert "ASSIGN" in kinds
        assert "COMPOSE" in kinds


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_symbol_defaults(self):
        sym = Symbol(name="foo", kind="FUNCTION", file="test.py", line=1, column=0, visibility="public")
        assert sym.name == "foo"
        assert sym.kind == "FUNCTION"
        assert sym.file == "test.py"
        assert sym.line == 1
        assert sym.column == 0
        assert sym.visibility == "public"
        assert sym.signature == ""
        assert sym.docstring == ""
        assert sym.module == ""

    def test_dependency_defaults(self):
        dep = Dependency(source="a", target="b", kind="IMPORT")
        assert dep.source == "a"
        assert dep.target == "b"
        assert dep.kind == "IMPORT"

    def test_filenode_defaults(self):
        node = FileNode(path="test.py", language="python", lines=100)
        assert node.path == "test.py"
        assert node.language == "python"
        assert node.lines == 100
        assert node.symbols == []
        assert node.imports == []
        assert node.dependents == []
        assert node.importance == 0.0


# ---------------------------------------------------------------------------
# RepographParser — Python parsing
# ---------------------------------------------------------------------------


class TestRepographParser:
    def test_parse_python_function(self, tmp_path):
        """Parse a Python file with a function definition."""
        code = '''\
def hello(name):
    """Say hello."""
    return f"Hello, {name}"
'''
        f = tmp_path / "test_mod.py"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        names = [s.name for s in symbols]
        assert "hello" in names
        assert "test_mod" in names  # module symbol

    def test_parse_python_class(self, tmp_path):
        """Parse a Python file with a class definition."""
        code = '''\
class MyClass:
    """A test class."""
    pass
'''
        f = tmp_path / "test_cls.py"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        names = [s.name for s in symbols]
        assert "MyClass" in names

    def test_parse_python_import(self, tmp_path):
        """Parse a Python file with import statements."""
        code = '''\
import os
import sys as system
from pathlib import Path
'''
        f = tmp_path / "test_import.py"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        kinds = [s.kind for s in symbols]
        assert "IMPORT" in kinds

    def test_parse_python_async_function(self, tmp_path):
        """Parse async function definitions."""
        code = '''\
async def fetch():
    return None
'''
        f = tmp_path / "test_async.py"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        names = [s.name for s in symbols]
        assert "fetch" in names

    def test_parse_python_visibility(self, tmp_path):
        """Private names start with underscore → private visibility."""
        code = '''\
def _private_func():
    pass

def public_func():
    pass
'''
        f = tmp_path / "test_vis.py"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        sym_map = {s.name: s.visibility for s in symbols if s.kind == "FUNCTION"}
        assert sym_map.get("_private_func") == "private"
        assert sym_map.get("public_func") == "public"

    def test_parse_python_class_visibility(self, tmp_path):
        """Public class → public visibility."""
        code = '''\
class _Internal:
    pass

class PublicClass:
    pass
'''
        f = tmp_path / "test_vis2.py"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        sym_map = {s.name: s.visibility for s in symbols if s.kind == "CLASS"}
        assert sym_map.get("_Internal") == "private"
        assert sym_map.get("PublicClass") == "public"

    def test_parse_python_preserves_lines(self, tmp_path):
        """Parsed symbols should have correct line numbers."""
        code = '''\
class A:
    pass


def b():
    pass
'''
        f = tmp_path / "test_line.py"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        cls_sym = [s for s in symbols if s.name == "A"][0]
        func_sym = [s for s in symbols if s.name == "b"][0]
        assert cls_sym.line == 1
        assert func_sym.line == 5

    def test_parse_python_docstrings(self, tmp_path):
        """Docstrings are captured in symbols."""
        code = '''\
def documented():
    """This is documented."""
    pass
'''
        f = tmp_path / "test_doc.py"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        func_sym = [s for s in symbols if s.name == "documented"][0]
        assert func_sym.docstring == "This is documented."

    def test_parse_python_module_name(self, tmp_path):
        """Module name is computed from file path."""
        code = '''\
x = 1
'''
        f = tmp_path / "my_module.py"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        mod_sym = [s for s in symbols if s.kind == "MODULE"][0]
        assert mod_sym.name == "my_module"

    def test_parse_python_invalid_file_returns_empty(self, tmp_path):
        """Invalid Python file returns empty symbols list."""
        f = tmp_path / "bad.py"
        f.write_text("def (invalid python")
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        assert symbols == []

    def test_parse_python_function_signature(self, tmp_path):
        """Function signature includes argument names."""
        code = '''\
def add(a, b):
    return a + b
'''
        f = tmp_path / "test_sig.py"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        func_sym = [s for s in symbols if s.name == "add"][0]
        assert "def add" in func_sym.signature

    def test_parse_typescript_basic(self, tmp_path):
        """Parse TypeScript file for functions and classes."""
        code = '''\
function hello() {}
class World {}
'''
        f = tmp_path / "test.ts"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        names = [s.name for s in symbols]
        assert "hello" in names
        assert "World" in names

    def test_parse_typescript_async_function(self, tmp_path):
        """Parse async TypeScript functions."""
        code = '''\
async function fetchData() {}
'''
        f = tmp_path / "test.ts"
        f.write_text(code)
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        names = [s.name for s in symbols]
        assert "fetchData" in names

    def test_parse_unsupported_language(self, tmp_path):
        """Unsupported file types return empty symbols."""
        f = tmp_path / "test.rs"
        f.write_text("fn main() {}")
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(f)
        assert symbols == []


# ---------------------------------------------------------------------------
# RepographGraph — CRUD operations
# ---------------------------------------------------------------------------


class TestRepographGraph:
    def test_add_file(self):
        graph = RepographGraph()
        symbols = [Symbol(name="foo", kind="FUNCTION", file="a.py", line=1, column=0, visibility="public")]
        graph.add_file("a.py", "python", symbols, imports=["os"])
        assert "a.py" in graph.nodes
        node = graph.nodes["a.py"]
        assert node.language == "python"
        assert node.imports == ["os"]
        assert len(node.symbols) == 1
        assert len(graph.symbols) == 1

    def test_add_dependency(self):
        graph = RepographGraph()
        graph.add_dependency("a.py::foo", "b.py::bar", DependencyKind.CALL)
        assert len(graph.edges) == 1
        assert graph.edges[0].kind == "CALL"

    def test_add_file_stores_symbols(self):
        graph = RepographGraph()
        symbols = [
            Symbol(name="f1", kind="FUNCTION", file="a.py", line=1, column=0, visibility="public"),
            Symbol(name="c1", kind="CLASS", file="a.py", line=5, column=0, visibility="public"),
        ]
        graph.add_file("a.py", "python", symbols, imports=[])
        assert "a.py::f1" in graph.symbols
        assert "a.py::c1" in graph.symbols

    def test_find_dependencies(self):
        graph = RepographGraph()
        graph.add_dependency("b.py", "a.py", DependencyKind.IMPORT)
        deps = graph.find_dependencies("a.py")
        assert "b.py" in deps

    def test_find_dependents(self):
        graph = RepographGraph()
        graph.add_dependency("a.py", "b.py", DependencyKind.CALL)
        deps = graph.find_dependents("a.py")
        assert "b.py" in deps

    def test_find_dependencies_no_match(self):
        graph = RepographGraph()
        graph.add_dependency("a.py", "b.py", DependencyKind.IMPORT)
        deps = graph.find_dependencies("c.py")
        assert deps == []

    def test_get_callers(self):
        graph = RepographGraph()
        graph.add_dependency("a.py::func_a", "b.py::func_b", DependencyKind.CALL)
        callers = graph.get_callers("func_b")
        assert "a.py::func_a" in callers

    def test_get_callees(self):
        graph = RepographGraph()
        graph.add_dependency("a.py::func_a", "b.py::func_b", DependencyKind.CALL)
        callees = graph.get_callees("func_a")
        assert "b.py::func_b" in callees

    def test_serialize(self):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [Symbol(name="f", kind="FUNCTION", file="a.py", line=1, column=0, visibility="public")], imports=[])
        graph.add_dependency("a.py::f", "b.py::g", DependencyKind.CALL)
        data = graph.serialize()
        assert "nodes" in data
        assert "edges" in data
        assert "symbols" in data
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1

    def test_save(self, tmp_path):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [Symbol(name="f", kind="FUNCTION", file="a.py", line=1, column=0, visibility="public")], imports=[])
        out_path = tmp_path / "graph.json"
        graph.save(out_path)
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert "metadata" in data
        assert "updated_at" in data["metadata"]
        assert "total_nodes" in data["metadata"]

    def test_serialize_multiple_files(self):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [Symbol(name="f", kind="FUNCTION", file="a.py", line=1, column=0, visibility="public")], imports=[])
        graph.add_file("b.py", "python", [Symbol(name="g", kind="FUNCTION", file="b.py", line=1, column=0, visibility="public")], imports=[])
        data = graph.serialize()
        assert len(data["nodes"]) == 2
        assert len(data["symbols"]) == 2


# ---------------------------------------------------------------------------
# PageRankCalculator
# ---------------------------------------------------------------------------


class TestPageRankCalculator:
    def test_basic_pagerank(self):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [], imports=[])
        graph.add_file("b.py", "python", [], imports=[])
        graph.add_dependency("a.py", "b.py", DependencyKind.IMPORT)
        calc = PageRankCalculator(graph, damping=0.85)
        scores = calc.calculate()
        assert "a.py" in scores
        assert "b.py" in scores
        # All scores should be positive
        assert all(v > 0 for v in scores.values())

    def test_pagerank_converges(self):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [], imports=[])
        graph.add_file("b.py", "python", [], imports=[])
        graph.add_file("c.py", "python", [], imports=[])
        graph.add_dependency("a.py", "b.py", DependencyKind.IMPORT)
        graph.add_dependency("b.py", "c.py", DependencyKind.IMPORT)
        calc = PageRankCalculator(graph, damping=0.85)
        scores = calc.calculate()
        # All scores should be positive
        assert all(v > 0 for v in scores.values())

    def test_apply_scores(self):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [], imports=[])
        graph.add_file("b.py", "python", [], imports=[])
        calc = PageRankCalculator(graph, damping=0.85)
        calc.apply_scores()
        assert graph.nodes["a.py"].importance > 0
        assert graph.nodes["b.py"].importance > 0


# ---------------------------------------------------------------------------
# RepographQuery
# ---------------------------------------------------------------------------


class TestRepographQuery:
    def test_find_symbol(self):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [Symbol(name="foo", kind="FUNCTION", file="a.py", line=1, column=0, visibility="public")], imports=[])
        graph.add_file("b.py", "python", [Symbol(name="foo", kind="FUNCTION", file="b.py", line=5, column=0, visibility="public")], imports=[])
        query = RepographQuery(graph)
        results = query.find_symbol("foo")
        assert len(results) == 2

    def test_find_symbol_no_match(self):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [Symbol(name="foo", kind="FUNCTION", file="a.py", line=1, column=0, visibility="public")], imports=[])
        query = RepographQuery(graph)
        results = query.find_symbol("bar")
        assert results == []

    def test_find_callers(self):
        graph = RepographGraph()
        graph.add_dependency("a.py::caller", "b.py::callee", DependencyKind.CALL)
        query = RepographQuery(graph)
        callers = query.find_callers("callee")
        assert "a.py::caller" in callers

    def test_find_dependents(self):
        graph = RepographGraph()
        graph.add_dependency("a.py::func", "b.py::other", DependencyKind.CALL)
        query = RepographQuery(graph)
        callees = query.find_dependents("func")
        assert "b.py::other" in callees

    def test_blast_radius_no_deps(self):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [], imports=[])
        query = RepographQuery(graph)
        affected = query.blast_radius("a.py")
        assert affected == []

    def test_blast_radius_with_deps(self):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [], imports=[])
        graph.add_file("b.py", "python", [], imports=[])
        graph.add_file("c.py", "python", [], imports=[])
        graph.add_dependency("b.py", "a.py", DependencyKind.IMPORT)
        graph.add_dependency("c.py", "b.py", DependencyKind.IMPORT)
        query = RepographQuery(graph)
        affected = query.blast_radius("a.py")
        assert "b.py" in affected

    def test_find_imports(self):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [], imports=["os", "sys"])
        query = RepographQuery(graph)
        imports = query.find_imports("a.py")
        assert imports == ["os", "sys"]

    def test_find_imports_missing_file(self):
        graph = RepographGraph()
        query = RepographQuery(graph)
        imports = query.find_imports("missing.py")
        assert imports == []

    def test_call_chain(self):
        graph = RepographGraph()
        graph.add_dependency("a.py::f1", "b.py::f2", DependencyKind.CALL)
        graph.add_dependency("b.py::f2", "c.py::f3", DependencyKind.CALL)
        query = RepographQuery(graph)
        chain = query.call_chain("f1")
        assert "f1" in chain
        assert any("f2" in c for c in chain)
        assert any("f3" in c for c in chain)

    def test_call_chain_respects_depth(self):
        graph = RepographGraph()
        for i in range(10):
            graph.add_dependency(f"a.py::f{i}", f"b.py::f{i+1}", DependencyKind.CALL)
        query = RepographQuery(graph)
        chain = query.call_chain("f0", max_depth=2)
        assert len(chain) <= 3  # f0 + 2 levels

    def test_to_markdown(self):
        graph = RepographGraph()
        graph.add_file("a.py", "python", [], imports=[])
        graph.add_file("b.py", "typescript", [], imports=[])
        calc = PageRankCalculator(graph, damping=0.85)
        calc.apply_scores()
        query = RepographQuery(graph)
        md = query.to_markdown()
        assert "# Repograph Report" in md
        assert "**Total Nodes:** 2" in md
        assert "python" in md
        assert "typescript" in md

    def test_blast_radius_avoids_cycles(self):
        """BFS should not loop on cyclic dependencies."""
        graph = RepographGraph()
        graph.add_file("a.py", "python", [], imports=[])
        graph.add_file("b.py", "python", [], imports=[])
        graph.add_dependency("b.py", "a.py", DependencyKind.IMPORT)
        graph.add_dependency("a.py", "b.py", DependencyKind.IMPORT)
        query = RepographQuery(graph)
        affected = query.blast_radius("a.py")
        assert "b.py" in affected
        assert len(affected) == 1  # no duplicates


# ---------------------------------------------------------------------------
# RepographSync
# ---------------------------------------------------------------------------


class TestRepographSync:
    def test_detect_python(self):
        sync = RepographSync(RepographGraph(), "/tmp")
        p = Path("/tmp/test.py")
        assert sync._detect_language(p) == "python"

    def test_detect_typescript(self):
        sync = RepographSync(RepographGraph(), "/tmp")
        p = Path("/tmp/test.ts")
        assert sync._detect_language(p) == "typescript"

    def test_detect_typescriptx(self):
        sync = RepographSync(RepographGraph(), "/tmp")
        p = Path("/tmp/test.tsx")
        assert sync._detect_language(p) == "typescript"

    def test_detect_javascript(self):
        sync = RepographSync(RepographGraph(), "/tmp")
        p = Path("/tmp/test.js")
        assert sync._detect_language(p) == "javascript"

    def test_detect_unknown(self):
        sync = RepographSync(RepographGraph(), "/tmp")
        p = Path("/tmp/test.xyz")
        assert sync._detect_language(p) == "unknown"

    def test_get_diff_no_git(self, tmp_path):
        """get_diff returns [] outside a git repo."""
        sync = RepographSync(RepographGraph(), str(tmp_path))
        diff = sync.get_diff()
        assert diff == []

    def test_get_diff_in_git_repo(self, tmp_path):
        """get_diff returns changed file names in a git repo."""
        import subprocess
        subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
        f = tmp_path / "change.txt"
        f.write_text("hello")
        subprocess.run(["git", "add", "change.txt"], cwd=str(tmp_path), capture_output=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=str(tmp_path), capture_output=True)
        f.write_text("changed")
        sync = RepographSync(RepographGraph(), str(tmp_path))
        diff = sync.get_diff()
        assert "change.txt" in diff

    def test_full_rebuild(self, tmp_path):
        """full_rebuild scans all Python files and adds them to the graph."""
        code = '''\
def hello():
    pass
'''
        (tmp_path / "mod1.py").write_text(code)
        (tmp_path / "mod2.py").write_text(code)
        parser = RepographParser(str(tmp_path))
        sync = RepographSync(RepographGraph(), str(tmp_path))
        sync.full_rebuild(parser)
        assert len(sync.graph.nodes) == 2
        assert "mod1.py" in sync.graph.nodes
        assert "mod2.py" in sync.graph.nodes

    def test_rebuild_for_changes(self, tmp_path):
        """Rebuild only changed files and their dependents."""
        code = '''\
def hello():
    pass
'''
        (tmp_path / "changed.py").write_text(code)
        parser = RepographParser(str(tmp_path))
        graph = RepographGraph()
        sync = RepographSync(graph, str(tmp_path))
        sync.rebuild_for_changes(["changed.py"], parser)
        assert "changed.py" in graph.nodes

    def test_rebuild_skips_missing_files(self, tmp_path):
        """Rebuild silently skips files that don't exist."""
        parser = RepographParser(str(tmp_path))
        graph = RepographGraph()
        sync = RepographSync(graph, str(tmp_path))
        sync.rebuild_for_changes(["nonexistent.py"], parser)
        assert "nonexistent.py" not in graph.nodes