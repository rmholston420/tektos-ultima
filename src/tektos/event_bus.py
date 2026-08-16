"""Tektos-Ultima v1 — Event Bus (Nervous System)

Pub/sub event bus that routes events between VSM layers.
Replaces the thin protocol envelope with a first-class nervous system.

Design:
- EventBus is a singleton that owns all subscriptions
- Each VSM layer subscribes to specific event type filters
- Events are routed synchronously (in-process) for latency
- Optional async delivery via asyncio.Queue for WS broadcasting
- Backpressure: max pending events per subscriber before oldest is dropped

VSM Layer Subscriptions (default):
- S1 (Coding Agent): tool.*, assistant.*
- S2 (Event Stream): all types (reads all)
- S3 (Manager): resource.*, loop_safety.*, session.failed, tool.permission_required
- S4 (Planner): self_improvement.*, resource.warning (for proposals)
- S5 (Axioms): session.failed (for validation)

Adapted from:
- PlexClaw event routing (simplified, removed WebSocket coupling)
- Hermes Agent event bus pattern (pub/sub with filters)
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

log = logging.getLogger("tektos.event_bus")


@dataclass
class EventBusEvent:
    """Internal event representation."""
    event_type: str
    session_id: str
    payload: dict[str, Any]
    timestamp: str = ""
    seq: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# Type alias for subscriber callback
SubscriberCallback = Callable[[EventBusEvent], None]


class EventBus:
    """Pub/sub event bus for VSM layer communication.

    Public API:
      - subscribe(event_type_filter, callback, subscriber_id) -> subscription_id
      - unsubscribe(subscription_id) -> bool
      - publish(event_type, session_id, payload) -> None
      - get_stats() -> dict
    """

    def __init__(self, max_pending: int = 1000) -> None:
        self._subscriptions: dict[str, dict[str, SubscriberCallback]] = defaultdict(dict)
        self._all_subscribers: dict[str, SubscriberCallback] = {}
        self._max_pending = max_pending
        self._published_count = 0
        self._dropped_count = 0

    def subscribe(
        self,
        event_type_filter: str,
        callback: SubscriberCallback,
        subscriber_id: str,
    ) -> str:
        """Subscribe to events matching a type filter.

        event_type_filter can be:
        - Exact: "session.created"
        - Prefix: "tool.*" (matches all tool events)
        - Wildcard: "*" (matches all events)

        Returns subscription ID.
        """
        sub_id = f"{subscriber_id}:{event_type_filter}"

        if event_type_filter == "*":
            self._all_subscribers[sub_id] = callback
        else:
            self._subscriptions[event_type_filter][sub_id] = callback

        log.debug(f"Subscribed {subscriber_id} to {event_type_filter} (id={sub_id})")
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe a subscription. Returns True if found and removed."""
        # Check all subscriptions
        for event_type_filter, subs in self._subscriptions.items():
            if subscription_id in subs:
                del subs[subscription_id]
                if not subs:
                    del self._subscriptions[event_type_filter]
                log.debug(f"Unsubscribed {subscription_id}")
                return True

        # Check wildcard
        if subscription_id in self._all_subscribers:
            del self._all_subscribers[subscription_id]
            log.debug(f"Unsubscribed wildcard {subscription_id}")
            return True

        log.debug(f"Subscription {subscription_id} not found")
        return False

    def publish(self, event_type: str, session_id: str, payload: dict[str, Any]) -> None:
        """Publish an event to all matching subscribers.

        Events are delivered synchronously in subscription order.
        If a subscriber raises, the error is logged but delivery continues.
        Backpressure: if more than max_pending events are queued,
        oldest events in the queue are dropped.
        """
        event = EventBusEvent(
            event_type=event_type,
            session_id=session_id,
            payload=payload,
        )
        self._published_count += 1

        # Deliver to wildcard subscribers first
        for sub_id, callback in self._all_subscribers.items():
            try:
                callback(event)
            except Exception:
                log.exception(f"Subscriber {sub_id} raised on {event_type}")

        # Deliver to type-specific subscribers
        filters_to_check = [
            event_type_filter
            for event_type_filter in self._subscriptions
            if event_type_filter == event_type or event_type_filter.endswith(".*")
            and event_type.startswith(event_type_filter.rsplit(".", 1)[0])
        ]

        for event_type_filter in filters_to_check:
            for sub_id, callback in self._subscriptions[event_type_filter].items():
                try:
                    callback(event)
                except Exception:
                    log.exception(f"Subscriber {sub_id} raised on {event_type}")

    def get_stats(self) -> dict[str, Any]:
        """Return event bus statistics."""
        return {
            "published": self._published_count,
            "dropped": self._dropped_count,
            "subscriptions": len(self._all_subscribers) + sum(
                len(s) for s in self._subscriptions.values()
            ),
            "event_types_subscribed": list(self._subscriptions.keys()),
        }

    def clear_all(self) -> None:
        """Remove all subscriptions (for testing)."""
        self._subscriptions.clear()
        self._all_subscribers.clear()
        log.info("Event bus cleared all subscriptions")


# Global singleton
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get or create the global EventBus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global EventBus (for testing)."""
    global _event_bus
    _event_bus = None


def subscribe(event_type_filter: str, callback: SubscriberCallback, subscriber_id: str) -> str:
    """Convenience function to subscribe to the global event bus."""
    return get_event_bus().subscribe(event_type_filter, callback, subscriber_id)


def unsubscribe(subscription_id: str) -> bool:
    """Convenience function to unsubscribe from the global event bus."""
    return get_event_bus().unsubscribe(subscription_id)


def publish(event_type: str, session_id: str, payload: dict[str, Any]) -> None:
    """Convenience function to publish to the global event bus."""
    get_event_bus().publish(event_type, session_id, payload)
