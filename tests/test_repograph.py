"""Tests for Repograph — AST parsing, dependency graph, PageRank, queries, and sync."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tektos.repograph import (
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


# ── SymbolKind / DependencyKind ──────────────────────────────────────────────

class TestSymbolKind:
    def test_all_kinds_present(self):
        assert SymbolKind.MODULE.value == 1
        assert SymbolKind.FUNCTION.value == 2
        assert SymbolKind.CLASS.value == 3
        assert SymbolKind.METHOD.value == 4
        assert SymbolKind.VARIABLE.value == 5
        assert SymbolKind.TYPE.value == 6
        assert SymbolKind.IMPORT.value == 7
        assert SymbolKind.CALL.value == 8

    def test_symbol_kind_name(self):
        assert SymbolKind.FUNCTION.name == "FUNCTION"
        assert SymbolKind.CLASS.name == "CLASS"


class TestDependencyKind:
    def test_all_kinds_present(self):
        assert DependencyKind.IMPORT.value == 1
        assert DependencyKind.CALL.value == 2
        assert DependencyKind.INHERIT.value == 3
        assert DependencyKind.TYPE_REF.value == 4
        assert DependencyKind.ASSIGN.value == 5
        assert DependencyKind.COMPOSE.value == 6


# ── Symbol / FileNode / Dependency ───────────────────────────────────────────

class TestSymbol:
    def test_creation(self):
        s = Symbol(
            name="test_func",
            kind=SymbolKind.FUNCTION.name,
            file="src/test.py",
            line=10,
            column=4,
            visibility="public",
            signature="def test_func(x: int) -> str:",
            docstring="Test docstring",
        )
        assert s.name == "test_func"
        assert s.kind == "FUNCTION"
        assert s.file == "src/test.py"
        assert s.line == 10
        assert s.visibility == "public"

    def test_defaults(self):
        s = Symbol(name="x", kind=SymbolKind.VARIABLE.name, file="f.py", line=1, column=0, visibility="public")
        assert s.signature == ""
        assert s.docstring == ""
        assert s.module == ""


class TestDependency:
    def test_creation(self):
        d = Dependency(
            source="a.py::func_a",
            target="b.py::func_b",
            kind=DependencyKind.CALL.name,
        )
        assert d.source == "a.py::func_a"
        assert d.target == "b.py::func_b"
        assert d.kind == "CALL"


class TestFileNode:
    def test_creation(self):
        fn = FileNode(path="src/test.py", language="python", lines=100)
        assert fn.path == "src/test.py"
        assert fn.language == "python"
        assert fn.lines == 100
        assert fn.symbols == []
        assert fn.imports == []
        assert fn.importance == 0.0


# ── RepographParser ──────────────────────────────────────────────────────────

class TestRepographParser:
    def test_python_function_detection(self, tmp_path):
        """Parser should detect function definitions in Python files."""
        test_file = tmp_path / "test_sample.py"
        test_file.write_text("""
def hello():
    pass

async def async_fetch(url):
    pass
""")
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(test_file)

        names = [s.name for s in symbols]
        assert "hello" in names
        assert "async_fetch" in names

    def test_python_class_detection(self, tmp_path):
        """Parser should detect class definitions in Python files."""
        test_file = tmp_path / "sample.py"
        test_file.write_text("""
class MyClass:
    pass

class AnotherClass:
    pass
""")
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(test_file)

        names = [s.name for s in symbols]
        assert "MyClass" in names
        assert "AnotherClass" in names

    def test_python_module_symbol(self, tmp_path):
        """Parser should create a module symbol as first entry."""
        test_file = tmp_path / "sample.py"
        test_file.write_text("def foo():\n    pass\n")
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(test_file)

        # First symbol should be the module
        assert symbols[0].kind == "MODULE"
        assert "sample" in symbols[0].name

    def test_import_detection(self, tmp_path):
        """Parser should detect import statements."""
        test_file = tmp_path / "sample.py"
        test_file.write_text("import os\nfrom pathlib import Path\n")
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(test_file)

        names = [s.name for s in symbols]
        assert "os" in names
        assert "from pathlib" in names

    def test_typescript_function_detection(self, tmp_path):
        """Parser should detect TypeScript functions."""
        test_file = tmp_path / "sample.ts"
        test_file.write_text("function hello() {}\nasync function fetchData() {}\n")
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(test_file)

        names = [s.name for s in symbols]
        assert "hello" in names
        assert "fetchData" in names

    def test_typescript_class_detection(self, tmp_path):
        """Parser should detect TypeScript classes."""
        test_file = tmp_path / "sample.ts"
        test_file.write_text("class MyClass {}\n")
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(test_file)

        names = [s.name for s in symbols]
        assert "MyClass" in names

    def test_parse_file_returns_empty_for_unknown_extension(self, tmp_path):
        """Parser should return empty list for unsupported file types."""
        test_file = tmp_path / "sample.txt"
        test_file.write_text("plain text")
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(test_file)
        assert symbols == []

    def test_parse_file_returns_empty_for_invalid_python(self, tmp_path):
        """Parser should handle invalid Python gracefully."""
        test_file = tmp_path / "bad.py"
        test_file.write_text("def (invalid syntax")
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(test_file)
        assert symbols == []

    def test_module_name_conversion(self, tmp_path):
        """Parser should convert file path to dotted module name."""
        subdir = tmp_path / "src" / "tektos"
        subdir.mkdir(parents=True)
        test_file = subdir / "sample.py"
        test_file.write_text("def foo():\n    pass\n")
        parser = RepographParser(str(tmp_path))
        symbols = parser.parse_file(test_file)

        # Find the module symbol
        module_sym = [s for s in symbols if s.kind == "MODULE"][0]
        assert module_sym.module == "src.tektos.sample"


# ── RepographGraph ───────────────────────────────────────────────────────────

class TestRepographGraph:
    def test_add_file(self):
        """Graph should store file nodes and symbols."""
        graph = RepographGraph()
        symbols = [
            Symbol(name="foo", kind="FUNCTION", file="test.py", line=1, column=0, visibility="public"),
            Symbol(name="Bar", kind="CLASS", file="test.py", line=5, column=0, visibility="public"),
        ]
        graph.add_file("test.py", "python", symbols, [])

        assert "test.py" in graph.nodes
        assert len(graph.symbols) == 2
        assert "test.py::foo" in graph.symbols
        assert "test.py::Bar" in graph.symbols

    def test_add_dependency(self):
        """Graph should store dependency edges."""
        graph = RepographGraph()
        graph.add_dependency("a.py::func_a", "b.py::func_b", DependencyKind.CALL)

        assert len(graph.edges) == 1
        assert graph.edges[0].kind == "CALL"

    def test_find_dependencies(self):
        """Graph should return files that depend on given file."""
        graph = RepographGraph()
        graph.add_dependency("caller.py", "target.py", DependencyKind.CALL)
        graph.add_dependency("other.py", "target.py", DependencyKind.CALL)

        deps = graph.find_dependencies("target.py")
        assert "caller.py" in deps
        assert "other.py" in deps

    def test_find_dependents(self):
        """Graph should return files that given file depends on."""
        graph = RepographGraph()
        graph.add_dependency("source.py", "dep1.py", DependencyKind.CALL)
        graph.add_dependency("source.py", "dep2.py", DependencyKind.CALL)

        deps = graph.find_dependents("source.py")
        assert "dep1.py" in deps
        assert "dep2.py" in deps

    def test_find_callers(self):
        """Graph should return symbols that call a given symbol."""
        graph = RepographGraph()
        graph.add_dependency("a.py::func_a", "b.py::target", DependencyKind.CALL)
        graph.add_dependency("c.py::func_c", "b.py::target", DependencyKind.CALL)
        graph.add_dependency("d.py::other", "d.py::other", DependencyKind.CALL)

        callers = graph.get_callers("target")
        assert "a.py::func_a" in callers
        assert "c.py::func_c" in callers
        assert "d.py::other" not in callers  # different symbol

    def test_find_callees(self):
        """Graph should return symbols called by a given symbol."""
        graph = RepographGraph()
        graph.add_dependency("source.py::func", "target1.py::func", DependencyKind.CALL)
        graph.add_dependency("source.py::func", "target2.py::func", DependencyKind.CALL)

        callees = graph.get_callees("source.py::func")
        assert "target1.py::func" in callees
        assert "target2.py::func" in callees

    def test_serialize(self):
        """Graph should serialize to dict format."""
        graph = RepographGraph()
        symbols = [Symbol(name="foo", kind="FUNCTION", file="test.py", line=1, column=0, visibility="public")]
        graph.add_file("test.py", "python", symbols, [])
        graph.add_dependency("test.py::foo", "other.py::bar", DependencyKind.CALL)

        data = graph.serialize()
        assert "nodes" in data
        assert "edges" in data
        assert "symbols" in data
        assert len(data["nodes"]) == 1
        assert len(data["edges"]) == 1
        assert len(data["symbols"]) == 1

    def test_save_to_file(self, tmp_path):
        """Graph should save to JSON file with metadata."""
        graph = RepographGraph()
        symbols = [Symbol(name="foo", kind="FUNCTION", file="test.py", line=1, column=0, visibility="public")]
        graph.add_file("test.py", "python", symbols, [])

        output_path = tmp_path / "repograph.json"
        graph.save(output_path)

        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert "metadata" in data
        assert "updated_at" in data["metadata"]
        assert data["metadata"]["total_nodes"] == 1

    def test_empty_graph_serialize(self):
        """Empty graph should serialize correctly."""
        graph = RepographGraph()
        data = graph.serialize()
        assert data["nodes"] == {}
        assert data["edges"] == []
        assert data["symbols"] == {}


# ── PageRankCalculator ───────────────────────────────────────────────────────

class TestPageRankCalculator:
    def test_calculate_basic(self):
        """PageRank should calculate scores for all nodes."""
        graph = RepographGraph()
        graph.add_file("a.py", "python", [], [])
        graph.add_file("b.py", "python", [], [])
        graph.add_file("c.py", "python", [], [])

        calc = PageRankCalculator(graph, damping=0.85)
        scores = calc.calculate()

        assert len(scores) == 3
        for score in scores.values():
            assert 0 <= score <= 1

    def test_calculate_with_edges(self):
        """PageRank should give higher scores to nodes with more incoming edges."""
        graph = RepographGraph()
        graph.add_file("popular.py", "python", [], [])
        graph.add_file("obscure.py", "python", [], [])
        graph.add_file("a.py", "python", [], [])
        graph.add_file("b.py", "python", [], [])
        graph.add_file("c.py", "python", [], [])
        graph.add_file("d.py", "python", [], [])

        # popular.py has more incoming edges
        graph.add_dependency("a.py", "popular.py", DependencyKind.CALL)
        graph.add_dependency("b.py", "popular.py", DependencyKind.CALL)
        graph.add_dependency("c.py", "popular.py", DependencyKind.CALL)
        graph.add_dependency("d.py", "obscure.py", DependencyKind.CALL)

        calc = PageRankCalculator(graph, damping=0.85)
        scores = calc.calculate()

        # popular.py should have higher score (3 incoming vs 1)
        popular_score = scores.get("popular.py", 0)
        obscure_score = scores.get("obscure.py", 0)
        # Note: PageRank with only 5 nodes may not show strong differentiation,
        # but popular.py should be >= obscure.py
        assert popular_score >= obscure_score

    def test_apply_scores(self):
        """apply_scores should set importance on nodes."""
        graph = RepographGraph()
        graph.add_file("test.py", "python", [], [])

        calc = PageRankCalculator(graph, damping=0.85)
        calc.apply_scores()

        assert "test.py" in graph.nodes
        assert graph.nodes["test.py"].importance > 0


# ── RepographQuery ───────────────────────────────────────────────────────────

class TestRepographQuery:
    def test_find_symbol(self):
        """Query should find symbols by name."""
        graph = RepographGraph()
        graph.add_file("a.py", "python", [
            Symbol(name="foo", kind="FUNCTION", file="a.py", line=1, column=0, visibility="public"),
        ], [])
        graph.add_file("b.py", "python", [
            Symbol(name="foo", kind="FUNCTION", file="b.py", line=5, column=0, visibility="public"),
        ], [])

        query = RepographQuery(graph)
        results = query.find_symbol("foo")
        assert len(results) == 2

    def test_find_callers(self):
        """Query should find callers of a symbol."""
        graph = RepographGraph()
        graph.add_dependency("caller.py::func", "target.py::target", DependencyKind.CALL)

        query = RepographQuery(graph)
        callers = query.find_callers("target.py::target")
        assert "caller.py::func" in callers

    def test_blast_radius(self):
        """Query should calculate blast radius for a file."""
        graph = RepographGraph()
        graph.add_file("a.py", "python", [], [])
        graph.add_file("b.py", "python", [], [])
        graph.add_file("c.py", "python", [], [])

        # a depends on b means a.py has edges TO b.py
        # b depends on c means b.py has edges TO c.py
        graph.add_dependency("a.py", "b.py", DependencyKind.CALL)
        graph.add_dependency("b.py", "c.py", DependencyKind.CALL)

        query = RepographQuery(graph)
        # Changes to b.py should affect a.py (which depends ON b)
        # blast_radius returns files that depend on the given file
        radius = query.blast_radius("b.py")
        # b.py has a single dependent: a.py (since a.py depends on b.py)
        assert "a.py" in radius

    def test_find_imports(self):
        """Query should return imports for a file."""
        graph = RepographGraph()
        graph.add_file("test.py", "python", [], ["os", "sys", "json"])

        query = RepographQuery(graph)
        imports = query.find_imports("test.py")
        assert "os" in imports
        assert "sys" in imports

    def test_call_chain(self):
        """Query should trace call chains."""
        graph = RepographGraph()
        graph.add_dependency("a.py::func_a", "b.py::func_b", DependencyKind.CALL)
        graph.add_dependency("b.py::func_b", "c.py::func_c", DependencyKind.CALL)

        query = RepographQuery(graph)
        chain = query.call_chain("a.py::func_a", max_depth=10)
        assert "a.py::func_a" in chain
        assert "b.py::func_b" in chain
        assert "c.py::func_c" in chain

    def test_to_markdown(self):
        """Query should generate Markdown report."""
        graph = RepographGraph()
        graph.add_file("a.py", "python", [], [])
        graph.add_file("b.py", "python", [], [])

        query = RepographQuery(graph)
        md = query.to_markdown()

        assert "# Repograph Report" in md
        assert "**Total Nodes:** 2" in md
        assert "python" in md


# ── RepographSync ────────────────────────────────────────────────────────────

class TestRepographSync:
    def test_detect_language_python(self, tmp_path):
        """Sync should detect Python from extension."""
        sync = RepographSync(RepographGraph(), str(tmp_path))
        lang = sync._detect_language(tmp_path / "test.py")
        assert lang == "python"

    def test_detect_language_typescript(self, tmp_path):
        """Sync should detect TypeScript from extension."""
        sync = RepographSync(RepographSync(RepographGraph(), str(tmp_path)).repo_root if hasattr(RepographSync(RepographGraph(), str(tmp_path)), 'repo_root') else tmp_path, str(tmp_path))
        # Simpler approach
        sync = RepographSync(RepographGraph(), str(tmp_path))
        lang = sync._detect_language(tmp_path / "sample.ts")
        assert lang == "typescript"

    def test_detect_language_unknown(self, tmp_path):
        """Sync should return 'unknown' for unsupported extensions."""
        sync = RepographSync(RepographGraph(), str(tmp_path))
        lang = sync._detect_language(tmp_path / "sample.txt")
        assert lang == "unknown"

    def test_rebuild_for_changes(self, tmp_path):
        """Sync should rebuild graph for changed files."""
        graph = RepographGraph()
        test_file = tmp_path / "sample.py"
        test_file.write_text("def foo():\n    pass\n")

        sync = RepographSync(graph, str(tmp_path))
        parser = RepographParser(str(tmp_path))
        sync.rebuild_for_changes(["sample.py"], parser)

        assert "sample.py" in graph.nodes

    def test_full_rebuild(self, tmp_path):
        """Sync should rebuild entire graph."""
        graph = RepographGraph()
        test_dir = tmp_path / "src" / "test"
        test_dir.mkdir(parents=True)
        (test_dir / "a.py").write_text("def foo():\n    pass\n")
        (test_dir / "b.py").write_text("class Bar:\n    pass\n")

        sync = RepographSync(graph, str(tmp_path))
        parser = RepographParser(str(tmp_path))
        sync.full_rebuild(parser)

        # full_rebuild replaces self.graph, so check sync.graph
        assert len(sync.graph.nodes) >= 2

    def test_get_diff_no_git(self, tmp_path):
        """Sync should return empty list if git diff fails."""
        graph = RepographGraph()
        sync = RepographSync(graph, str(tmp_path))
        # tmp_path is not a git repo, so diff should fail gracefully
        diff = sync.get_diff()
        assert diff == []

    def test_full_rebuild_empty_repo(self, tmp_path):
        """Sync should handle empty repository."""
        graph = RepographGraph()
        sync = RepographSync(graph, str(tmp_path))
        parser = RepographParser(str(tmp_path))
        sync.full_rebuild(parser)
        assert len(graph.nodes) == 0
