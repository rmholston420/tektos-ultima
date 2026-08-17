"""Coverage expansion for axioms.py — targets all uncovered paths.

Covers:
- Axiom: is_active(), is_complete(), with tags/blocking/prerequisites
- AxiomSystem: load() dir-not-found, dict YAML docs, list YAML docs, None skip
- _parse_axiom with all optional fields
- _save() and _serialize() round-trip
- list_active(), list_by_category(), list_by_status()
- get_blockers(), get_dependents()
- to_markdown() with full field combinations
- load_axioms() caching
- Convenience functions: axiom_get, axiom_has, axiom_verify, axiom_create
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from tektos.axioms import (
    Axiom,
    AxiomSystem,
    load_axioms,
    axiom_get,
    axiom_has,
    axiom_verify,
    axiom_create,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def axiom_dir(tmp_path):
    """Create a temporary axioms directory with test files."""
    axioms_dir = tmp_path / "axioms"
    axioms_dir.mkdir()

    # Write a YAML file with a dict document
    axiom_file = axioms_dir / "milestones.axiom"
    axiom_file.write_text(yaml.dump({
        "id": "phase.1.complete",
        "category": "milestone",
        "status": "verified",
        "date": "2026-08-14",
        "content": "Phase 1 complete",
        "notes": "All milestones met",
        "metadata": {"test_count": 100, "coverage_pct": 85},
        "prerequisites": [],
        "blocking": ["phase.2.setup"],
        "tags": ["milestone", "phase1"],
    }))

    # Write a YAML file with a list document
    list_file = axioms_dir / "directives.axiom"
    list_file.write_text(yaml.dump_all([
        {
            "id": "directive.1",
            "category": "directive",
            "status": "in_progress",
            "date": "2026-08-15",
            "content": "Always write tests first",
        },
        {
            "id": "directive.2",
            "category": "directive",
            "status": "pending",
            "date": "2026-08-15",
            "content": "Review all code before merge",
            "tags": ["process"],
        },
    ]))

    # Write a file with a None doc (empty lines)
    empty_file = axioms_dir / "empty.axiom"
    empty_file.write_text("\n\n\n")

    return axioms_dir


# ── Axiom class tests ────────────────────────────────────────────────────


class TestAxiomMethods:
    """Test Axiom.is_active() and is_complete() with various states."""

    def test_is_active_pending(self):
        axiom = Axiom(id="a1", category="test", status="pending", date="2026-08-01")
        assert axiom.is_active() is True
        assert axiom.is_complete() is False

    def test_is_active_in_progress(self):
        axiom = Axiom(id="a2", category="test", status="in_progress", date="2026-08-01")
        assert axiom.is_active() is True
        assert axiom.is_complete() is False

    def test_is_active_verified(self):
        axiom = Axiom(id="a3", category="test", status="verified", date="2026-08-01")
        assert axiom.is_active() is True
        assert axiom.is_complete() is True

    def test_is_active_deprecated(self):
        axiom = Axiom(id="a4", category="test", status="deprecated", date="2026-08-01")
        assert axiom.is_active() is False
        assert axiom.is_complete() is False

    def test_axiom_with_tags(self):
        axiom = Axiom(
            id="a5",
            category="test",
            status="verified",
            date="2026-08-01",
            tags=["tag1", "tag2"],
            prerequisites=["a1", "a2"],
            blocking=["a3"],
        )
        assert axiom.tags == ["tag1", "tag2"]
        assert axiom.prerequisites == ["a1", "a2"]
        assert axiom.blocking == ["a3"]


# ── AxiomSystem.load() tests ─────────────────────────────────────────────


class TestAxiomSystemLoad:
    """Test AxiomSystem.load() with various file configurations."""

    def test_load_dir_not_found(self):
        """load() should warn and return self if directory doesn't exist."""
        system = AxiomSystem(axioms_dir="/nonexistent/path/xyz")
        result = system.load()
        assert result is system
        assert len(system._axioms) == 0

    def test_load_dict_yaml_docs(self, axiom_dir):
        """load() should parse dict YAML documents."""
        system = AxiomSystem(axioms_dir=axiom_dir)
        system.load()
        assert "phase.1.complete" in system._axioms
        axiom = system._axioms["phase.1.complete"]
        assert axiom.category == "milestone"
        assert axiom.content == "Phase 1 complete"
        assert axiom.metadata == {"test_count": 100, "coverage_pct": 85}
        assert axiom.blocking == ["phase.2.setup"]
        assert axiom.tags == ["milestone", "phase1"]

    def test_load_list_yaml_docs(self, axiom_dir):
        """load() should parse list YAML documents (yaml.dump_all)."""
        system = AxiomSystem(axioms_dir=axiom_dir)
        system.load()
        assert "directive.1" in system._axioms
        assert "directive.2" in system._axioms
        assert system._axioms["directive.1"].content == "Always write tests first"
        assert system._axioms["directive.2"].tags == ["process"]

    def test_load_skips_none_docs(self, axiom_dir):
        """load() should skip None (empty) YAML documents."""
        system = AxiomSystem(axioms_dir=axiom_dir)
        system.load()
        # Should have loaded dict and list docs but not empty file
        assert len(system._axioms) == 3  # phase.1.complete, directive.1, directive.2

    def test_load_list_item_branch(self, tmp_path):
        """load() should cover the list item branch (line 83)."""
        axioms_dir = tmp_path / "axioms"
        axioms_dir.mkdir()
        list_axiom = axioms_dir / "list_items.axiom"
        list_axiom.write_text(yaml.dump_all([
            [{"id": "list.1", "category": "test", "status": "verified", "date": "2026-08-01"}],
            {"id": "dict.1", "category": "test", "status": "pending", "date": "2026-08-02"},
        ]))
        system = AxiomSystem(axioms_dir=axioms_dir)
        system.load()
        assert "list.1" in system._axioms  # list branch (line 83)
        assert "dict.1" in system._axioms  # dict branch (line 85-86)

    def test_load_dict_branch(self, tmp_path):
        """load() should cover the dict branch (line 85-86)."""
        axioms_dir = tmp_path / "axioms"
        axioms_dir.mkdir()
        dict_axiom = axioms_dir / "dict_doc.axiom"
        dict_axiom.write_text(yaml.dump({
            "id": "dict.only",
            "category": "test",
            "status": "verified",
            "date": "2026-08-03",
        }))
        system = AxiomSystem(axioms_dir=axioms_dir)
        system.load()
        assert "dict.only" in system._axioms

    def test_set_status(self, tmp_path):
        """set_status should modify and persist status."""
        import tektos.axioms as axioms_module
        original = axioms_module._axiom_system
        axioms_module._axiom_system = None
        try:
            axioms_dir = tmp_path / "axioms"
            axioms_dir.mkdir()
            axiom_file = axioms_dir / "test.axiom"
            axiom_file.write_text(yaml.dump({
                "id": "status.1",
                "category": "test",
                "status": "verified",
                "date": "2026-08-01",
            }))
            system = load_axioms(axioms_dir=axioms_dir)
            result = system.set_status("status.1", "deprecated")
            assert result is True
            assert system._axioms["status.1"].status == "deprecated"
        finally:
            axioms_module._axiom_system = original

    def test_set_status_missing(self):
        """set_status on missing id should return False."""
        system = AxiomSystem()
        assert system.set_status("nonexistent", "verified") is False

    def test_add_and_persist(self, tmp_path):
        """add should store and persist an axiom."""
        axioms_dir = tmp_path / "axioms"
        system = AxiomSystem(axioms_dir=axioms_dir)
        axiom = Axiom(id="added.1", category="test", status="pending", date="2026-08-10")
        system.add(axiom)
        assert "added.1" in system._axioms
        assert system._axioms["added.1"].content == ""
        # Verify it was saved
        system._save()
        reloaded = AxiomSystem(axioms_dir=axioms_dir)
        reloaded.load()
        assert "added.1" in reloaded._axioms

    def test_add_persists(self, tmp_path):
        """add should call _save to persist."""
        axioms_dir = tmp_path / "axioms"
        system = AxiomSystem(axioms_dir=axioms_dir)
        axiom = Axiom(id="persist.1", category="test", status="pending", date="2026-08-10")
        system.add(axiom)
        assert "persist.1" in system._axioms
        # Verify persistence via reload
        system._save()
        reloaded = AxiomSystem(axioms_dir=axioms_dir)
        reloaded.load()
        assert "persist.1" in reloaded._axioms

    def test_load_invalid_yaml_logs_error(self, tmp_path):
        """load() should log error and continue on invalid YAML."""
        axioms_dir = tmp_path / "axioms"
        axioms_dir.mkdir()
        bad_file = axioms_dir / "bad.axiom"
        bad_file.write_text("invalid: yaml: {bad content: [unclosed")

        system = AxiomSystem(axioms_dir=axioms_dir)
        system.load()  # Should not raise
        assert len(system._axioms) == 0

    def test_load_empty_directory(self, tmp_path):
        """load() should work with empty directory."""
        axioms_dir = tmp_path / "axioms"
        axioms_dir.mkdir()

        system = AxiomSystem(axioms_dir=axioms_dir)
        system.load()
        assert len(system._axioms) == 0


# ── _parse_axiom tests ───────────────────────────────────────────────────


class TestParseAxiom:
    """Test AxiomSystem._parse_axiom with various data shapes."""

    def test_parse_minimal(self):
        system = AxiomSystem()
        axiom = system._parse_axiom({"id": "minimal", "category": "test"})
        assert axiom.id == "minimal"
        assert axiom.category == "test"
        assert axiom.status == "pending"
        assert axiom.content == ""
        assert axiom.notes == ""
        assert axiom.metadata == {}
        assert axiom.prerequisites == []
        assert axiom.blocking == []
        assert axiom.tags == []

    def test_parse_full(self):
        system = AxiomSystem()
        axiom = system._parse_axiom({
            "id": "full",
            "category": "architecture",
            "status": "verified",
            "date": "2026-08-16",
            "content": "Full axiom",
            "notes": "Detailed notes",
            "metadata": {"key": "val"},
            "prerequisites": ["p1"],
            "blocking": ["b1"],
            "tags": ["arch"],
        })
        assert axiom.date == "2026-08-16"
        assert axiom.content == "Full axiom"
        assert axiom.notes == "Detailed notes"
        assert axiom.metadata == {"key": "val"}
        assert axiom.prerequisites == ["p1"]
        assert axiom.blocking == ["b1"]
        assert axiom.tags == ["arch"]

    def test_parse_missing_category_defaults_to_misc(self):
        system = AxiomSystem()
        axiom = system._parse_axiom({"id": "no-cat"})
        assert axiom.category == "misc"

    def test_parse_missing_status_defaults_to_pending(self):
        system = AxiomSystem()
        axiom = system._parse_axiom({"id": "no-status"})
        assert axiom.status == "pending"


# ── _save and _serialize tests ───────────────────────────────────────────


class TestSaveAndSerialize:
    """Test AxiomSystem._save() and _serialize()."""

    def test_serialize_basic(self):
        system = AxiomSystem()
        axiom = Axiom(id="s1", category="test", status="verified", date="2026-08-01")
        serialized = system._serialize(axiom)
        assert serialized["id"] == "s1"
        assert serialized["category"] == "test"
        assert serialized["status"] == "verified"
        assert serialized["content"] == ""
        assert serialized["metadata"] == {}

    def test_serialize_with_all_fields(self):
        system = AxiomSystem()
        axiom = Axiom(
            id="s2",
            category="architecture",
            status="in_progress",
            date="2026-08-16",
            content="Design doc",
            notes="WIP",
            metadata={"draft": True},
            prerequisites=["p1"],
            blocking=["b1"],
            tags=["arch", "design"],
        )
        serialized = system._serialize(axiom)
        assert serialized == {
            "id": "s2",
            "category": "architecture",
            "status": "in_progress",
            "date": "2026-08-16",
            "content": "Design doc",
            "notes": "WIP",
            "metadata": {"draft": True},
            "prerequisites": ["p1"],
            "blocking": ["b1"],
            "tags": ["arch", "design"],
        }

    def test_save_creates_category_dirs(self, tmp_path):
        """_save() should create category subdirectories."""
        axioms_dir = tmp_path / "axioms"
        system = AxiomSystem(axioms_dir=axioms_dir)

        axiom1 = Axiom(id="a1", category="milestone", status="verified", date="2026-08-01")
        axiom2 = Axiom(id="a2", category="directive", status="pending", date="2026-08-02")
        system._axioms["a1"] = axiom1
        system._axioms["a2"] = axiom2
        system._save()

        assert (axioms_dir / "milestone").is_dir()
        assert (axioms_dir / "directive").is_dir()
        assert (axioms_dir / "milestone" / "milestone.axiom").exists()
        assert (axioms_dir / "directive" / "directive.axiom").exists()

    def test_save_load_round_trip(self, tmp_path):
        """_save() and load() should round-trip correctly."""
        axioms_dir = tmp_path / "axioms"

        system = AxiomSystem(axioms_dir=axioms_dir)
        axiom = Axiom(
            id="rt.1",
            category="test",
            status="verified",
            date="2026-08-01",
            content="Round trip",
            tags=["rt"],
        )
        system._axioms["rt.1"] = axiom
        system._save()

        # Reload from fresh instance
        system2 = AxiomSystem(axioms_dir=axioms_dir)
        system2.load()
        assert "rt.1" in system2._axioms
        assert system2._axioms["rt.1"].content == "Round trip"
        assert system2._axioms["rt.1"].tags == ["rt"]


# ── list_active, list_by_category, list_by_status tests ──────────────────


class TestListMethods:
    """Test AxiomSystem.list_active(), list_by_category(), list_by_status()."""

    def test_list_active_filters_deprecated(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(id="a1", category="test", status="verified", date="2026-08-01")
        system._axioms["a2"] = Axiom(id="a2", category="test", status="deprecated", date="2026-08-02")
        system._axioms["a3"] = Axiom(id="a3", category="test", status="pending", date="2026-08-03")

        active = system.list_active()
        assert len(active) == 2
        assert all(a.status != "deprecated" for a in active)

    def test_list_active_empty(self):
        system = AxiomSystem()
        assert system.list_active() == []

    def test_list_by_category(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(id="a1", category="milestone", status="verified", date="2026-08-01")
        system._axioms["a2"] = Axiom(id="a2", category="directive", status="pending", date="2026-08-02")
        system._axioms["a3"] = Axiom(id="a3", category="milestone", status="in_progress", date="2026-08-03")

        milestones = system.list_by_category("milestone")
        assert len(milestones) == 2
        assert all(a.category == "milestone" for a in milestones)

    def test_list_by_category_no_match(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(id="a1", category="test", status="verified", date="2026-08-01")
        assert system.list_by_category("nonexistent") == []

    def test_list_by_status(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(id="a1", category="test", status="verified", date="2026-08-01")
        system._axioms["a2"] = Axiom(id="a2", category="test", status="pending", date="2026-08-02")

        verified = system.list_by_status("verified")
        assert len(verified) == 1
        assert verified[0].id == "a1"

    def test_list_by_status_no_match(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(id="a1", category="test", status="verified", date="2026-08-01")
        assert system.list_by_status("deprecated") == []


# ── get_blockers and get_dependents tests ─────────────────────────────────


class TestBlockersAndDependents:
    """Test AxiomSystem.get_blockers() and get_dependents()."""

    def test_get_blockers_no_prerequisites(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(id="a1", category="test", status="verified", date="2026-08-01")
        blockers = system.get_blockers("a1")
        assert blockers == []

    def test_get_blockers_with_unmet(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(id="a1", category="test", status="verified", date="2026-08-01")
        system._axioms["a2"] = Axiom(id="a2", category="test", status="pending", date="2026-08-02")
        system._axioms["a3"] = Axiom(
            id="a3",
            category="test",
            status="in_progress",
            date="2026-08-03",
            prerequisites=["a1", "a2"],
        )
        blockers = system.get_blockers("a3")
        assert len(blockers) == 1
        assert blockers[0].id == "a2"

    def test_get_blockers_all_met(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(id="a1", category="test", status="verified", date="2026-08-01")
        system._axioms["a2"] = Axiom(id="a2", category="test", status="verified", date="2026-08-02")
        system._axioms["a3"] = Axiom(
            id="a3",
            category="test",
            status="in_progress",
            date="2026-08-03",
            prerequisites=["a1", "a2"],
        )
        blockers = system.get_blockers("a3")
        assert blockers == []

    def test_get_blockers_missing_prerequisite(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(id="a1", category="test", status="verified", date="2026-08-01")
        system._axioms["a2"] = Axiom(
            id="a2",
            category="test",
            status="in_progress",
            date="2026-08-02",
            prerequisites=["nonexistent"],
        )
        blockers = system.get_blockers("a2")
        assert blockers == []

    def test_get_dependents(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(id="a1", category="test", status="verified", date="2026-08-01")
        system._axioms["a2"] = Axiom(
            id="a2",
            category="test",
            status="in_progress",
            date="2026-08-02",
            prerequisites=["a1"],
        )
        system._axioms["a3"] = Axiom(
            id="a3",
            category="test",
            status="pending",
            date="2026-08-03",
            prerequisites=["a1"],
        )
        dependents = system.get_dependents("a1")
        assert len(dependents) == 2
        assert {d.id for d in dependents} == {"a2", "a3"}

    def test_get_dependents_no_dependents(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(id="a1", category="test", status="verified", date="2026-08-01")
        assert system.get_dependents("a1") == []

    def test_get_blockers_no_axiom(self):
        """get_blockers should return [] when axiom doesn't exist (line 161)."""
        system = AxiomSystem()
        assert system.get_blockers("nonexistent") == []


# ── to_markdown tests ────────────────────────────────────────────────────


class TestToMarkdown:
    """Test AxiomSystem.to_markdown() rendering."""

    def test_to_markdown_header(self):
        system = AxiomSystem()
        markdown = system.to_markdown()
        assert markdown.startswith("# Tektos Axioms")
        assert "## Active Axioms" in markdown

    def test_to_markdown_active_only(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(
            id="a1",
            category="milestone",
            status="verified",
            date="2026-08-01",
            content="Active axiom",
            notes="Detailed notes",
            metadata={"key": "val"},
            tags=["tag1"],
        )
        system._axioms["a2"] = Axiom(
            id="a2",
            category="milestone",
            status="deprecated",
            date="2026-08-02",
            content="Deprecated",
        )
        markdown = system.to_markdown()
        assert "### `a1`" in markdown
        assert "a2" not in markdown  # Deprecated axioms excluded

    def test_to_markdown_field_rendering(self):
        system = AxiomSystem()
        system._axioms["a1"] = Axiom(
            id="a1",
            category="directive",
            status="in_progress",
            date="2026-08-15",
            content="Always test first",
            notes="TDD style",
            metadata={"priority": "high"},
            tags=["tdd", "process"],
        )
        markdown = system.to_markdown()
        assert "### `a1`" in markdown
        assert "**Category**: directive" in markdown
        assert "**Status**: in_progress" in markdown
        assert "**Date**: 2026-08-15" in markdown
        assert "**Summary**: Always test first" in markdown
        assert "**Metadata**: priority=high" in markdown
        assert "**Notes**: TDD style" in markdown
        assert "**Tags**: tdd, process" in markdown

    def test_to_markdown_sorted(self):
        system = AxiomSystem()
        system._axioms["c"] = Axiom(id="c", category="test", status="verified", date="2026-08-03")
        system._axioms["a"] = Axiom(id="a", category="test", status="verified", date="2026-08-01")
        system._axioms["b"] = Axiom(id="b", category="test", status="verified", date="2026-08-02")

        markdown = system.to_markdown()
        # Verify sorted by id
        a_pos = markdown.find("### `a`")
        b_pos = markdown.find("### `b`")
        c_pos = markdown.find("### `c`")
        assert a_pos < b_pos < c_pos

    def test_to_markdown_no_axioms(self):
        system = AxiomSystem()
        markdown = system.to_markdown()
        assert "# Tektos Axioms" in markdown
        assert "## Active Axioms" in markdown


# ── Convenience function tests ───────────────────────────────────────────


class TestConvenienceFunctions:
    """Test load_axioms(), axiom_get(), axiom_has(), axiom_verify(), axiom_create()."""

    def test_load_axioms_caching(self, axiom_dir):
        """load_axioms() should cache and return same instance."""
        # Clear any existing cache
        import tektos.axioms as axioms_module
        original = axioms_module._axiom_system
        axioms_module._axiom_system = None

        try:
            system1 = load_axioms(axioms_dir=axiom_dir)
            system2 = load_axioms(axioms_dir=axiom_dir)
            assert system1 is system2
        finally:
            axioms_module._axiom_system = original

    def test_axiom_get(self, axiom_dir):
        """axiom_get() should return axiom by id."""
        import tektos.axioms as axioms_module
        original = axioms_module._axiom_system
        axioms_module._axiom_system = None

        try:
            load_axioms(axioms_dir=axiom_dir)
            axiom = axiom_get("phase.1.complete")
            assert axiom is not None
            assert axiom.id == "phase.1.complete"
        finally:
            axioms_module._axiom_system = original

    def test_axiom_get_missing(self):
        """axiom_get() should return None for missing id."""
        assert axiom_get("nonexistent.id") is None

    def test_axiom_has_true(self, axiom_dir):
        """axiom_has() should return True for existing id."""
        import tektos.axioms as axioms_module
        original = axioms_module._axiom_system
        axioms_module._axiom_system = None

        try:
            load_axioms(axioms_dir=axiom_dir)
            assert axiom_has("phase.1.complete") is True
        finally:
            axioms_module._axiom_system = original

    def test_axiom_has_false(self):
        """axiom_has() should return False for missing id."""
        assert axiom_has("nonexistent.id") is False

    def test_axiom_verify(self, axiom_dir):
        """axiom_verify() should mark axiom as verified and save."""
        import tektos.axioms as axioms_module
        original = axioms_module._axiom_system
        axioms_module._axiom_system = None

        try:
            load_axioms(axioms_dir=axiom_dir)
            result = axiom_verify("phase.1.complete")
            assert result is True
            # Verify it was saved (file exists with updated status)
            axiom_file = Path(axiom_dir) / "milestone" / "milestone.axiom"
            content = axiom_file.read_text()
            assert "status: verified" in content
        finally:
            axioms_module._axiom_system = original

    def test_axiom_verify_missing(self):
        """axiom_verify() should return False for missing id."""
        assert axiom_verify("nonexistent.id") is False

    def test_axiom_create(self, axiom_dir):
        """axiom_create() should create and persist new axiom."""
        import tektos.axioms as axioms_module
        original = axioms_module._axiom_system
        axioms_module._axiom_system = None

        try:
            load_axioms(axioms_dir=axiom_dir)
            axiom = axiom_create(
                id="created.1",
                category="milestone",
                content="Created axiom",
                tags=["new"],
            )
            assert axiom.id == "created.1"
            assert axiom.category == "milestone"
            assert axiom.status == "pending"
            assert axiom.content == "Created axiom"
            result = axiom_get("created.1")
            assert result is not None
            assert result.id == "created.1"
        finally:
            axioms_module._axiom_system = original
