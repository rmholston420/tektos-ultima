"""Tests for axioms.py uncovered lines: axiom_get, axiom_has, axiom_verify, axiom_create, axiom_registry iteration, and exception paths."""

import pytest

from tektos.axioms import (
    Axiom,
    load_axioms,
    axiom_get,
    axiom_has,
    axiom_verify,
    axiom_create,
)


class TestAxiomClass:
    """Test Axiom dataclass basics."""

    def test_axiom_creation(self):
        """Axiom can be created with all required fields."""
        axiom = Axiom(
            id="test.1",
            category="test",
            status="pending",
            date="2026-01-01",
            content="Test axiom",
        )
        assert axiom.id == "test.1"
        assert axiom.category == "test"
        assert axiom.status == "pending"
        assert axiom.is_active() is True
        assert axiom.is_complete() is False

    def test_axiom_verified(self):
        """Axiom with verified status is complete."""
        axiom = Axiom(
            id="test.2",
            category="test",
            status="verified",
            date="2026-01-01",
        )
        assert axiom.is_active() is True
        assert axiom.is_complete() is True

    def test_axiom_deprecated(self):
        """Axiom with deprecated status is not active."""
        axiom = Axiom(
            id="test.3",
            category="test",
            status="deprecated",
            date="2026-01-01",
        )
        assert axiom.is_active() is False

    def test_axiom_with_metadata(self):
        """Axiom can have metadata dict."""
        axiom = Axiom(
            id="test.4",
            category="test",
            status="in_progress",
            date="2026-01-01",
            metadata={"test_count": 10},
            tags=["unit-test"],
        )
        assert axiom.metadata == {"test_count": 10}
        assert axiom.tags == ["unit-test"]


class TestAxiomFunctions:
    """Cover axioms.py lines 238-263: module-level convenience functions."""

    def test_axiom_get_returns_none_for_missing(self):
        """axiom_get returns None for non-existent axiom."""
        result = axiom_get("nonexistent_axiom_xyz")
        assert result is None

    def test_axiom_has_returns_false_for_missing(self):
        """axiom_has returns False for non-existent axiom."""
        result = axiom_has("nonexistent_axiom_xyz")
        assert result is False

    def test_axiom_verify_returns_false_for_missing(self):
        """axiom_verify returns False for non-existent axiom."""
        result = axiom_verify("nonexistent_axiom_xyz")
        assert result is False

    def test_axiom_create(self):
        """axiom_create creates a new axiom."""
        result = axiom_create(
            id="test.create.1",
            category="test",
            content="Created axiom",
        )
        assert result is not None
        assert isinstance(result, Axiom)
        assert result.id == "test.create.1"
        assert result.category == "test"


class TestLoadAxioms:
    """Test load_axioms function."""

    def test_load_axioms_returns_system(self):
        """load_axioms returns an AxiomSystem instance."""
        result = load_axioms()
        assert result is not None
