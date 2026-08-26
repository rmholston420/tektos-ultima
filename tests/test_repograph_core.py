"""Tests for src/tektos/repograph/core.py

Covers: SymbolKind, DependencyKind, Symbol, Dependency, FileNode,
RepographParser, RepographGraph, PageRankCalculator, RepographQuery, RepographSync.
"""

import json
import os
import tempfile
from pathlib import Path

from tektos.repograph.core import (
    SymbolKind,
    DependencyKind,
    Symbol,
    Dependency,
    FileNode,
    RepographParser,
    RepographGraph,
    PageRankCalculator,
    RepographQuery,
    RepographSync,
)


# ─── Enums ──────────────────────────────────────────────────────────────────────

class TestSymbolKind:
    def test_all_kinds(self):
        assert SymbolKind.MODULE.value > 0
        assert SymbolKind.FUNCTION.value > 0
        assert SymbolKind.CLASS.value > 0
        assert SymbolKind.METHOD.value > 0
        assert SymbolKind.VARIABLE.value > 0
        assert SymbolKind.TYPE.value > 0
        assert SymbolKind.IMPORT.value > 0
        assert SymbolKind.CALL.value > 0

    def test_name(self):
        assert SymbolKind.FUNCTION.name == "FUNCTION"
        assert SymbolKind.CLASS.name == "CLASS"


class TestDependencyKind:
    def test_all_kinds(self):
        assert DependencyKind.IMPORT.value > 0
        assert DependencyKind.CALL.value > 0
        assert DependencyKind.INHERIT.value > 0
        assert DependencyKind.TYPE_REF.value > 0
        assert DependencyKind.ASSIGN.value > 0
        assert DependencyKind.COMPOSE.value > 0

    def test_name(self):
        assert DependencyKind.IMPORT.name == "IMPORT"
        assert DependencyKind.CALL.name == "CALL"


# ─── Dataclasses ────────────────────────────────────────────────────────────────

class TestSymbol:
    def test_creation(self):
        s = Symbol(name="main", kind="FUNCTION", file="test.py", line=1, column=0, visibility="public")
        assert s.name == "main"
        assert s.kind == "FUNCTION"
        assert s.file == "test.py"
        assert s.line == 1
        assert s.column == 0
        assert s.visibility == "public"
        assert s.signature == ""
        assert s.docstring == ""
        assert s.module == ""

    def test_with_all_fields(self):
        s = Symbol(
            name="create_session",
            kind="METHOD",
            file="src/session.py",
            line=10,
            column=4,
            visibility="public",
            signature="def create_session(self)",
            docstring="Create a new session",
            module="src.session",
        )
        assert s.signature == "def create_session(self)"
        assert s.docstring == "Create a new session"
        assert s.module == "src.session"


class TestDependency:
    def test_creation(self):
        d = Dependency(source="a", target="b", kind="IMPORT")
        assert d.source == "a"
        assert d.target == "b"
        assert d.kind == "IMPORT"


class TestFileNode:
    def test_creation(self):
        fn = FileNode(path="test.py", language="python", lines=100)
        assert fn.path == "test.py"
        assert fn.language == "python"
        assert fn.lines == 100
        assert fn.symbols == []
        assert fn.imports == []
        assert fn.dependents == []
        assert fn.importance == 0.0


# ─── RepographParser ────────────────────────────────────────────────────────────

class TestRepographParser:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.parser = RepographParser(self.tmpdir)

    def test_parse_python_file(self):
        test_file = Path(self.tmpdir) / "test_module.py"
        test_file.write_text("""
def hello():
    '''Say hello'''
    pass

class MyClass:
    '''A class'''
    pass

import os
from pathlib import Path
""")
        symbols = self.parser.parse_file(test_file)
        assert len(symbols) > 0
        # Should have module, function, class, and imports
        kinds = [s.kind for s in symbols]
        assert "MODULE" in kinds
        assert "FUNCTION" in kinds
        assert "CLASS" in kinds
        assert "IMPORT" in kinds

    def test_parse_python_file_empty(self):
        test_file = Path(self.tmpdir) / "empty.py"
        test_file.write_text("")
        symbols = self.parser.parse_file(test_file)
        # Should still have at least the module symbol
        assert len(symbols) >= 1
        assert symbols[0].kind == "MODULE"

    def test_parse_python_file_with_async(self):
        test_file = Path(self.tmpdir) / "async_test.py"
        test_file.write_text("""
async def fetch_data():
    pass
""")
        symbols = self.parser.parse_file(test_file)
        kinds = [s.kind for s in symbols]
        assert "FUNCTION" in kinds

    def test_parse_python_file_private(self):
        test_file = Path(self.tmpdir) / "private.py"
        test_file.write_text("""
def _private_func():
    pass

class _PrivateClass:
    pass
""")
        symbols = self.parser.parse_file(test_file)
        for s in symbols:
            if s.kind in ("FUNCTION", "CLASS"):
                assert s.visibility == "private"

    def test_parse_python_file_public(self):
        test_file = Path(self.tmpdir) / "public.py"
        test_file.write_text("""
def public_func():
    pass
""")
        symbols = self.parser.parse_file(test_file)
        for s in symbols:
            if s.kind == "FUNCTION":
                assert s.visibility == "public"

    def test_parse_nonexistent_file(self):
        symbols = self.parser.parse_file(Path("/nonexistent/file.py"))
        assert symbols == []

    def test_get_module_name(self):
        test_file = Path(self.tmpdir) / "src" / "module.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("")
        name = self.parser._get_module_name(test_file)
        assert name == "src.module"


# ─── RepographGraph ─────────────────────────────────────────────────────────────

class TestRepographGraph:
    def setup_method(self):
        self.graph = RepographGraph()

    def test_add_file(self):
        symbols = [
            Symbol(name="main", kind="FUNCTION", file="test.py", line=1, column=0, visibility="public"),
        ]
        self.graph.add_file("test.py", "python", symbols, ["os"])
        assert "test.py" in self.graph.nodes
        assert len(self.graph.symbols) == 1  # only the function symbol we passed

    def test_add_dependency(self):
        self.graph.add_dependency("a.py", "b.py", DependencyKind.IMPORT)
        assert len(self.graph.edges) == 1
        assert self.graph.edges[0].kind == "IMPORT"

    def test_find_dependencies(self):
        self.graph.add_dependency("a.py", "b.py", DependencyKind.IMPORT)
        self.graph.add_dependency("c.py", "b.py", DependencyKind.CALL)
        deps = self.graph.find_dependencies("b.py")
        assert "a.py" in deps
        assert "c.py" in deps

    def test_find_dependents(self):
        self.graph.add_dependency("a.py", "b.py", DependencyKind.IMPORT)
        self.graph.add_dependency("a.py", "c.py", DependencyKind.CALL)
        dependents = self.graph.find_dependents("a.py")
        assert "b.py" in dependents
        assert "c.py" in dependents

    def test_get_callers(self):
        self.graph.add_dependency("a.py", "b.py", DependencyKind.CALL)
        callers = self.graph.get_callers("b.py")
        assert "a.py" in callers

    def test_get_callees(self):
        self.graph.add_dependency("a.py", "b.py", DependencyKind.CALL)
        callees = self.graph.get_callees("a.py")
        assert "b.py" in callees

    def test_serialize(self):
        self.graph.add_file("test.py", "python", [], [])
        data = self.graph.serialize()
        assert "nodes" in data
        assert "edges" in data
        assert "symbols" in data

    def test_save(self):
        self.graph.add_file("test.py", "python", [], [])
        tmpfile = Path(tempfile.mkdtemp()) / "graph.json"
        self.graph.save(tmpfile)
        assert tmpfile.exists()
        data = json.loads(tmpfile.read_text())
        assert "metadata" in data
        assert "total_nodes" in data["metadata"]

    def test_find_dependencies_empty(self):
        deps = self.graph.find_dependencies("nonexistent.py")
        assert deps == []


# ─── PageRankCalculator ─────────────────────────────────────────────────────────

class TestPageRankCalculator:
    def setup_method(self):
        self.graph = RepographGraph()
        self.graph.add_file("a.py", "python", [], [])
        self.graph.add_file("b.py", "python", [], [])
        self.graph.add_file("c.py", "python", [], [])
        self.graph.add_dependency("a.py", "b.py", DependencyKind.IMPORT)
        self.graph.add_dependency("b.py", "c.py", DependencyKind.IMPORT)
        self.calculator = PageRankCalculator(self.graph)

    def test_calculate(self):
        scores = self.calculator.calculate()
        assert len(scores) == 3
        for score in scores.values():
            assert score > 0

    def test_apply_scores(self):
        self.calculator.apply_scores()
        for node in self.graph.nodes.values():
            assert node.importance >= 0


# ─── RepographQuery ─────────────────────────────────────────────────────────────

class TestRepographQuery:
    def setup_method(self):
        self.graph = RepographGraph()
        self.graph.add_file("a.py", "python", [], [])
        self.graph.add_file("b.py", "python", [], [])
        self.graph.add_dependency("a.py", "b.py", DependencyKind.CALL)
        self.query = RepographQuery(self.graph)

    def test_find_symbol(self):
        self.graph.symbols["a.py::main"] = Symbol(
            name="main", kind="FUNCTION", file="a.py", line=1, column=0, visibility="public"
        )
        results = self.query.find_symbol("main")
        assert len(results) == 1
        assert results[0].name == "main"

    def test_find_symbol_not_found(self):
        results = self.query.find_symbol("nonexistent")
        assert results == []

    def test_find_callers(self):
        callers = self.query.find_callers("b.py")
        assert "a.py" in callers

    def test_find_dependents(self):
        callees = self.query.find_dependents("a.py")
        assert "b.py" in callees

    def test_blast_radius(self):
        # a.py -> b.py -> c.py
        self.graph.add_file("c.py", "python", [], [])
        self.graph.add_dependency("b.py", "c.py", DependencyKind.CALL)
        affected = self.query.blast_radius("c.py")
        assert "b.py" in affected
        assert "a.py" in affected

    def test_find_imports(self):
        self.graph.nodes["test.py"] = FileNode(path="test.py", language="python", lines=10, imports=["os", "sys"])
        imports = self.query.find_imports("test.py")
        assert "os" in imports
        assert "sys" in imports

    def test_find_imports_not_found(self):
        imports = self.query.find_imports("nonexistent.py")
        assert imports == []

    def test_call_chain(self):
        # a -> b -> c
        self.graph.add_file("c.py", "python", [], [])
        self.graph.add_dependency("b.py", "c.py", DependencyKind.CALL)
        chain = self.query.call_chain("a.py")
        assert "a.py" in chain
        assert "b.py" in chain

    def test_to_markdown(self):
        md = self.query.to_markdown()
        assert "# Repograph Report" in md
        assert "Total Nodes" in md
        assert "Total Edges" in md


# ─── RepographSync ──────────────────────────────────────────────────────────────

class TestRepographSync:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.graph = RepographGraph()
        self.sync = RepographSync(self.graph, self.tmpdir)

    def test_detect_language_python(self):
        lang = self.sync._detect_language(Path("test.py"))
        assert lang == "python"

    def test_detect_language_typescript(self):
        lang = self.sync._detect_language(Path("test.ts"))
        assert lang == "typescript"

    def test_detect_language_javascript(self):
        lang = self.sync._detect_language(Path("test.js"))
        assert lang == "javascript"

    def test_detect_language_unknown(self):
        lang = self.sync._detect_language(Path("test.xyz"))
        assert lang == "unknown"

    def test_get_diff(self):
        # Initialize git repo for diff to work
        os.system(f"cd {self.tmpdir} && git init -q && git config user.email 'test@test.com' && git config user.name 'Test'")
        test_file = Path(self.tmpdir) / "test.py"
        test_file.write_text("# test")
        os.system(f"cd {self.tmpdir} && git add . && git commit -m 'initial' -q")
        test_file.write_text("# modified")
        diff = self.sync.get_diff()
        assert "test.py" in diff

    def test_get_diff_no_git(self):
        # Non-git directory should return empty
        sync = RepographSync(self.graph, "/tmp")
        diff = sync.get_diff()
        assert diff == []

    def test_rebuild_for_changes(self):
        test_file = Path(self.tmpdir) / "test.py"
        test_file.write_text("def hello(): pass")
        parser = RepographParser(self.tmpdir)
        self.sync.rebuild_for_changes(["test.py"], parser)
        assert "test.py" in self.graph.nodes

    def test_full_rebuild(self):
        test_file = Path(self.tmpdir) / "test.py"
        test_file.write_text("def hello(): pass")
        parser = RepographParser(self.tmpdir)
        self.sync.full_rebuild(parser)
        # full_rebuild replaces self.graph with a new RepographGraph
        assert "test.py" in self.sync.graph.nodes
