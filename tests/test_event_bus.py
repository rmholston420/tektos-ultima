"""Tests for event_bus.py convenience functions and callback exception handling."""

from unittest.mock import MagicMock, patch

import pytest

from src.tektos.event_bus import (
    EventBus,
    publish,
    subscribe,
    unsubscribe,
    get_event_bus,
    reset_event_bus,
)


class TestEventBusConvenienceFunctions:
    """Cover event_bus.py lines 190-202: convenience functions for global bus."""

    def setup_method(self):
        """Reset global event bus before each test."""
        reset_event_bus()

    def teardown_method(self):
        """Clear global event bus after each test."""
        reset_event_bus()

    def test_subscribe_convenience(self):
        """subscribe() convenience function works."""
        callback = MagicMock()
        sub_id = subscribe("test.event", callback, "test-sub")
        assert isinstance(sub_id, str)
        assert len(sub_id) > 0

    def test_publish_convenience(self):
        """publish() convenience function delivers events."""
        callback = MagicMock()
        subscribe("publish.test", callback, "pub-sub")
        publish("publish.test", "session-1", {"key": "value"})
        callback.assert_called_once()

    def test_unsubscribe_convenience(self):
        """unsubscribe() convenience function works."""
        callback = MagicMock()
        sub_id = subscribe("unsubscribe.test", callback, "unsub-sub")
        result = unsubscribe(sub_id)
        assert result is True

    def test_unsubscribe_convenience_returns_false(self):
        """unsubscribe() returns False for invalid ID."""
        result = unsubscribe("nonexistent-subscription-id")
        assert result is False


class TestEventBusCallbackException:
    """Cover event_bus.py lines 136-137: exception handling in subscriber callbacks."""

    def test_callback_exception_logged(self):
        """Exception in callback is logged but doesn't crash the bus."""
        bus = EventBus()

        def bad_callback(event):
            raise ValueError("intentional error")

        sub_id = bus.subscribe("exception.test", bad_callback, "bad-sub")
        assert sub_id is not None

        # This should NOT raise — the bus catches callback exceptions
        bus.publish("exception.test", "session-1", {"data": "test"})

    def test_callback_exception_doesnt_block_other_subscribers(self):
        """Bad callback doesn't prevent delivery to other subscribers."""
        bus = EventBus()
        good_callback = MagicMock()

        def bad_callback(event):
            raise ValueError("bad")

        bus.subscribe("no_block.test", bad_callback, "bad-sub")
        sub_id = bus.subscribe("no_block.test", good_callback, "good-sub")
        assert sub_id is not None

        bus.publish("no_block.test", "session-1", {"data": "test"})
        good_callback.assert_called_once()
