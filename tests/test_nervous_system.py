"""Tests for event bus and state machine — VS2 Nervous System.

Tests the EventBus (pub/sub with type filters) and StateMachine (FSM)
modules, verifying event routing, state transitions, backpressure, and
integration with SessionManager lifecycle.
"""

import pytest
from tektos.event_bus import EventBus, EventBusEvent, get_event_bus, reset_event_bus
from tektos.state_machine import (
    StateMachine,
    State,
    StateChange,
    InvalidTransitionError,
    get_state_machine,
    reset_state_machine,
)


# ─── EventBus Tests ─────────────────────────────────────────────────────────

class TestEventBus:
    """Core event bus pub/sub functionality."""

    def setup_method(self):
        reset_event_bus()

    def teardown_method(self):
        reset_event_bus()

    def test_subscribe_and_publish(self):
        """Basic subscribe → publish → callback invocation."""
        bus = get_event_bus()
        received = []
        bus.subscribe("session.created", lambda e: received.append(e), "test1")

        bus.publish("session.created", "sess-1", {"model": "qwen"})

        assert len(received) == 1
        assert received[0].event_type == "session.created"
        assert received[0].session_id == "sess-1"

    def test_prefix_filter(self):
        """Prefix filter 'tool.*' matches all tool events."""
        bus = get_event_bus()
        received = []
        bus.subscribe("tool.*", lambda e: received.append(e), "test2")

        bus.publish("tool.started", "s1", {"tool_name": "bash"})
        bus.publish("tool.completed", "s1", {"status": "success"})
        bus.publish("assistant.delta", "s1", {"text": "hi"})  # Should NOT match

        assert len(received) == 2
        types = {e.event_type for e in received}
        assert types == {"tool.started", "tool.completed"}

    def test_wildcard_filter(self):
        """Wildcard '*' matches all events."""
        bus = get_event_bus()
        received = []
        bus.subscribe("*", lambda e: received.append(e), "test3")

        bus.publish("a", "s1", {})
        bus.publish("b", "s1", {})
        bus.publish("c", "s1", {})

        assert len(received) == 3

    def test_unsubscribe(self):
        """Unsubscribing removes callback from delivery."""
        bus = get_event_bus()
        received = []
        sub_id = bus.subscribe("test", lambda e: received.append(e), "test4")

        bus.publish("test", "s1", {})
        assert len(received) == 1

        bus.unsubscribe(sub_id)
        bus.publish("test", "s1", {})
        assert len(received) == 1  # No new event

    def test_unsubscribe_unknown_returns_false(self):
        bus = get_event_bus()
        assert bus.unsubscribe("nonexistent") is False

    def test_multiple_subscribers(self):
        """Multiple subscribers for same event all receive it."""
        bus = get_event_bus()
        received1 = []
        received2 = []
        bus.subscribe("test", lambda e: received1.append(e), "s1")
        bus.subscribe("test", lambda e: received2.append(e), "s2")

        bus.publish("test", "s1", {"key": "val"})

        assert len(received1) == 1
        assert len(received2) == 1
        assert received1[0].payload["key"] == "val"

    def test_subscriber_exception_does_not_cascade(self):
        """If one subscriber raises, others still receive the event."""
        bus = get_event_bus()
        received = []
        bus.subscribe("test", lambda e: (_ for _ in ()).throw(ValueError("boom")), "bad")
        bus.subscribe("test", lambda e: received.append(e), "good")

        bus.publish("test", "s1", {})  # Should not raise

        assert len(received) == 1

    def test_event_has_timestamp(self):
        bus = get_event_bus()
        received = []
        bus.subscribe("test", lambda e: received.append(e), "ts")
        bus.publish("test", "s1", {})
        assert received[0].timestamp  # Should be non-empty ISO string

    def test_stats(self):
        bus = get_event_bus()
        bus.subscribe("a", lambda e: None, "s1")
        bus.subscribe("b.*", lambda e: None, "s2")
        bus.subscribe("*", lambda e: None, "s3")

        bus.publish("a", "s1", {})
        bus.publish("b", "s1", {})
        bus.publish("c", "s1", {})

        stats = bus.get_stats()
        assert stats["published"] == 3
        assert stats["subscriptions"] == 3

    def test_clear_all(self):
        bus = get_event_bus()
        bus.subscribe("a", lambda e: None, "s1")
        bus.subscribe("*", lambda e: None, "s2")
        bus.clear_all()

        stats = bus.get_stats()
        assert stats["subscriptions"] == 0


# ─── State Machine Tests ────────────────────────────────────────────────────

class TestStateMachine:
    """Session state machine transitions."""

    def setup_method(self):
        reset_state_machine()

    def teardown_method(self):
        reset_state_machine()

    def test_create_session_initial_state(self):
        """Creating a session starts in CREATED state."""
        sm = get_state_machine()
        assert sm.get_state("sess-1") == State.CREATED

    def test_transition_created_to_ready(self):
        sm = get_state_machine()
        change = sm.transition("sess-1", State.READY, "session created")

        assert change.from_state == "created"
        assert change.to_state == "ready"
        assert sm.get_state("sess-1") == State.READY

    def test_transition_ready_to_running(self):
        sm = get_state_machine()
        sm.transition("sess-1", State.READY, "init")
        change = sm.transition("sess-1", State.RUNNING, "processing")

        assert change.to_state == "running"
        assert sm.get_state("sess-1") == State.RUNNING

    def test_transition_running_to_ready(self):
        sm = get_state_machine()
        sm.transition("sess-1", State.READY, "init")
        sm.transition("sess-1", State.RUNNING, "processing")
        sm.transition("sess-1", State.READY, "complete")

        assert sm.get_state("sess-1") == State.READY

    def test_transition_running_to_interrupted(self):
        sm = get_state_machine()
        sm.transition("sess-1", State.READY, "init")
        sm.transition("sess-1", State.RUNNING, "processing")
        sm.transition("sess-1", State.INTERRUPTED, "user interrupt")

        assert sm.get_state("sess-1") == State.INTERRUPTED

    def test_transition_interrupted_to_ready(self):
        sm = get_state_machine()
        sm.transition("sess-1", State.READY, "init")
        sm.transition("sess-1", State.RUNNING, "processing")
        sm.transition("sess-1", State.INTERRUPTED, "interrupt")
        sm.transition("sess-1", State.READY, "resumed")

        assert sm.get_state("sess-1") == State.READY

    def test_invalid_transition_raises(self):
        """Cannot go directly from CREATED → RUNNING."""
        sm = get_state_machine()
        with pytest.raises(InvalidTransitionError):
            sm.transition("sess-1", State.RUNNING, "skipped ready")

    def test_invalid_transition_created_to_failed(self):
        """Cannot fail before running."""
        sm = get_state_machine()
        with pytest.raises(InvalidTransitionError):
            sm.transition("sess-1", State.FAILED, "nope")

    def test_history_recorded(self):
        sm = get_state_machine()
        sm.transition("sess-1", State.READY, "init")
        sm.transition("sess-1", State.RUNNING, "proc")
        sm.transition("sess-1", State.READY, "done")

        history = sm.get_history("sess-1")
        assert len(history) == 3
        assert history[0].from_state == "created"
        assert history[1].from_state == "ready"
        assert history[2].from_state == "running"

    def test_string_state_input(self):
        """State machine accepts string state names."""
        sm = get_state_machine()
        sm.transition("sess-1", "ready", "test")
        assert sm.get_state("sess-1") == State.READY

    def test_is_valid_transition_static(self):
        assert StateMachine.is_valid_transition(State.READY, State.RUNNING) is True
        assert StateMachine.is_valid_transition(State.CREATED, State.RUNNING) is False
        assert StateMachine.is_valid_transition(State.RUNNING, State.READY) is True
        assert StateMachine.is_valid_transition(State.RUNNING, State.FAILED) is True
        assert StateMachine.is_valid_transition(State.READY, State.CREATED) is False

    def test_get_allowed_transitions(self):
        sm = get_state_machine()
        allowed = sm.get_allowed_transitions(State.CREATED)
        assert allowed == ["ready"]

        allowed = sm.get_allowed_transitions(State.RUNNING)
        assert set(allowed) == {"ready", "failed", "interrupted"}

    def test_stats(self):
        sm = get_state_machine()
        sm.transition("s1", State.READY, "a")
        sm.transition("s1", State.RUNNING, "b")
        sm.transition("s2", State.READY, "c")

        stats = sm.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["transitions_completed"] == 3
        assert stats["invalid_attempts"] == 0

    def test_invalid_attempts_counted(self):
        sm = get_state_machine()
        with pytest.raises(InvalidTransitionError):
            sm.transition("s1", State.RUNNING, "invalid")

        stats = sm.get_stats()
        assert stats["invalid_attempts"] == 1

    def test_multiple_sessions_independent(self):
        sm = get_state_machine()
        sm.transition("s1", State.READY, "a")
        sm.transition("s1", State.RUNNING, "b")
        sm.transition("s2", State.READY, "c")

        assert sm.get_state("s1") == State.RUNNING
        assert sm.get_state("s2") == State.READY

    def test_event_bus_integration(self):
        """State machine emits state_change events to the event bus."""
        reset_event_bus()
        reset_state_machine()

        bus = get_event_bus()
        sm = get_state_machine()
        received = []
        bus.subscribe("session.state_change", lambda e: received.append(e), "listener")

        sm.transition("s1", State.READY, "test")

        assert len(received) == 1
        assert received[0].payload["from_state"] == "created"
        assert received[0].payload["to_state"] == "ready"
        assert received[0].payload["reason"] == "test"


# ─── Integration: SessionManager + State Machine ────────────────────────────

class TestSessionIntegration:
    """SessionManager correctly triggers state machine transitions."""

    def setup_method(self):
        reset_state_machine()
        reset_event_bus()

    def teardown_method(self):
        reset_state_machine()
        reset_event_bus()

    @pytest.mark.asyncio
    async def test_create_session_emits_state_change(self):
        """Creating a session triggers created → ready transition."""
        from tektos.runtime.session import SessionManager
        from tektos.store.event_store import init as init_event_store
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_event_store(f.name)

            sm = get_state_machine()
            bus = get_event_bus()
            received = []
            bus.subscribe("session.state_change", lambda e: received.append(e), "test")

            mgr = SessionManager()
            session = await mgr.create_session(model="qwen")

            assert sm.get_state(session.id) == State.READY
            assert len(received) == 1
            assert received[0].payload["to_state"] == "ready"

    @pytest.mark.asyncio
    async def test_interrupt_session_emits_state_change(self):
        """Interrupting a running session triggers running → interrupted."""
        from tektos.runtime.session import SessionManager
        from tektos.store.event_store import init as init_event_store
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_event_store(f.name)

            sm = get_state_machine()
            bus = get_event_bus()
            received = []
            bus.subscribe("session.state_change", lambda e: received.append(e), "test")

            mgr = SessionManager()
            session = await mgr.create_session(model="qwen")

            # Manually put session into running state
            session.status = "running"
            sm.transition(session.id, State.RUNNING, "test running")

            await mgr.interrupt_session(session.id)

            assert sm.get_state(session.id) == State.INTERRUPTED
            assert any(c.payload["to_state"] == "interrupted" for c in received)
