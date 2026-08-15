"""
Tektos-Ultima v1 — Axiom System Tests

Tests the axiom framework using the actual API:
- Axiom dataclass (id, category, status, date, content, notes, metadata, prerequisites, blocking, tags)
- AxiomSystem: load, get, has, add, create, verify, set_status
- Querying: list_active, list_by_category, list_by_status
- Dependency: get_blockers, get_dependents
- Persistence to .axiom YAML files
- to_markdown rendering
- Convenience functions
"""

import asyncio
from pathlib import Path

import pytest
import yaml

from tektos.axioms import (
    Axiom,
    AxiomSystem,
    axiom_create,
    axiom_get,
    axiom_has,
    axiom_verify,
    load_axioms,
)


# ---------------------------------------------------------------------------
# Axiom dataclass
# ---------------------------------------------------------------------------


class TestAxiomDataclass:
    def test_axiom_defaults(self):
        axiom = Axiom(id="test.1", category="milestone", status="pending", date="2024-01-01")
        assert axiom.id == "test.1"
        assert axiom.content == ""
        assert axiom.notes == ""
        assert axiom.metadata == {}
        assert axiom.prerequisites == []
        assert axiom.blocking == []
        assert axiom.tags == []

    def test_axiom_custom_values(self):
        axiom = Axiom(
            id="test.2",
            category="architecture",
            status="verified",
            date="2024-06-15",
            content="Use event sourcing",
            notes="See ADR-001",
            metadata={"test_count": 100},
            prerequisites=["test.1"],
            blocking=[],
            tags=["events", "persistence"],
        )
        assert axiom.id == "test.2"
        assert axiom.category == "architecture"
        assert axiom.status == "verified"
        assert axiom.content == "Use event sourcing"
        assert axiom.notes == "See ADR-001"
        assert axiom.metadata == {"test_count": 100}
        assert axiom.prerequisites == ["test.1"]
        assert axiom.tags == ["events", "persistence"]

    def test_is_active_pending(self):
        axiom = Axiom(id="a", category="x", status="pending", date="2024-01-01")
        assert axiom.is_active() is True

    def test_is_active_in_progress(self):
        axiom = Axiom(id="a", category="x", status="in_progress", date="2024-01-01")
        assert axiom.is_active() is True

    def test_is_active_verified(self):
        axiom = Axiom(id="a", category="x", status="verified", date="2024-01-01")
        assert axiom.is_active() is True

    def test_is_active_deprecated(self):
        axiom = Axiom(id="a", category="x", status="deprecated", date="2024-01-01")
        assert axiom.is_active() is False

    def test_is_complete_verified(self):
        axiom = Axiom(id="a", category="x", status="verified", date="2024-01-01")
        assert axiom.is_complete() is True

    def test_is_complete_not_verified(self):
        axiom = Axiom(id="a", category="x", status="pending", date="2024-01-01")
        assert axiom.is_complete() is False


# ---------------------------------------------------------------------------
# AxiomSystem CRUD
# ---------------------------------------------------------------------------


class TestAxiomSystemCRUD:
    @pytest.fixture
    def axsys(self, tmp_path):
        s = AxiomSystem(str(tmp_path))
        s.load()  # ensure empty
        return s

    def test_initial_empty(self, axsys):
        assert axsys.list_active() == []

    def test_add_axiom(self, axsys):
        axiom = Axiom(id="test.1", category="milestone", status="verified", date="2024-01-01", content="done")
        axsys.add(axiom)
        found = axsys.get("test.1")
        assert found is not None
        assert found.content == "done"

    def test_get_missing_returns_none(self, axsys):
        assert axsys.get("nonexistent") is None

    def test_has_true(self, axsys):
        axsys.add(Axiom(id="test.1", category="x", status="verified", date="2024-01-01"))
        assert axsys.has("test.1") is True

    def test_has_false(self, axsys):
        assert axsys.has("nonexistent") is False

    def test_verify(self, axsys):
        axsys.add(Axiom(id="test.1", category="x", status="pending", date="2024-01-01"))
        result = axsys.verify("test.1")
        assert result is True
        found = axsys.get("test.1")
        assert found.status == "verified"

    def test_verify_missing(self, axsys):
        assert axsys.verify("nonexistent") is False

    def test_set_status(self, axsys):
        axsys.add(Axiom(id="test.1", category="x", status="pending", date="2024-01-01"))
        result = axsys.set_status("test.1", "in_progress")
        assert result is True
        found = axsys.get("test.1")
        assert found.status == "in_progress"

    def test_set_status_missing(self, axsys):
        assert axsys.set_status("nonexistent", "x") is False

    def test_create(self, axsys):
        axiom = axsys.create(
            id="test.1", category="milestone", content="new axiom",
            tags=["tag1"], metadata={"key": "val"},
            prerequisites=["dep.1"],
        )
        assert axiom.id == "test.1"
        assert axiom.category == "milestone"
        assert axiom.status == "pending"
        assert axiom.tags == ["tag1"]
        assert axiom.metadata == {"key": "val"}
        assert axiom.prerequisites == ["dep.1"]
        # Verify it was persisted
        found = axsys.get("test.1")
        assert found is not None

    def test_list_active(self, axsys):
        axsys.add(Axiom(id="a1", category="x", status="verified", date="2024-01-01"))
        axsys.add(Axiom(id="a2", category="x", status="deprecated", date="2024-01-01"))
        axsys.add(Axiom(id="a3", category="x", status="in_progress", date="2024-01-01"))
        active = axsys.list_active()
        ids = {a.id for a in active}
        assert "a1" in ids
        assert "a3" in ids
        assert "a2" not in ids  # deprecated is not active

    def test_list_by_category(self, axsys):
        axsys.add(Axiom(id="a1", category="architecture", status="verified", date="2024-01-01"))
        axsys.add(Axiom(id="a2", category="milestone", status="verified", date="2024-01-01"))
        axsys.add(Axiom(id="a3", category="architecture", status="pending", date="2024-01-01"))
        arch = axsys.list_by_category("architecture")
        assert len(arch) == 2
        assert all(a.category == "architecture" for a in arch)

    def test_list_by_status(self, axsys):
        axsys.add(Axiom(id="a1", category="x", status="verified", date="2024-01-01"))
        axsys.add(Axiom(id="a2", category="x", status="pending", date="2024-01-01"))
        axsys.add(Axiom(id="a3", category="x", status="verified", date="2024-01-01"))
        verified = axsys.list_by_status("verified")
        assert len(verified) == 2
        assert all(a.status == "verified" for a in verified)


# ---------------------------------------------------------------------------
# Dependency queries
# ---------------------------------------------------------------------------


class TestDependencyQueries:
    @pytest.fixture
    def axsys(self, tmp_path):
        s = AxiomSystem(str(tmp_path))
        s.load()
        return s

    def test_get_blockers_empty(self, axsys):
        axsys.add(Axiom(id="a1", category="x", status="verified", date="2024-01-01", prerequisites=[]))
        blockers = axsys.get_blockers("a1")
        assert blockers == []

    def test_get_blockers_present(self, axsys):
        axsys.add(Axiom(id="dep1", category="x", status="pending", date="2024-01-01"))
        axsys.add(Axiom(id="dep2", category="x", status="verified", date="2024-01-01"))
        axsys.add(Axiom(id="a1", category="x", status="verified", date="2024-01-01", prerequisites=["dep1", "dep2"]))
        blockers = axsys.get_blockers("a1")
        assert len(blockers) == 1
        assert blockers[0].id == "dep1"  # only pending one

    def test_get_blockers_missing_prerequisite(self, axsys):
        axsys.add(Axiom(id="a1", category="x", status="verified", date="2024-01-01", prerequisites=["missing"]))
        blockers = axsys.get_blockers("a1")
        assert blockers == []  # missing prerequisite returns None, filtered out

    def test_get_dependents(self, axsys):
        axsys.add(Axiom(id="dep", category="x", status="verified", date="2024-01-01"))
        axsys.add(Axiom(id="a1", category="x", status="pending", date="2024-01-01", prerequisites=["dep"]))
        axsys.add(Axiom(id="a2", category="x", status="pending", date="2024-01-01", prerequisites=["dep"]))
        axsys.add(Axiom(id="a3", category="x", status="pending", date="2024-01-01", prerequisites=["other"]))
        dependents = axsys.get_dependents("dep")
        assert len(dependents) == 2
        ids = {a.id for a in dependents}
        assert "a1" in ids
        assert "a2" in ids
        assert "a3" not in ids

    def test_get_dependents_none(self, axsys):
        axsys.add(Axiom(id="a1", category="x", status="pending", date="2024-01-01", prerequisites=[]))
        dependents = axsys.get_dependents("a1")
        assert dependents == []


# ---------------------------------------------------------------------------
# Persistence to .axiom YAML
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_load_yaml(self, tmp_path):
        s = AxiomSystem(str(tmp_path))
        s.load()
        s.add(Axiom(id="persist.1", category="milestone", status="verified", date="2024-01-01", content="saved", tags=["test"]))
        # Re-create to simulate reload
        s2 = AxiomSystem(str(tmp_path))
        s2.load()
        found = s2.get("persist.1")
        assert found is not None
        assert found.content == "saved"
        assert found.tags == ["test"]

    def test_yaml_file_created(self, tmp_path):
        s = AxiomSystem(str(tmp_path))
        s.load()
        s.add(Axiom(id="f.1", category="architecture", status="verified", date="2024-01-01", content="yml"))
        # Should create architecture/architecture.axiom
        yml_path = tmp_path / "architecture" / "architecture.axiom"
        assert yml_path.exists()
        with open(yml_path) as f:
            docs = list(yaml.safe_load_all(f))
        assert any(d["id"] == "f.1" for d in docs if d)

    def test_save_creates_categories(self, tmp_path):
        s = AxiomSystem(str(tmp_path))
        s.load()
        s.add(Axiom(id="a.1", category="milestone", status="verified", date="2024-01-01"))
        s.add(Axiom(id="a.2", category="directive", status="pending", date="2024-01-01"))
        dirs = [d.name for d in tmp_path.iterdir() if d.is_dir()]
        assert "milestone" in dirs
        assert "directive" in dirs

    def test_overwrite_existing_axiom(self, tmp_path):
        s = AxiomSystem(str(tmp_path))
        s.load()
        s.add(Axiom(id="over.1", category="x", status="pending", date="2024-01-01"))
        s.add(Axiom(id="over.1", category="x", status="verified", date="2024-01-02", content="updated"))
        s2 = AxiomSystem(str(tmp_path))
        s2.load()
        found = s2.get("over.1")
        assert found.status == "verified"
        assert found.content == "updated"


# ---------------------------------------------------------------------------
# to_markdown
# ---------------------------------------------------------------------------


class TestToMarkdown:
    def test_markdown_empty(self, tmp_path):
        s = AxiomSystem(str(tmp_path))
        s.load()
        md = s.to_markdown()
        assert "# Tektos Axioms" in md
        assert "## Active Axioms" in md

    def test_markdown_with_axioms(self, tmp_path):
        s = AxiomSystem(str(tmp_path))
        s.load()
        s.add(Axiom(id="md.1", category="milestone", status="verified", date="2024-01-01", content="test content", tags=["a", "b"]))
        md = s.to_markdown()
        assert "### `md.1`" in md
        assert "**Category**: milestone" in md
        assert "**Status**: verified" in md
        assert "**Summary**: test content" in md
        assert "**Tags**: a, b" in md

    def test_markdown_excludes_deprecated(self, tmp_path):
        s = AxiomSystem(str(tmp_path))
        s.load()
        s.add(Axiom(id="dep.1", category="x", status="deprecated", date="2024-01-01"))
        md = s.to_markdown()
        assert "dep.1" not in md


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    def test_axiom_create_and_get(self, tmp_path):
        # Reset global cache
        import tektos.axioms as axmod
        axmod._axiom_system = None
        s = AxiomSystem(str(tmp_path))
        axmod._axiom_system = s
        s.load()

        axiom = axiom_create("conv.1", "milestone", "convenience test", tags=["conv"])
        assert axiom.id == "conv.1"
        assert axiom.content == "convenience test"

        found = axiom_get("conv.1")
        assert found is not None
        assert found.id == "conv.1"

        assert axiom_has("conv.1") is True
        assert axiom_has("conv.missing") is False

        assert axiom_verify("conv.1") is True
        found = axiom_get("conv.1")
        assert found.status == "verified"

    def test_axiom_verify_missing(self):
        import tektos.axioms as axmod
        s = AxiomSystem("/nonexistent/path")
        axmod._axiom_system = s
        s.load()
        assert axiom_verify("missing") is False

    def test_axiom_get_missing(self):
        import tektos.axioms as axmod
        s = AxiomSystem("/nonexistent/path")
        axmod._axiom_system = s
        s.load()
        assert axiom_get("missing") is None