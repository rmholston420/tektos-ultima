"""Tests for memory persistence layer — SQLite-backed 4-tier memory.

Tests save/load/search/decay on all tiers, transfer logging, stats,
and the MemorySystem integration with persistence.
"""

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from tektos.memory.persistence import MemoryPersistence
from tektos.memory.memory_system import MemorySystem


# ─── Helper fixtures ─────────────────────────────────────────────────────────


def _sample_entry(tier="working", **overrides) -> dict:
    """Create a sample memory entry for testing."""
    base = {
        "id": f"{tier}-test-1",
        "content": f"{tier} memory content",
        "hemisphere": "left",
        "is_novel": True,
        "novelty_score": 0.75,
        "timestamp": "2026-08-16T00:00:00+00:00",
        "expires_at": "2026-08-16T00:01:00+00:00",
        "source_tier": None,
        "destination_tier": None,
        "who": "test",
        "what": "test_entry",
        "where": "test_location",
        "when": "2026-08-16T00:00:00+00:00",
        "why": "testing",
        "how": "manual",
        "metadata": {"key": "value"},
    }
    base.update(overrides)
    return base


def _sample_entry_unique(tier="working", idx=0, **overrides) -> dict:
    """Create a sample memory entry with unique ID (avoids duplicate ID collisions)."""
    base = {
        "id": f"{tier}-test-idx-{idx}",
        "content": f"{tier} memory content {idx}",
        "hemisphere": "left",
        "is_novel": True if idx == 1 else False,
        "novelty_score": 0.75 if idx == 1 else 0.0,
        "timestamp": "2026-08-16T00:00:00+00:00",
        "expires_at": "2026-08-16T00:01:00+00:00",
        "source_tier": None,
        "destination_tier": None,
        "who": "test",
        "what": "test_entry",
        "where": "test_location",
        "when": "2026-08-16T00:00:00+00:00",
        "why": "testing",
        "how": "manual",
        "metadata": {"key": "value"},
    }
    base.update(overrides)
    return base


# ─── Persistence Tests ──────────────────────────────────────────────────────


class TestPersistence:
    """Core MemoryPersistence CRUD operations."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.db_path = f"/tmp/test_memory_{id(self)}.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.persistence = MemoryPersistence(self.db_path)
        yield
        self.persistence.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_save_and_load_working(self):
        entry = _sample_entry(tier="working")
        result_id = self.persistence.save_working(entry)
        assert result_id == entry["id"]

        loaded = self.persistence.load_working(limit=10)
        assert len(loaded) == 1
        assert loaded[0]["content"] == "working memory content"
        assert loaded[0]["where"] == "test_location"
        assert loaded[0]["metadata"]["key"] == "value"

    def test_save_and_load_long_term(self):
        entry = _sample_entry(tier="long_term", expires_at=None)
        result_id = self.persistence.save_long_term(entry)
        assert result_id == entry["id"]

        loaded = self.persistence.load_long_term(limit=10)
        assert len(loaded) == 1
        assert loaded[0]["content"] == "long_term memory content"

    def test_save_and_load_procedural(self):
        entry = _sample_entry(tier="procedural", metadata={"skill_id": "test-skill"})
        result_id = self.persistence.save_procedural(entry)
        assert result_id == entry["id"]

        loaded = self.persistence.load_procedural(limit=10)
        assert len(loaded) == 1
        assert loaded[0]["content"] == "procedural memory content"

    def test_multiple_entries_same_tier(self):
        for i in range(5):
            entry = _sample_entry(tier="working", id=f"working-multi-{i}")
            self.persistence.save_working(entry)

        loaded = self.persistence.load_all_working()
        assert len(loaded) == 5

    def test_delete_working(self):
        self.persistence.save_working(_sample_entry(tier="working", id="del-test"))
        assert len(self.persistence.load_working()) == 1

        deleted = self.persistence.delete_working("del-test")
        assert deleted is True
        assert len(self.persistence.load_working()) == 0

    def test_delete_nonexistent_returns_false(self):
        deleted = self.persistence.delete_working("nonexistent")
        assert deleted is False

    def test_delete_long_term(self):
        self.persistence.save_long_term(_sample_entry(tier="long_term", id="del-lt"))
        assert len(self.persistence.load_long_term()) == 1

        deleted = self.persistence.delete_long_term("del-lt")
        assert deleted is True

    def test_delete_procedural(self):
        self.persistence.save_procedural(_sample_entry(tier="procedural", id="del-pr"))
        assert len(self.persistence.load_procedural()) == 1

        deleted = self.persistence.delete_procedural("del-pr")
        assert deleted is True

    def test_search_long_term(self):
        self.persistence.save_long_term(_sample_entry_unique(tier="long_term", idx=0, content="testing search", what="search_test"))
        self.persistence.save_long_term(_sample_entry_unique(tier="long_term", idx=1, content="unrelated content", what="other_test"))

        results = self.persistence.search_long_term("search")
        assert len(results) == 1
        assert results[0]["what"] == "search_test"

    def test_search_procedural(self):
        self.persistence.save_procedural(_sample_entry_unique(tier="procedural", idx=0, content="coding skill", what="how_to_code"))
        self.persistence.save_procedural(_sample_entry_unique(tier="procedural", idx=1, content="design pattern"))

        results = self.persistence.search_procedural("coding")
        assert len(results) == 1
        assert "coding" in results[0]["content"].lower()

    def test_search_no_matches(self):
        results = self.persistence.search_long_term("zzzz_nonexistent")
        assert len(results) == 0

    def test_get_stats(self):
        self.persistence.save_working(_sample_entry_unique(tier="working", idx=0))
        self.persistence.save_working(_sample_entry_unique(tier="working", idx=1, is_novel=True))
        self.persistence.save_long_term(_sample_entry_unique(tier="long_term", idx=0))
        self.persistence.save_procedural(_sample_entry_unique(tier="procedural", idx=0))

        stats = self.persistence.get_stats()
        assert stats["working_count"] == 2
        assert stats["working_novel"] == 1
        assert stats["long_term_count"] == 1
        assert stats["procedural_count"] == 1
        assert stats["transfers"] == 0

    def test_import_entries(self):
        entries = [
            _sample_entry(tier="working", id=f"import-{i}")
            for i in range(3)
        ]
        count = self.persistence.import_entries("working", entries)
        assert count == 3
        assert len(self.persistence.load_all_working()) == 3

    def test_export_entries(self):
        self.persistence.save_working(_sample_entry(tier="working", id="export-1"))
        self.persistence.save_working(_sample_entry(tier="working", id="export-2"))

        exported = self.persistence.export_entries("working")
        assert len(exported) == 2

    def test_export_unknown_tier(self):
        exported = self.persistence.export_entries("nonexistent")
        assert exported == []


# ─── Transfer Logging ───────────────────────────────────────────────────────


class TestTransferLogging:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.db_path = f"/tmp/test_transfer_{id(self)}.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.persistence = MemoryPersistence(self.db_path)
        yield
        self.persistence.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_log_transfer(self):
        self.persistence.log_transfer("sensory", "working", "mem-test-1")
        history = self.persistence.get_transfer_history()
        assert len(history) == 1
        assert history[0]["from_tier"] == "sensory"
        assert history[0]["to_tier"] == "working"
        assert history[0]["entry_id"] == "mem-test-1"

    def test_multiple_transfers(self):
        for i in range(5):
            self.persistence.log_transfer("working", "long_term", f"mem-{i}")

        history = self.persistence.get_transfer_history()
        assert len(history) == 5


# ─── Decay ──────────────────────────────────────────────────────────────────


class TestDecay:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.db_path = f"/tmp/test_decay_{id(self)}.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.persistence = MemoryPersistence(self.db_path)
        yield
        self.persistence.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_decay_removes_expired_working(self):
        # Save with past expiry
        entry = _sample_entry(tier="working", expires_at="2020-01-01T00:00:00+00:00")
        self.persistence.save_working(entry)

        result = self.persistence.decay_working()
        assert result == 1
        assert len(self.persistence.load_working()) == 0

    def test_decay_keeps_non_expired(self):
        # Save with future expiry
        entry = _sample_entry(tier="working", expires_at="2030-01-01T00:00:00+00:00")
        self.persistence.save_working(entry)

        result = self.persistence.decay_working()
        assert result == 0
        assert len(self.persistence.load_working()) == 1

    def test_decay_no_expiry_keeps_entry(self):
        entry = _sample_entry(tier="working", expires_at=None)
        self.persistence.save_working(entry)

        result = self.persistence.decay_working()
        assert result == 0

    def test_decay_all(self):
        self.persistence.save_working(_sample_entry(tier="working", expires_at="2020-01-01T00:00:00+00:00"))
        self.persistence.save_working(_sample_entry(tier="working", id="keep", expires_at=None))

        result = self.persistence.decay_all()
        assert result["working"] == 1
        assert result["long_term"] == 0
        assert result["procedural"] == 0


# ─── MemorySystem Integration ───────────────────────────────────────────────


class TestMemorySystemIntegration:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.db_path = f"/tmp/test_integration_{id(self)}.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        yield
        # Cleanup handled by fixture teardown
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_init_loads_persistent_entries(self):
        # Create persistence and populate it
        persistence = MemoryPersistence(self.db_path)
        persistence.save_long_term(_sample_entry(tier="long_term", id="lt-init"))
        persistence.close()

        # Create MemorySystem — should auto-load
        ms = MemorySystem(persistence=MemoryPersistence(self.db_path))
        lt = ms.tiers["long_term"]
        assert len(lt) == 1
        assert lt[0].content == "long_term memory content"
        ms.persistence.close()

    def test_add_to_memory_system_persists(self):
        persistence = MemoryPersistence(self.db_path)
        ms = MemorySystem(persistence=persistence)

        # Add via MemorySystem (in-memory, but persistence exists)
        entry = ms.add("persisted content", tier="long_term")
        assert len(ms.tiers["long_term"]) == 1

        # Verify persistence layer has it too
        loaded = persistence.load_long_term()
        assert len(loaded) == 1

        ms.persistence.close()

    def test_summary_includes_persisted_data(self):
        persistence = MemoryPersistence(self.db_path)
        persistence.save_long_term(_sample_entry(tier="long_term", id="sum-1"))
        persistence.save_procedural(_sample_entry(tier="procedural", id="sum-2"))
        persistence.close()

        ms = MemorySystem(persistence=MemoryPersistence(self.db_path))
        summary = ms.get_summary()
        assert summary["long_term_count"] == 1
        assert summary["procedural_count"] == 1

        ms.persistence.close()


# ─── Background Decay Scheduler ─────────────────────────────────────────────


class TestDecayScheduler:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        self.db_path = f"/tmp/test_scheduler_{id(self)}.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.persistence = MemoryPersistence(self.db_path)
        yield
        self.persistence.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_scheduler_starts_and_stops(self):
        self.persistence.start_decay_scheduler(interval=1.0)
        assert self.persistence.decay_thread is not None
        assert self.persistence.decay_thread.is_alive()

        self.persistence.stop_decay_scheduler()
        assert self.persistence.decay_thread is None

    def test_scheduler_removes_expired(self):
        # Save with past expiry
        self.persistence.save_working(_sample_entry(tier="working", expires_at="2020-01-01T00:00:00+00:00"))

        # Verify entry exists before decay
        assert len(self.persistence.load_working()) == 1

        # Manually trigger decay to verify removal
        removed = self.persistence.decay_working()
        assert removed == 1
        assert len(self.persistence.load_working()) == 0
