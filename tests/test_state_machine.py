"""Tests for the session state machine."""

import pytest
from unittest.mock import patch, MagicMock

from tektos.state_machine import (
    State,
    InvalidTransitionError,
    Transition,
    StateMachine,
    StateChange,
    get_state_machine,
    reset_state_machine,
    VALID_TRANSITIONS,
)


class TestState:
    """Tests for State enum."""

    def test_all_states_exist(self):
        assert hasattr(State, "CREATED")
        assert hasattr(State, "READY")
        assert hasattr(State, "RUNNING")
        assert hasattr(State, "INTERRUPTED")
        assert hasattr(State, "FAILED")
        assert hasattr(State, "IDLE")

    def test_state_values(self):
        assert State.CREATED.value == "created"
        assert State.READY.value == "ready"
        assert State.RUNNING.value == "running"
        assert State.INTERRUPTED.value == "interrupted"
        assert State.FAILED.value == "failed"
        assert State.IDLE.value == "idle"

    def test_state_from_string(self):
        assert State("created") == State.CREATED
        assert State("ready") == State.READY
        assert State("running") == State.RUNNING


class TestTransition:
    """Tests for Transition dataclass."""

    def test_transition_creation(self):
        t = Transition(State.CREATED, State.READY, "Initial transition")
        assert t.from_state == State.CREATED
        assert t.to_state == State.READY
        assert t.description == "Initial transition"

    def test_transition_defaults(self):
        t = Transition(State.CREATED, State.READY)
        assert t.description == ""

    def test_transition_is_frozen(self):
        t = Transition(State.CREATED, State.READY)
        with pytest.raises(Exception):
            t.from_state = State.RUNNING


class TestValidTransitions:
    """Tests for VALID_TRANSITIONS list."""

    def test_all_transitions_defined(self):
        assert len(VALID_TRANSITIONS) > 0

    def test_all_transitions_are_transition_instances(self):
        for t in VALID_TRANSITIONS:
            assert isinstance(t, Transition)

    def test_expected_transitions_exist(self):
        """Verify all documented transitions are present."""
        from_states = {t.from_state for t in VALID_TRANSITIONS}
        assert State.CREATED in from_states
        assert State.READY in from_states
        assert State.RUNNING in from_states
        assert State.INTERRUPTED in from_states

    def test_no_duplicate_transitions(self):
        transitions = [(t.from_state, t.to_state) for t in VALID_TRANSITIONS]
        assert len(transitions) == len(set(transitions))


class TestStateMachine:
    """Tests for StateMachine class."""

    def setup_method(self):
        """Create a fresh StateMachine for each test."""
        self.sm = StateMachine()

    def test_initial_state(self):
        """New session should default to CREATED."""
        state = self.sm.get_state("session-1")
        assert state == State.CREATED

    def test_transition_created_to_ready(self):
        """Valid transition: created → ready."""
        change = self.sm.transition("session-1", State.READY, "test")
        assert change.from_state == "created"
        assert change.to_state == "ready"
        assert change.reason == "test"
        assert self.sm.get_state("session-1") == State.READY

    def test_transition_ready_to_running(self):
        """Valid transition: ready → running."""
        self.sm.transition("session-1", State.READY)
        change = self.sm.transition("session-1", State.RUNNING, "processing")
        assert change.to_state == "running"
        assert self.sm.get_state("session-1") == State.RUNNING

    def test_transition_running_to_ready(self):
        """Valid transition: running → ready."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-1", State.RUNNING)
        change = self.sm.transition("session-1", State.READY, "completed")
        assert change.to_state == "ready"

    def test_transition_running_to_failed(self):
        """Valid transition: running → failed."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-1", State.RUNNING)
        change = self.sm.transition("session-1", State.FAILED, "error")
        assert change.to_state == "failed"

    def test_transition_running_to_interrupted(self):
        """Valid transition: running → interrupted."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-1", State.RUNNING)
        change = self.sm.transition("session-1", State.INTERRUPTED, "user stop")
        assert change.to_state == "interrupted"

    def test_transition_interrupted_to_ready(self):
        """Valid transition: interrupted → ready."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-1", State.RUNNING)
        self.sm.transition("session-1", State.INTERRUPTED)
        change = self.sm.transition("session-1", State.READY, "resumed")
        assert change.to_state == "ready"

    def test_transition_ready_to_idle(self):
        """Valid transition: ready → idle."""
        self.sm.transition("session-1", State.READY)
        change = self.sm.transition("session-1", State.IDLE, "no connections")
        assert change.to_state == "idle"

    def test_invalid_transition_raises_error(self):
        """Invalid transition should raise InvalidTransitionError."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-1", State.RUNNING)
        with pytest.raises(InvalidTransitionError):
            self.sm.transition("session-1", State.CREATED)  # running → created is invalid

    def test_invalid_transition_running_to_created(self):
        """Cannot transition from running back to created."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-1", State.RUNNING)
        with pytest.raises(InvalidTransitionError):
            self.sm.transition("session-1", State.CREATED)

    def test_invalid_transition_failed_to_running(self):
        """Cannot transition from failed to running."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-1", State.RUNNING)
        self.sm.transition("session-1", State.FAILED)
        with pytest.raises(InvalidTransitionError):
            self.sm.transition("session-1", State.RUNNING)

    def test_string_state_input(self):
        """StateMachine should accept string state names."""
        change = self.sm.transition("session-1", "ready", "test")
        assert change.to_state == "ready"
        assert self.sm.get_state("session-1") == State.READY

    def test_history_records_transitions(self):
        """Transition history should be recorded."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-1", State.RUNNING)
        self.sm.transition("session-1", State.READY)

        history = self.sm.get_history("session-1")
        assert len(history) == 3
        assert history[0].to_state == "ready"
        assert history[1].to_state == "running"
        assert history[2].to_state == "ready"

    def test_history_isolation_between_sessions(self):
        """History should be isolated per session."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-2", State.READY)
        self.sm.transition("session-2", State.RUNNING)

        assert len(self.sm.get_history("session-1")) == 1
        assert len(self.sm.get_history("session-2")) == 2

    def test_stats(self):
        """Stats should track transitions and invalid attempts."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-1", State.RUNNING)
        self.sm.transition("session-2", State.READY)

        stats = self.sm.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["transitions_completed"] == 3
        assert stats["invalid_attempts"] == 0

    def test_stats_with_invalid_attempts(self):
        """Stats should track invalid transition attempts."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-1", State.RUNNING)
        try:
            self.sm.transition("session-1", State.CREATED)  # running → created is invalid
        except InvalidTransitionError:
            pass

        stats = self.sm.get_stats()
        assert stats["invalid_attempts"] == 1

    def test_stats_state_distribution(self):
        """Stats should show state distribution."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-2", State.READY)
        self.sm.transition("session-3", State.READY)
        self.sm.transition("session-3", State.RUNNING)

        stats = self.sm.get_stats()
        assert stats["state_distribution"]["ready"] == 2
        assert stats["state_distribution"]["running"] == 1

    def test_is_valid_transition_static(self):
        """Static method should check valid transitions."""
        assert StateMachine.is_valid_transition(State.CREATED, State.READY) is True
        assert StateMachine.is_valid_transition(State.READY, State.RUNNING) is True
        assert StateMachine.is_valid_transition(State.RUNNING, State.READY) is True
        assert StateMachine.is_valid_transition(State.RUNNING, State.FAILED) is True
        assert StateMachine.is_valid_transition(State.RUNNING, State.INTERRUPTED) is True
        assert StateMachine.is_valid_transition(State.INTERRUPTED, State.READY) is True
        assert StateMachine.is_valid_transition(State.READY, State.IDLE) is True

        # Invalid transitions
        assert StateMachine.is_valid_transition(State.CREATED, State.RUNNING) is False
        assert StateMachine.is_valid_transition(State.FAILED, State.RUNNING) is False
        assert StateMachine.is_valid_transition(State.IDLE, State.RUNNING) is False

    def test_is_valid_transition_with_strings(self):
        """Static method should accept string states."""
        assert StateMachine.is_valid_transition("created", "ready") is True
        assert StateMachine.is_valid_transition("ready", "running") is True
        assert StateMachine.is_valid_transition("running", "created") is False

    def test_get_allowed_transitions(self):
        """Should return allowed next states for a given state."""
        allowed = self.sm.get_allowed_transitions(State.CREATED)
        assert "ready" in allowed

        allowed = self.sm.get_allowed_transitions(State.READY)
        assert "running" in allowed
        assert "idle" in allowed

        allowed = self.sm.get_allowed_transitions(State.RUNNING)
        assert "ready" in allowed
        assert "failed" in allowed
        assert "interrupted" in allowed

        allowed = self.sm.get_allowed_transitions(State.INTERRUPTED)
        assert "ready" in allowed

    def test_multiple_sessions_independent(self):
        """Multiple sessions should be independent."""
        self.sm.transition("session-1", State.READY)
        self.sm.transition("session-2", State.READY)
        self.sm.transition("session-2", State.RUNNING)

        assert self.sm.get_state("session-1") == State.READY
        assert self.sm.get_state("session-2") == State.RUNNING

    def test_transition_emits_event(self):
        """Transition should emit state_change event to event bus."""
        mock_bus = MagicMock()
        with patch("tektos.state_machine.get_event_bus", return_value=mock_bus):
            self.sm.transition("session-1", State.READY, "test")
            mock_bus.publish.assert_called_once()
            call_args = mock_bus.publish.call_args
            assert call_args[0][0] == "session.state_change"
            assert call_args[0][1] == "session-1"
            assert call_args[0][2]["from_state"] == "created"
            assert call_args[0][2]["to_state"] == "ready"

    def test_transition_event_failure_does_not_crash(self):
        """Event bus failure should not prevent transition."""
        with patch("tektos.state_machine.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock()
            mock_bus.publish.side_effect = Exception("bus error")
            mock_get_bus.return_value = mock_bus

            # Should not raise
            change = self.sm.transition("session-1", State.READY, "test")
            assert change.to_state == "ready"

    def test_timestamp_mono_is_set(self):
        """StateChange should have timestamp_mono set."""
        change = self.sm.transition("session-1", State.READY)
        assert change.timestamp_mono > 0
        assert isinstance(change.timestamp_mono, float)

    def test_timestamp_is_iso_string(self):
        """StateChange timestamp should be ISO format string."""
        change = self.sm.transition("session-1", State.READY)
        # Should parse as valid ISO timestamp
        from datetime import datetime
        dt = datetime.fromisoformat(change.timestamp)
        assert dt is not None


class TestSingleton:
    """Tests for get_state_machine and reset_state_machine."""

    def setup_method(self):
        reset_state_machine()

    def teardown_method(self):
        reset_state_machine()

    def test_get_state_machine_creates_singleton(self):
        sm1 = get_state_machine()
        sm2 = get_state_machine()
        assert sm1 is sm2

    def test_reset_state_machine_clears_singleton(self):
        sm1 = get_state_machine()
        reset_state_machine()
        sm2 = get_state_machine()
        assert sm1 is not sm2

    def test_reset_clears_state(self):
        sm = get_state_machine()
        sm.transition("session-1", State.READY)
        reset_state_machine()

        sm2 = get_state_machine()
        assert sm2.get_state("session-1") == State.CREATED
