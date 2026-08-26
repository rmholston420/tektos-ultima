"""Tests for Axiom System — context compression framework."""

import pytest
import tempfile
import yaml
from pathlib import Path

from tektos.axioms import (
    Axiom,
    AxiomSystem,
    load_axioms,
    axiom_get,
    axiom_has,
    axiom_verify,
    axiom_create,
)


class TestAxiom:
    def test_defaults(self):
        axiom = Axiom(
            id="test.1",
            category="milestone",
            status="pending",
            date="2025-01-01",
        )
        assert axiom.id == "test.1"
        assert axiom.category == "milestone"
        assert axiom.status == "pending"
        assert axiom.date == "2025-01-01"
        assert axiom.content == ""
        assert axiom.notes == ""
        assert axiom.metadata == {}
        assert axiom.prerequisites == []
        assert axiom.blocking == []
        assert axiom.tags == []

    def test_custom(self):
        axiom = Axiom(
            id="test.2",
            category="directive",
            status="verified",
            date="2025-01-02",
            content="Test content",
            notes="Test notes",
            metadata={"test_count": 10},
            prerequisites=["test.1"],
            blocking=["test.3"],
            tags=["test", "example"],
        )
        assert axiom.content == "Test content"
        assert axiom.notes == "Test notes"
        assert axiom.metadata == {"test_count": 10}
        assert axiom.prerequisites == ["test.1"]
        assert axiom.blocking == ["test.3"]
        assert axiom.tags == ["test", "example"]

    def test_is_active_pending(self):
        axiom = Axiom(id="t", category="c", status="pending", date="2025-01-01")
        assert axiom.is_active() is True

    def test_is_active_in_progress(self):
        axiom = Axiom(id="t", category="c", status="in_progress", date="2025-01-01")
        assert axiom.is_active() is True

    def test_is_active_verified(self):
        axiom = Axiom(id="t", category="c", status="verified", date="2025-01-01")
        assert axiom.is_active() is True

    def test_is_active_deprecated(self):
        axiom = Axiom(id="t", category="c", status="deprecated", date="2025-01-01")
        assert axiom.is_active() is False

    def test_is_complete_verified(self):
        axiom = Axiom(id="t", category="c", status="verified", date="2025-01-01")
        assert axiom.is_complete() is True

    def test_is_complete_not_verified(self):
        axiom = Axiom(id="t", category="c", status="pending", date="2025-01-01")
        assert axiom.is_complete() is False


class TestAxiomSystem:
    def test_init_default_dir(self):
        system = AxiomSystem()
        assert system.axioms_dir is not None

    def test_init_custom_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            system = AxiomSystem(axioms_dir=tmpdir)
            assert str(system.axioms_dir) == tmpdir

    def test_load_nonexistent_dir(self, caplog):
        system = AxiomSystem(axioms_dir="/nonexistent/path")
        system.load()
        assert len(system._axioms) == 0

    def test_add_and_get(self):
        system = AxiomSystem()
        axiom = Axiom(id="test.1", category="milestone", status="pending", date="2025-01-01")
        system.add(axiom)
        result = system.get("test.1")
        assert result is not None
        assert result.id == "test.1"

    def test_add_and_has(self):
        system = AxiomSystem()
        axiom = Axiom(id="test.1", category="milestone", status="pending", date="2025-01-01")
        system.add(axiom)
        assert system.has("test.1") is True
        assert system.has("nonexistent") is False

    def test_verify(self):
        system = AxiomSystem()
        axiom = Axiom(id="test.1", category="milestone", status="pending", date="2025-01-01")
        system.add(axiom)
        result = system.verify("test.1")
        assert result is True
        got = system.get("test.1")
        assert got is not None
        assert got.status == "verified"

    def test_verify_nonexistent(self):
        system = AxiomSystem()
        result = system.verify("nonexistent")
        assert result is False

    def test_set_status(self):
        system = AxiomSystem()
        axiom = Axiom(id="test.1", category="milestone", status="pending", date="2025-01-01")
        system.add(axiom)
        result = system.set_status("test.1", "verified")
        assert result is True
        got = system.get("test.1")
        assert got is not None
        assert got.status == "verified"

    def test_set_status_nonexistent(self):
        system = AxiomSystem()
        result = system.set_status("nonexistent", "verified")
        assert result is False

    def test_create(self):
        system = AxiomSystem()
        axiom = system.create(
            id="test.1",
            category="milestone",
            content="Test content",
        )
        assert axiom.id == "test.1"
        assert axiom.category == "milestone"
        assert axiom.status == "pending"
        assert axiom.content == "Test content"
        assert system.has("test.1")

    def test_list_active(self):
        system = AxiomSystem()
        system.add(Axiom(id="t1", category="c", status="pending", date="2025-01-01"))
        system.add(Axiom(id="t2", category="c", status="verified", date="2025-01-01"))
        system.add(Axiom(id="t3", category="c", status="deprecated", date="2025-01-01"))
        active = system.list_active()
        assert len(active) == 2
        ids = {a.id for a in active}
        assert "t3" not in ids

    def test_list_by_category(self):
        system = AxiomSystem()
        system.add(Axiom(id="t1", category="milestone", status="pending", date="2025-01-01"))
        system.add(Axiom(id="t2", category="directive", status="pending", date="2025-01-01"))
        system.add(Axiom(id="t3", category="milestone", status="verified", date="2025-01-01"))
        milestones = system.list_by_category("milestone")
        assert len(milestones) == 2
        ids = {a.id for a in milestones}
        assert "t2" not in ids

    def test_list_by_status(self):
        system = AxiomSystem()
        system.add(Axiom(id="t1", category="c", status="pending", date="2025-01-01"))
        system.add(Axiom(id="t2", category="c", status="verified", date="2025-01-01"))
        pending = system.list_by_status("pending")
        assert len(pending) == 1
        assert pending[0].id == "t1"

    def test_get_blockers(self):
        system = AxiomSystem()
        system.add(Axiom(id="t1", category="c", status="pending", date="2025-01-01"))
        system.add(Axiom(id="t2", category="c", status="verified", date="2025-01-01"))
        system.add(Axiom(id="t3", category="c", status="pending", date="2025-01-01", prerequisites=["t1", "t2"]))
        blockers = system.get_blockers("t3")
        assert len(blockers) == 1
        assert blockers[0].id == "t1"

    def test_get_blockers_no_prerequisites(self):
        system = AxiomSystem()
        system.add(Axiom(id="t1", category="c", status="pending", date="2025-01-01"))
        blockers = system.get_blockers("t1")
        assert blockers == []

    def test_get_blockers_nonexistent(self):
        system = AxiomSystem()
        blockers = system.get_blockers("nonexistent")
        assert blockers == []

    def test_get_dependents(self):
        system = AxiomSystem()
        system.add(Axiom(id="t1", category="c", status="pending", date="2025-01-01"))
        system.add(Axiom(id="t2", category="c", status="pending", date="2025-01-01", prerequisites=["t1"]))
        system.add(Axiom(id="t3", category="c", status="pending", date="2025-01-01", prerequisites=["t1"]))
        dependents = system.get_dependents("t1")
        assert len(dependents) == 2
        ids = {a.id for a in dependents}
        assert "t2" in ids
        assert "t3" in ids

    def test_get_dependents_none(self):
        system = AxiomSystem()
        system.add(Axiom(id="t1", category="c", status="pending", date="2025-01-01"))
        dependents = system.get_dependents("t1")
        assert dependents == []

    def test_to_markdown(self):
        system = AxiomSystem()
        system.add(Axiom(id="t1", category="milestone", status="verified", date="2025-01-01", content="Test"))
        md = system.to_markdown()
        assert "# Tektos Axioms" in md
        assert "## Active Axioms" in md
        assert "### `t1`" in md
        assert "**Category**: milestone" in md
        assert "**Status**: verified" in md
        assert "**Summary**: Test" in md

    def test_to_markdown_excludes_deprecated(self):
        system = AxiomSystem()
        system.add(Axiom(id="t1", category="c", status="verified", date="2025-01-01"))
        system.add(Axiom(id="t2", category="c", status="deprecated", date="2025-01-01"))
        md = system.to_markdown()
        assert "### `t1`" in md
        assert "### `t2`" not in md

    def test_save_and_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            system = AxiomSystem(axioms_dir=tmpdir)
            system.add(Axiom(id="t1", category="milestone", status="pending", date="2025-01-01", content="Test"))
            system._save()
            # Reload
            system2 = AxiomSystem(axioms_dir=tmpdir)
            system2.load()
            axiom = system2.get("t1")
            assert axiom is not None
            assert axiom.content == "Test"

    def test_serialize_roundtrip(self):
        system = AxiomSystem()
        axiom = Axiom(
            id="t1",
            category="milestone",
            status="pending",
            date="2025-01-01",
            content="Test",
            notes="Notes",
            metadata={"key": "value"},
            prerequisites=["t2"],
            blocking=["t3"],
            tags=["test"],
        )
        serialized = system._serialize(axiom)
        assert serialized["id"] == "t1"
        assert serialized["category"] == "milestone"
        assert serialized["status"] == "pending"
        assert serialized["content"] == "Test"
        assert serialized["notes"] == "Notes"
        assert serialized["metadata"] == {"key": "value"}
        assert serialized["prerequisites"] == ["t2"]
        assert serialized["blocking"] == ["t3"]
        assert serialized["tags"] == ["test"]


class TestConvenienceFunctions:
    def test_axiom_get(self):
        result = axiom_get("nonexistent")
        assert result is None

    def test_axiom_has(self):
        result = axiom_has("nonexistent")
        assert result is False

    def test_axiom_verify(self):
        result = axiom_verify("nonexistent")
        assert result is False

    def test_axiom_create(self):
        axiom = axiom_create(
            id="test.1",
            category="milestone",
            content="Test",
        )
        assert axiom.id == "test.1"
        assert axiom.category == "milestone"
        assert axiom.content == "Test"
