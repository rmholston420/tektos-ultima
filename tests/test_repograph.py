"""Tests for src/tektos/repograph.py (standalone module, not the repograph/ package)

Covers: GraphNode, GraphEdge, Repograph, get_repograph.
"""

import importlib.util
import sys
from pathlib import Path

# Load the standalone repograph.py module directly
_repograph_path = Path(__file__).parent.parent / "src" / "tektos" / "repograph.py"
_spec = importlib.util.spec_from_file_location("standalone_repograph", _repograph_path)
_repograph_mod = importlib.util.module_from_spec(_spec)
sys.modules["standalone_repograph"] = _repograph_mod
_spec.loader.exec_module(_repograph_mod)

GraphNode = _repograph_mod.GraphNode
GraphEdge = _repograph_mod.GraphEdge
Repograph = _repograph_mod.Repograph
get_repograph = _repograph_mod.get_repograph


# ─── GraphNode ──────────────────────────────────────────────────────────────────

class TestGraphNode:
    def test_creation(self):
        node = GraphNode(id="n1", label="main.py", type="file")
        assert node.id == "n1"
        assert node.label == "main.py"
        assert node.type == "file"
        assert node.metadata == {}

    def test_with_metadata(self):
        node = GraphNode(
            id="n2",
            label="User class",
            type="class",
            metadata={"lines": 150},
        )
        assert node.metadata == {"lines": 150}


# ─── GraphEdge ──────────────────────────────────────────────────────────────────

class TestGraphEdge:
    def test_creation(self):
        edge = GraphEdge(source="n1", target="n2", relation="imports")
        assert edge.source == "n1"
        assert edge.target == "n2"
        assert edge.relation == "imports"
        assert edge.metadata == {}

    def test_with_metadata(self):
        edge = GraphEdge(
            source="n1",
            target="n2",
            relation="depends_on",
            metadata={"strength": 0.8},
        )
        assert edge.metadata == {"strength": 0.8}


# ─── Repograph ──────────────────────────────────────────────────────────────────

class TestRepograph:
    def setup_method(self):
        self.graph = Repograph()

    def test_add_node(self):
        node = GraphNode(id="n1", label="main.py", type="file")
        self.graph.add_node(node)
        assert self.graph.get_node_count() == 1
        assert self.graph.get_node("n1") is node

    def test_add_edge(self):
        self.graph.add_node(GraphNode(id="n1", label="a", type="file"))
        self.graph.add_node(GraphNode(id="n2", label="b", type="file"))
        self.graph.add_edge(GraphEdge(source="n1", target="n2", relation="imports"))
        assert self.graph.get_edge_count() == 1
        assert self.graph.get_neighbors("n1") == ["n2"]

    def test_get_node_not_found(self):
        assert self.graph.get_node("nonexistent") is None

    def test_get_neighbors_empty(self):
        assert self.graph.get_neighbors("nonexistent") == []

    def test_get_all_nodes(self):
        self.graph.add_node(GraphNode(id="n1", label="a", type="file"))
        self.graph.add_node(GraphNode(id="n2", label="b", type="file"))
        nodes = self.graph.get_all_nodes()
        assert len(nodes) == 2
        assert "n1" in nodes
        assert "n2" in nodes

    def test_get_all_edges(self):
        self.graph.add_edge(GraphEdge(source="n1", target="n2", relation="imports"))
        edges = self.graph.get_all_edges()
        assert len(edges) == 1
        assert edges[0].relation == "imports"

    def test_get_dependencies(self):
        self.graph.add_edge(GraphEdge(source="n1", target="n2", relation="imports"))
        self.graph.add_edge(GraphEdge(source="n1", target="n3", relation="depends_on"))
        self.graph.add_edge(GraphEdge(source="n1", target="n4", relation="calls"))
        deps = self.graph.get_dependencies("n1")
        assert "n2" in deps
        assert "n3" in deps
        assert "n4" not in deps  # "calls" is not a dependency relation

    def test_get_dependents(self):
        self.graph.add_edge(GraphEdge(source="n1", target="n2", relation="imports"))
        self.graph.add_edge(GraphEdge(source="n3", target="n2", relation="depends_on"))
        self.graph.add_edge(GraphEdge(source="n4", target="n2", relation="calls"))
        dependents = self.graph.get_dependents("n2")
        assert "n1" in dependents
        assert "n3" in dependents
        assert "n4" not in dependents  # "calls" is not a dependency relation

    def test_get_node_count(self):
        assert self.graph.get_node_count() == 0
        self.graph.add_node(GraphNode(id="n1", label="a", type="file"))
        assert self.graph.get_node_count() == 1

    def test_get_edge_count(self):
        assert self.graph.get_edge_count() == 0
        self.graph.add_edge(GraphEdge(source="n1", target="n2", relation="imports"))
        assert self.graph.get_edge_count() == 1

    def test_to_memory_entry(self):
        self.graph.add_node(GraphNode(id="n1", label="a", type="file"))
        self.graph.add_node(GraphNode(id="n2", label="b", type="class"))
        self.graph.add_edge(GraphEdge(source="n1", target="n2", relation="imports"))
        entry = self.graph.to_memory_entry()
        assert entry["total_nodes"] == 2
        assert entry["total_edges"] == 1
        assert "file" in entry["node_types"]
        assert "class" in entry["node_types"]


# ─── Convenience Function ───────────────────────────────────────────────────────

class TestConvenienceFunction:
    def test_get_repograph_singleton(self):
        g1 = get_repograph()
        g2 = get_repograph()
        assert g1 is g2
