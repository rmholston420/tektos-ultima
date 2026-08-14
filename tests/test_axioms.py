"""Tests for Axiom System — context compression framework."""

from pathlib import Path

import pytest
import yaml

from tektos.axioms import Axiom, AxiomSystem, axiom_create, axiom_has, axiom_verify, load_axioms


# ── Axiom Data Model ────────────────────────────────────────────────────────

class TestAxiom:
    def test_defaults(self):
        a = Axiom(id="test.1", category="misc", status="pending", date="2026-01-01")
        assert a.content == ""
        assert a.notes == ""
        assert a.metadata == {}
        assert a.prerequisites == []
        assert a.blocking == []
        assert a.tags == []

    def test_is_active_pending(self):
        a = Axiom(id="test.1", category="misc", status="pending", date="2026-01-01")
        assert a.is_active() is True
        assert a.is_complete() is False

    def test_is_active_in_progress(self):
        a = Axiom(id="test.1", category="misc", status="in_progress", date="2026-01-01")
        assert a.is_active() is True
        assert a.is_complete() is False

    def test_is_active_verified(self):
        a = Axiom(id="test.1", category="misc", status="verified", date="2026-01-01")
        assert a.is_active() is True
        assert a.is_complete() is True

    def test_is_active_deprecated(self):
        a = Axiom(id="test.1", category="misc", status="deprecated", date="2026-01-01")
        assert a.is_active() is False
        assert a.is_complete() is False


# ── AxiomSystem ─────────────────────────────────────────────────────────────

class TestAxiomSystem:
    def test_load_empty_directory(self, tmp_path):
        """Loading from empty directory should return empty system."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        system = AxiomSystem(str(ax_dir))
        system.load()
        assert len(system.list_active()) == 0

    def test_load_single_axiom(self, tmp_path):
        """Should load a single axiom from file."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "milestone.axiom"
        axiom_file.write_text(yaml.dump({
            'id': 'phase.6.1.test',
            'category': 'milestone',
            'status': 'verified',
            'date': '2026-01-01',
            'content': 'Test axiom',
        }))
        system = AxiomSystem(str(ax_dir))
        system.load()
        assert system.has('phase.6.1.test') is True
        axiom = system.get('phase.6.1.test')
        assert axiom is not None
        assert axiom.status == 'verified'
        assert axiom.content == 'Test axiom'

    def test_load_multiple_axioms(self, tmp_path):
        """Should load multiple axioms from same file."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "milestone.axiom"
        axiom_file.write_text(yaml.dump_all([{
            'id': 'phase.6.1.test',
            'category': 'milestone',
            'status': 'verified',
            'date': '2026-01-01',
            'content': 'Test 1',
        }, {
            'id': 'phase.6.2.test',
            'category': 'milestone',
            'status': 'pending',
            'date': '2026-01-02',
            'content': 'Test 2',
        }]))
        system = AxiomSystem(str(ax_dir))
        system.load()
        assert system.has('phase.6.1.test') is True
        assert system.has('phase.6.2.test') is True
        assert len(system.list_active()) == 2

    def test_get_returns_none(self, tmp_path):
        """get() should return None for unknown axiom ID."""
        system = AxiomSystem()
        system.load()
        assert system.get('nonexistent.id') is None

    def test_has_returns_false(self, tmp_path):
        """has() should return False for unknown axiom ID."""
        system = AxiomSystem()
        system.load()
        assert system.has('nonexistent.id') is False

    def test_verify_axiom(self, tmp_path):
        """verify() should mark axiom as verified and persist."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "milestone.axiom"
        axiom_file.write_text(yaml.dump({
            'id': 'phase.6.1.test',
            'category': 'milestone',
            'status': 'pending',
            'date': '2026-01-01',
            'content': 'Test axiom',
        }))
        system = AxiomSystem(str(ax_dir))
        system.load()
        assert system.verify('phase.6.1.test') is True
        assert system.get('phase.6.1.test').status == 'verified'

        # _save() groups by category into subdirectories, e.g. milestone/milestone.axiom
        # Verify persistence by re-reading from the subdirectory
        sub_dir = ax_dir / "milestone"
        saved_file = sub_dir / "milestone.axiom"
        with open(saved_file) as f:
            data = list(yaml.safe_load_all(f))
        assert len(data) >= 1
        assert data[0]['status'] == 'verified'

    def test_set_status(self, tmp_path):
        """set_status() should update status and persist."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "milestone.axiom"
        axiom_file.write_text(yaml.dump({
            'id': 'phase.6.1.test',
            'category': 'milestone',
            'status': 'pending',
            'date': '2026-01-01',
        }))
        system = AxiomSystem(str(ax_dir))
        system.load()
        assert system.set_status('phase.6.1.test', 'in_progress') is True
        assert system.get('phase.6.1.test').status == 'in_progress'
        assert system.set_status('nonexistent', 'verified') is False

    def test_add_axiom(self, tmp_path):
        """add() should store axiom and persist."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        system = AxiomSystem(str(ax_dir))
        system.load()
        axiom = Axiom(id='phase.6.1.new', category='milestone', status='verified', date='2026-01-01')
        system.add(axiom)
        assert system.has('phase.6.1.new') is True

    def test_create_axiom(self, tmp_path):
        """create() should create and persist axiom."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        system = AxiomSystem(str(ax_dir))
        system.load()
        axiom = system.create('phase.6.1.created', 'milestone', 'Created axiom')
        assert axiom.id == 'phase.6.1.created'
        assert axiom.category == 'milestone'
        assert axiom.content == 'Created axiom'
        assert axiom.status == 'pending'
        assert system.has('phase.6.1.created') is True

    def test_list_active(self, tmp_path):
        """list_active() should exclude deprecated axioms."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "milestone.axiom"
        axiom_file.write_text(yaml.dump_all([{
            'id': 'active.test',
            'category': 'milestone',
            'status': 'verified',
            'date': '2026-01-01',
        }, {
            'id': 'deprecated.test',
            'category': 'milestone',
            'status': 'deprecated',
            'date': '2026-01-01',
        }]))
        system = AxiomSystem(str(ax_dir))
        system.load()
        active = system.list_active()
        assert len(active) == 1
        assert active[0].id == 'active.test'

    def test_list_by_category(self, tmp_path):
        """list_by_category() should filter by category."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "test.axiom"
        axiom_file.write_text(yaml.dump_all([{
            'id': 'test.1',
            'category': 'milestone',
            'status': 'verified',
            'date': '2026-01-01',
        }, {
            'id': 'test.2',
            'category': 'constraint',
            'status': 'verified',
            'date': '2026-01-01',
        }]))
        system = AxiomSystem(str(ax_dir))
        system.load()
        milestones = system.list_by_category('milestone')
        constraints = system.list_by_category('constraint')
        assert len(milestones) == 1
        assert milestones[0].id == 'test.1'
        assert len(constraints) == 1
        assert constraints[0].id == 'test.2'

    def test_list_by_status(self, tmp_path):
        """list_by_status() should filter by status."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "test.axiom"
        axiom_file.write_text(yaml.dump_all([{
            'id': 'test.1',
            'category': 'misc',
            'status': 'verified',
            'date': '2026-01-01',
        }, {
            'id': 'test.2',
            'category': 'misc',
            'status': 'pending',
            'date': '2026-01-01',
        }]))
        system = AxiomSystem(str(ax_dir))
        system.load()
        verified = system.list_by_status('verified')
        pending = system.list_by_status('pending')
        assert len(verified) == 1
        assert verified[0].id == 'test.1'
        assert len(pending) == 1
        assert pending[0].id == 'test.2'

    def test_get_blockers(self, tmp_path):
        """get_blockers() should return incomplete prerequisite axioms."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "test.axiom"
        axiom_file.write_text(yaml.dump_all([{
            'id': 'prereq.1',
            'category': 'misc',
            'status': 'pending',
            'date': '2026-01-01',
        }, {
            'id': 'prereq.2',
            'category': 'misc',
            'status': 'verified',
            'date': '2026-01-01',
        }, {
            'id': 'target.test',
            'category': 'misc',
            'status': 'pending',
            'date': '2026-01-01',
            'prerequisites': ['prereq.1', 'prereq.2'],
        }]))
        system = AxiomSystem(str(ax_dir))
        system.load()
        # Debug: print loaded axiom IDs
        print("Loaded axiom IDs:", list(system._axioms.keys()))
        blockers = system.get_blockers('target.test')
        # Only prereq.1 is incomplete (prereq.2 is verified)
        assert len(blockers) == 1
        assert blockers[0].id == 'prereq.1'

    def test_get_dependents(self, tmp_path):
        """get_dependents() should return axioms that depend on given axiom."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "test.axiom"
        axiom_file.write_text(yaml.dump_all([{
            'id': 'base.test',
            'category': 'misc',
            'status': 'verified',
            'date': '2026-01-01',
        }, {
            'id': 'dependent.1',
            'category': 'misc',
            'status': 'pending',
            'date': '2026-01-01',
            'prerequisites': ['base.test'],
        }, {
            'id': 'dependent.2',
            'category': 'misc',
            'status': 'pending',
            'date': '2026-01-01',
            'prerequisites': ['base.test'],
        }]))
        system = AxiomSystem(str(ax_dir))
        system.load()
        dependents = system.get_dependents('base.test')
        assert len(dependents) == 2
        dep_ids = {d.id for d in dependents}
        assert 'dependent.1' in dep_ids
        assert 'dependent.2' in dep_ids

    def test_to_markdown(self, tmp_path):
        """to_markdown() should render axioms as Markdown."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "milestone.axiom"
        axiom_file.write_text(yaml.dump({
            'id': 'phase.6.1.test',
            'category': 'milestone',
            'status': 'verified',
            'date': '2026-01-01',
            'content': 'Test axiom',
        }))
        system = AxiomSystem(str(ax_dir))
        system.load()
        md = system.to_markdown()
        assert '# Tektos Axioms' in md
        assert 'phase.6.1.test' in md
        assert 'Test axiom' in md

    def test_empty_directory_creates_no_error(self):
        """Loading from nonexistent directory should not crash."""
        system = AxiomSystem('/nonexistent/path')
        system.load()
        assert len(system.list_active()) == 0


# ── Convenience Functions ───────────────────────────────────────────────────

class TestConvenienceFunctions:
    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset global axiom cache before each test."""
        import tektos.axioms
        tektos.axioms._axiom_system = None
        yield
        tektos.axioms._axiom_system = None

    def test_axiom_has(self, tmp_path):
        """axiom_has() should check existence."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "milestone.axiom"
        axiom_file.write_text(yaml.dump({
            'id': 'test.has',
            'category': 'misc',
            'status': 'verified',
            'date': '2026-01-01',
        }))
        import tektos.axioms
        tektos.axioms._axiom_system = AxiomSystem(str(ax_dir))
        tektos.axioms._axiom_system.load()
        assert axiom_has('test.has') is True
        assert axiom_has('nonexistent') is False

    def test_axiom_verify(self, tmp_path):
        """axiom_verify() should mark as verified."""
        ax_dir = tmp_path / "axioms"
        ax_dir.mkdir()
        axiom_file = ax_dir / "milestone.axiom"
        axiom_file.write_text(yaml.dump({
            'id': 'test.verify',
            'category': 'milestone',
            'status': 'pending',
            'date': '2026-01-01',
        }))
        from tektos.axioms import axiom_get
        import tektos.axioms
        tektos.axioms._axiom_system = AxiomSystem(str(ax_dir))
        tektos.axioms._axiom_system.load()
        assert axiom_verify('test.verify') is True
        ax = axiom_get('test.verify')
        assert ax is not None
        assert ax.status == 'verified'
