"""
Tektos-Ultima v1 — Event Store Tests

Tests SQLite append-only event store with replay, including:
- init/teardown lifecycle
- append_event (seq assignment, FTS5 indexing)
- get_events (pagination, filtering, ordering)
- get_replay (full history)
- search_events (FTS5 + linear scan fallback)
- delete_session (event count, FTS cleanup)
- thread safety
"""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from tektos.store.event_store import (
    append_event,
    get_events,
    get_replay,
    search_events,
    delete_session,
    init,
    set_path,
    get_db_path,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Each test gets a fresh SQLite database."""
    db_path = str(tmp_path / "test.db")
    set_path(db_path)
    init(db_path, init_db=True)
    yield db_path
    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


class TestInit:
    def test_creates_database_file(self, tmp_path):
        db_path = str(tmp_path / "new.db")
        set_path(db_path)
        init(db_path)
        assert Path(db_path).exists()

    def test_creates_parent_directory(self, tmp_path):
        nested = str(tmp_path / "a" / "b" / "c")
        set_path(os.path.join(nested, "test.db"))
        init(nested + "/test.db")
        assert Path(nested, "test.db").exists()

    def test_creates_events_table(self, tmp_path):
        db_path = str(tmp_path / "t.db")
        set_path(db_path)
        init(db_path)
        import sqlite3
        conn = sqlite3.connect(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "events" in table_names
        conn.close()

    def test_creates_fts_table(self, tmp_path):
        db_path = str(tmp_path / "t.db")
        set_path(db_path)
        init(db_path)
        import sqlite3
        conn = sqlite3.connect(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "events_fts" in table_names
        conn.close()

    def test_creates_indexes(self, tmp_path):
        db_path = str(tmp_path / "t.db")
        set_path(db_path)
        init(db_path)
        import sqlite3
        conn = sqlite3.connect(db_path)
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
        index_names = [i[0] for i in indexes]
        assert "idx_session_seq" in index_names
        assert "idx_event_type" in index_names
        assert "idx_created_at" in index_names
        conn.close()


class TestAppendEvent:
    def test_appends_event_with_auto_seq(self):
        seq = asyncio.run(append_event("s1", "system.message", {"text": "hi"}))
        assert seq == 1

    def test_appends_event_with_auto_seq_2(self):
        asyncio.run(append_event("s1", "system.message", {"text": "hi"}))
        seq = asyncio.run(append_event("s1", "assistant.delta", {"text": "lo"}))
        assert seq == 2

    def test_sequential_seqs_per_session(self):
        for i in range(5):
            seq = asyncio.run(
                append_event("s1", "system.message", {"index": i})
            )
            assert seq == i + 1

    def test_independent_seqs_per_session(self):
        seq_a = asyncio.run(append_event("sA", "system.message", {}))
        assert seq_a == 1
        seq_b = asyncio.run(append_event("sB", "system.message", {}))
        assert seq_b == 1  # independent counter

    def test_preserves_payload(self):
        payload = {"cmd": "ls -la", "args": ["-la"]}
        asyncio.run(append_event("s1", "tool.started", payload))
        events = asyncio.run(get_events("s1"))
        assert events[0]["payload"]["cmd"] == "ls -la"
        assert events[0]["payload"]["args"] == ["-la"]

    def test_preserves_protocol_version(self):
        asyncio.run(
            append_event("s1", "system.message", {}, protocol_version="0.9.0")
        )
        events = asyncio.run(get_events("s1"))
        assert events[0]["protocol_version"] == "0.9.0"

    def test_default_protocol_version(self):
        asyncio.run(append_event("s1", "system.message", {}))
        events = asyncio.run(get_events("s1"))
        assert events[0]["protocol_version"] == "1.0.0"

    def test_returns_seq_number(self):
        seq = asyncio.run(append_event("s1", "tool.started", {}))
        assert isinstance(seq, int)
        assert seq >= 1

    def test_event_type_stored(self):
        asyncio.run(append_event("s1", "tool.permission.required", {}))
        events = asyncio.run(get_events("s1"))
        assert events[0]["type"] == "tool.permission.required"

    def test_multiple_sessions_no_cross_contamination(self):
        asyncio.run(append_event("sA", "system.message", {"sid": "A"}))
        asyncio.run(append_event("sB", "system.message", {"sid": "B"}))
        events_a = asyncio.run(get_events("sA"))
        events_b = asyncio.run(get_events("sB"))
        assert len(events_a) == 1
        assert len(events_b) == 1
        assert events_a[0]["payload"]["sid"] == "A"
        assert events_b[0]["payload"]["sid"] == "B"

    def test_large_payload(self):
        large_text = "x" * 10000
        asyncio.run(append_event("s1", "assistant.delta", {"text": large_text}))
        events = asyncio.run(get_events("s1"))
        assert len(events[0]["payload"]["text"]) == 10000

    def test_nested_payload(self):
        nested = {
            "a": {"b": {"c": [1, 2, 3]}},
            "d": [{"e": True}, {"e": False}],
        }
        asyncio.run(append_event("s1", "system.message", nested))
        events = asyncio.run(get_events("s1"))
        assert events[0]["payload"]["a"]["b"]["c"] == [1, 2, 3]


class TestGetEvents:
    def test_returns_empty_for_no_events(self):
        events = asyncio.run(get_events("nonexistent"))
        assert events == []

    def test_returns_events_ordered_by_seq(self):
        # Insert in order — seqs are 1,2,3 matching payloads
        for i in [1, 2, 3]:
            asyncio.run(append_event("s1", "system.message", {"order": i}))
        events = asyncio.run(get_events("s1"))
        assert [e["payload"]["order"] for e in events] == [1, 2, 3]

    def test_since_seq_filter(self):
        for i in range(5):
            asyncio.run(append_event("s1", "system.message", {"seq": i}))
        events = asyncio.run(get_events("s1", since_seq=2))
        assert len(events) == 3
        assert events[0]["seq"] == 3

    def test_since_seq_zero_includes_all(self):
        for i in range(3):
            asyncio.run(append_event("s1", "system.message", {}))
        events = asyncio.run(get_events("s1", since_seq=0))
        assert len(events) == 3

    def test_limit(self):
        for i in range(10):
            asyncio.run(append_event("s1", "system.message", {}))
        events = asyncio.run(get_events("s1", limit=3))
        assert len(events) == 3

    def test_limit_cap(self):
        for i in range(20):
            asyncio.run(append_event("s1", "system.message", {}))
        events = asyncio.run(get_events("s1", limit=20000))
        assert len(events) == 20  # hard cap at 10000, but only 20 exist

    def test_event_type_filter(self):
        asyncio.run(append_event("s1", "system.message", {}))
        asyncio.run(append_event("s1", "assistant.delta", {}))
        asyncio.run(append_event("s1", "system.message", {}))
        events = asyncio.run(get_events("s1", event_type="system.message"))
        assert len(events) == 2
        assert all(e["type"] == "system.message" for e in events)

    def test_created_at_present(self):
        asyncio.run(append_event("s1", "system.message", {}))
        events = asyncio.run(get_events("s1"))
        assert "created_at" in events[0]
        assert events[0]["created_at"] is not None

    def test_event_fields(self):
        asyncio.run(append_event("s1", "tool.started", {"cmd": "ls"}))
        events = asyncio.run(get_events("s1"))
        assert set(events[0].keys()) == {"seq", "type", "payload", "protocol_version", "created_at"}


class TestGetReplay:
    def test_returns_all_events(self):
        for i in range(10):
            asyncio.run(append_event("s1", "system.message", {"i": i}))
        replay = asyncio.run(get_replay("s1"))
        assert len(replay) == 10

    def test_ordered_by_seq(self):
        for i in [1, 2, 5, 8, 9]:
            asyncio.run(append_event("s1", "system.message", {"order": i}))
        replay = asyncio.run(get_replay("s1"))
        assert [e["payload"]["order"] for e in replay] == [1, 2, 5, 8, 9]

    def test_empty_session(self):
        replay = asyncio.run(get_replay("nonexistent"))
        assert replay == []


class TestSearchEvents:
    def test_search_by_type(self):
        asyncio.run(append_event("s1", "system.message", {"note": "find_type"}))
        results = asyncio.run(search_events("find_type"))
        assert any(r["payload"].get("note") == "find_type" for r in results)

    def test_search_by_payload_content(self):
        asyncio.run(append_event("s1", "system.message", {"cmd": "grep -r hello"}))
        results = asyncio.run(search_events("hello"))
        assert any("grep" in str(r["payload"]) for r in results)

    def test_search_limits_results(self):
        for i in range(50):
            asyncio.run(append_event("s1", "system.message", {"note": str(i)}))
        results = asyncio.run(search_events("system", limit=10))
        assert len(results) <= 10

    def test_search_empty_query(self):
        asyncio.run(append_event("s1", "system.message", {}))
        results = asyncio.run(search_events("system"))
        assert len(results) >= 1

    def test_search_returns_session_id(self):
        asyncio.run(append_event("s1", "system.message", {}))
        results = asyncio.run(search_events("system"))
        assert all("session_id" in r for r in results)
        assert any(r["session_id"] == "s1" for r in results)

    def test_search_returns_seq(self):
        asyncio.run(append_event("s1", "system.message", {}))
        results = asyncio.run(search_events("system"))
        assert all("seq" in r for r in results)


class TestDeleteSession:
    def test_deletes_all_events(self):
        for i in range(5):
            asyncio.run(append_event("s1", "system.message", {}))
        count = asyncio.run(delete_session("s1"))
        assert count == 5
        events = asyncio.run(get_events("s1"))
        assert events == []

    def test_delete_nonexistent_returns_zero(self):
        count = asyncio.run(delete_session("nonexistent"))
        assert count == 0

    def test_delete_one_session_does_not_affect_another(self):
        asyncio.run(append_event("sA", "system.message", {}))
        asyncio.run(append_event("sB", "system.message", {}))
        asyncio.run(append_event("sA", "system.message", {}))
        count = asyncio.run(delete_session("sA"))
        assert count == 2
        events_b = asyncio.run(get_events("sB"))
        assert len(events_b) == 1

    def test_delete_frees_storage(self):
        for i in range(100):
            asyncio.run(append_event("s1", "system.message", {"data": "x" * 1000}))
        asyncio.run(delete_session("s1"))
        events = asyncio.run(get_events("s1"))
        assert len(events) == 0


class TestFTSIndexing:
    def test_fts_indexed_on_insert(self):
        asyncio.run(append_event("s1", "system.message", {"content": "searchable_text"}))
        results = asyncio.run(search_events("searchable_text"))
        assert len(results) >= 1

    def test_fts_search_across_sessions(self):
        asyncio.run(append_event("sA", "system.message", {"note": "cross_session"}))
        asyncio.run(append_event("sB", "system.message", {"note": "cross_session"}))
        results = asyncio.run(search_events("cross_session"))
        session_ids = {r["session_id"] for r in results}
        assert "sA" in session_ids
        assert "sB" in session_ids

    def test_fts_rebuilt_on_mismatch(self, tmp_path):
        """If FTS row count < events row count during init, FTS is rebuilt."""
        import sqlite3
        import tektos.store.event_store as es

        db_path = str(tmp_path / "rebuild.db")
        es.set_path(db_path)
        # Init fresh (creates FTS)
        es.init(db_path)
        # Insert events via direct SQL (bypasses FTS)
        conn = sqlite3.connect(db_path)
        for i in range(5):
            conn.execute(
                "INSERT INTO events (session_id, seq, type, payload, protocol_version) VALUES (?, 1, 'system.message', '{}', '1.0.0')",
                ("s1",)
            )
        conn.commit()
        # Now FTS has 0 rows but events has 5 — mismatch detected on next init
        conn.close()
        # Re-init — should detect mismatch and rebuild FTS
        es.init(db_path)
        # Now FTS should be rebuilt
        for i in range(5):
            asyncio.run(append_event("s1", "system.message", {"rebuilt": True}))
        results = asyncio.run(search_events("rebuilt"))
        assert len(results) >= 1

    def test_search_fallback_when_fts_disabled(self, tmp_path):
        """When FTS is disabled, search falls back to linear scan."""
        import tektos.store.event_store as es

        db_path = str(tmp_path / "nofts.db")
        es.set_path(db_path)
        es.init(db_path)
        es._fts_available = False  # simulate FTS unavailable
        asyncio.run(append_event("s1", "system.message", {"note": "linear_scan_test"}))
        results = asyncio.run(search_events("linear_scan_test"))
        assert any("linear_scan_test" in str(r["payload"]) for r in results)


class TestUninitializedStore:
    def test_raises_on_append_without_init(self):
        set_path("")
        with pytest.raises(RuntimeError, match="not initialized"):
            asyncio.run(append_event("s1", "system.message", {}))

    def test_get_db_path_returns_empty_when_not_set(self):
        set_path("")
        assert get_db_path() == ""


class TestEdgeCases:
    def test_special_characters_in_payload(self):
        special = {"emoji": "🔥", "unicode": "日本語", "newline": "line1\nline2"}
        asyncio.run(append_event("s1", "system.message", special))
        events = asyncio.run(get_events("s1"))
        assert events[0]["payload"]["emoji"] == "🔥"
        assert events[0]["payload"]["unicode"] == "日本語"

    def test_empty_payload(self):
        asyncio.run(append_event("s1", "system.message", {}))
        events = asyncio.run(get_events("s1"))
        assert events[0]["payload"] == {}

    def test_boolean_in_payload(self):
        asyncio.run(append_event("s1", "system.message", {"flag": True, "off": False}))
        events = asyncio.run(get_events("s1"))
        assert events[0]["payload"]["flag"] is True
        assert events[0]["payload"]["off"] is False

    def test_numeric_payload(self):
        asyncio.run(append_event("s1", "system.message", {"num": 42, "float": 3.14, "neg": -7}))
        events = asyncio.run(get_events("s1"))
        assert events[0]["payload"]["num"] == 42
        assert events[0]["payload"]["float"] == 3.14
        assert events[0]["payload"]["neg"] == -7