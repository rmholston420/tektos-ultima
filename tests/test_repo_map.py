"""Tests for src/tektos/runtime/repo_map.py

Covers: FileNode, RepoMap, get_repo_map.
"""

from tektos.runtime.repo_map import RepoMap, FileNode, get_repo_map


# ─── FileNode ───────────────────────────────────────────────────────────────────

class TestFileNode:
    def test_creation(self):
        node = FileNode(path="src/main.py", type="file", size=1000)
        assert node.path == "src/main.py"
        assert node.type == "file"
        assert node.size == 1000
        assert node.dependencies == []
        assert node.imports == []
        assert node.metadata == {}

    def test_with_all_fields(self):
        node = FileNode(
            path="src/utils.py",
            type="file",
            size=500,
            dependencies=["src/main.py"],
            imports=["import os"],
            metadata={"priority": "high"},
        )
        assert node.dependencies == ["src/main.py"]
        assert node.imports == ["import os"]
        assert node.metadata == {"priority": "high"}


# ─── RepoMap ────────────────────────────────────────────────────────────────────

class TestRepoMap:
    def setup_method(self):
        self.repo_map = RepoMap(project_root="/home/rmholston/dev/tektos-ultima-v1")

    def test_get_node(self):
        node = self.repo_map.get_node("src/tektos/__init__.py")
        assert node is not None
        assert node.path == "src/tektos/__init__.py"
        assert node.type == "file"

    def test_get_node_not_found(self):
        node = self.repo_map.get_node("nonexistent.py")
        assert node is None

    def test_get_all_nodes(self):
        nodes = self.repo_map.get_all_nodes()
        assert isinstance(nodes, dict)
        assert len(nodes) > 0

    def test_get_dependencies(self):
        node = self.repo_map.get_node("src/tektos/__init__.py")
        if node:
            deps = self.repo_map.get_dependencies(node.path)
            assert isinstance(deps, list)

    def test_get_imports(self):
        node = self.repo_map.get_node("src/tektos/__init__.py")
        if node:
            imports = self.repo_map.get_imports(node.path)
            assert isinstance(imports, list)

    def test_get_file_count(self):
        count = self.repo_map.get_file_count()
        assert count > 0

    def test_to_memory_entry(self):
        entry = self.repo_map.to_memory_entry()
        assert "total_files" in entry
        assert "project_root" in entry
        assert "recent_files" in entry
        assert entry["total_files"] > 0


# ─── Convenience Function ───────────────────────────────────────────────────────

class TestConvenienceFunction:
    def test_get_repo_map_singleton(self):
        m1 = get_repo_map("/home/rmholston/dev/tektos-ultima-v1")
        m2 = get_repo_map("/home/rmholston/dev/tektos-ultima-v1")
        assert m1 is m2

    def test_get_repo_map_different_root(self):
        m1 = get_repo_map("/home/rmholston/dev/tektos-ultima-v1")
        m2 = get_repo_map("/tmp")
        assert m1 is not m2
