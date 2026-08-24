"""
EventEmitter - A flexible event emission system supporting
method chaining, wildcard events, and error handling.

Usage:
    emitter = EventEmitter()
    emitter.on('event', callback).emit('event', arg1, arg2)
"""

import fnmatch
import logging
import sys
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class EventEmitter:
    """
    An event emitter supporting multiple listeners, wildcard events,
    one-time listeners, and method chaining.

    Attributes:
        listeners: A dictionary mapping event names to lists of callbacks.
        wildcard_listeners: A dictionary mapping wildcard patterns to
                            lists of callbacks.
    """

    def __init__(self) -> None:
        """Initialize the EventEmitter with empty listener registries."""
        self.listeners: Dict[str, List[Callable]] = {}
        self.wildcard_listeners: Dict[str, List[Callable]] = {}

    def _is_wildcard(self, event: str) -> bool:
        """Check if an event string contains wildcard characters."""
        return "*" in event or "?" in event or "[" in event

    def on(self, event: str, callback: Callable) -> "EventEmitter":
        """
        Register a listener for the given event.

        If the event name contains wildcard characters (e.g. 'user.*'),
        the callback is registered as a wildcard listener and will fire
        for any event matching that pattern.

        Args:
            event: The event name (or pattern) to listen for.
            callback: The function to call when the event is emitted.

        Returns:
            self for method chaining.

        Example:
            emitter.on('user.login', lambda u: print(f'{u} logged in'))
            emitter.on('user.*', lambda e, **kw: print(f'{e} happened'))
        """
        # Wildcard listeners are stored separately
        if self._is_wildcard(event):
            if event not in self.wildcard_listeners:
                self.wildcard_listeners[event] = []
            self.wildcard_listeners[event].append(callback)
            return self

        # Direct listeners
        if event in self.wildcard_listeners:
            raise ValueError(
                f"Cannot register direct listener for '{event}' "
                f"when a wildcard listener for '{event}' already exists."
            )

        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append(callback)
        return self

    def off(self, event: str, callback: Callable) -> "EventEmitter":
        """
        Remove a specific listener from the given event.

        Args:
            event: The event name to remove the listener from.
            callback: The callback function to remove.

        Returns:
            self for method chaining.

        Example:
            emitter.off('user.login', my_callback)
        """
        if self._is_wildcard(event):
            if event in self.wildcard_listeners and callback in self.wildcard_listeners[event]:
                self.wildcard_listeners[event].remove(callback)
                if not self.wildcard_listeners[event]:
                    del self.wildcard_listeners[event]
        else:
            if event in self.listeners and callback in self.listeners[event]:
                self.listeners[event].remove(callback)
                if not self.listeners[event]:
                    del self.listeners[event]
        return self

    def once(self, event: str, callback: Callable) -> "EventEmitter":
        """
        Register a one-time listener that will be called at most once.

        The callback is automatically removed after it is called.

        Args:
            event: The event name to listen for.
            callback: The function to call once when the event is emitted.

        Returns:
            self for method chaining.

        Example:
            emitter.once('shutdown', lambda: print('Shutting down...'))
        """

        def wrapped_callback(*args, **kwargs):
            """Wrapper that removes itself after first invocation."""
            self.off(event, wrapped_callback)
            callback(*args, **kwargs)

        return self.on(event, wrapped_callback)

    def remove_all(self, event: Optional[str] = None) -> "EventEmitter":
        """
        Remove all listeners for a specific event, or all events if none given.

        Args:
            event: The event name to clear. If None, removes all listeners
                   across all events.

        Returns:
            self for method chaining.

        Example:
            emitter.remove_all('user')        # remove all 'user' listeners
            emitter.remove_all()              # remove everything
        """
        if event is not None:
            self.listeners.pop(event, None)
        else:
            self.listeners.clear()
            self.wildcard_listeners.clear()
        return self

    def _match_wildcard(self, pattern: str, event: str) -> bool:
        """
        Check if an event name matches a wildcard pattern.

        Supports simple glob-style wildcards via fnmatch:
        - '*' matches any sequence of characters
        - '?' matches any single character
        - '[seq]' matches any character in seq

        Args:
            pattern: The wildcard pattern (e.g., 'user.*').
            event: The event name to test (e.g., 'user.login').

        Returns:
            True if the event matches the pattern.
        """
        return fnmatch.fnmatch(event, pattern)

    def _emit_with_wildcards(self, event: str, *args, **kwargs) -> List:
        """
        Emit to all wildcard listeners that match the given event.

        Args:
            event: The event name to match against wildcards.
            *args: Positional arguments to pass to listeners.
            **kwargs: Keyword arguments to pass to listeners.

        Returns:
            A list of results from all wildcard listener calls.
        """
        results = []

        for pattern, callbacks in list(self.wildcard_listeners.items()):
            if self._match_wildcard(pattern, event):
                for callback in list(callbacks):
                    try:
                        result = callback(event, *args, **kwargs)
                        results.append(result)
                    except Exception as exc:
                        logger.error(
                            "Wildcard listener error for '%s' -> '%s': %s",
                            pattern,
                            event,
                            exc,
                        )

        return results

    def emit(self, event: str, *args, **kwargs) -> "EventEmitter":
        """
        Trigger the given event, calling all registered listeners.

        Wildcard listeners (registered via 'on' with a pattern like
        'user.*') are invoked first, in the order they were registered
        and in the order wildcard patterns were added. Then direct
        listeners for the exact event name are called.

        If a listener raises an exception, it is logged and the
        remaining listeners for that event are still called.

        Args:
            event: The event name to emit.
            *args: Positional arguments to pass to listeners.
            **kwargs: Keyword arguments to pass to listeners.

        Returns:
            self for method chaining.

        Example:
            emitter.emit('user.login', username='alice', ip='127.0.0.1')
        """
        # First, call wildcard listeners
        self._emit_with_wildcards(event, *args, **kwargs)

        # Then, call direct listeners
        if event in self.listeners:
            for callback in list(self.listeners[event]):
                try:
                    callback(*args, **kwargs)
                except Exception as exc:
                    logger.error(
                        "Listener error for event '%s': %s", event, exc
                    )

        return self


def main() -> None:
    """Demonstrate all EventEmitter features."""
    print("=" * 60)
    print("EventEmitter Demonstration")
    print("=" * 60)

    # ----------------------------------------------------------------
    # 1. Method chaining
    # ----------------------------------------------------------------
    print("\n--- 1. Method Chaining ---")

    def greet(name: str) -> None:
        print(f"  [greet] Hello, {name}!")

    def farewell(name: str) -> None:
        print(f"  [farewell] Goodbye, {name}!")

    # Chain multiple on() calls and then emit()
    (
        EventEmitter()
        .on("greet", greet)
        .on("farewell", farewell)
        .emit("greet", "Alice")
        .emit("farewell", "Alice")
    )

    # ----------------------------------------------------------------
    # 2. Wildcard events
    # ----------------------------------------------------------------
    print("\n--- 2. Wildcard Events ---")

    emitter = EventEmitter()

    def on_user_event(event: str, **kwargs) -> None:
        print(f"  [wildcard] Event '{event}' fired with: {kwargs}")

    emitter.on("user.*", on_user_event)

    emitter.emit("user.login", username="alice")
    emitter.emit("user.logout", username="bob")
    emitter.emit("user.profile_updated", username="charlie", age=30)

    # ----------------------------------------------------------------
    # 3. once() listeners
    # ----------------------------------------------------------------
    print("\n--- 3. One-Time Listeners (once) ---")

    emitter2 = EventEmitter()

    call_count = 0

    def counted_callback() -> None:
        nonlocal call_count
        call_count += 1
        print(f"  [once] Called (count: {call_count})")

    emitter2.once("tick", counted_callback)

    # Call the event multiple times
    emitter2.emit("tick")  # Should print count: 1
    emitter2.emit("tick")  # Should NOT print (listener removed)
    emitter2.emit("tick")  # Should NOT print
    print(f"  [once] Final call count: {call_count}")

    # ----------------------------------------------------------------
    # 4. Error handling
    # ----------------------------------------------------------------
    print("\n--- 4. Error Handling ---")

    emitter3 = EventEmitter()

    def good_listener() -> None:
        print("  [good] Listener executed successfully")

    def bad_listener() -> None:
        raise ValueError("Intentional error in listener!")

    def another_good_listener() -> None:
        print("  [good] This listener still runs after the error")

    emitter3.on("dangerous", good_listener)
    emitter3.on("dangerous", bad_listener)
    emitter3.on("dangerous", another_good_listener)

    print("  Emitting 'dangerous' event (bad listener in the middle):")
    emitter3.emit("dangerous")

    # Wildcard error handling
    def bad_wildcard(*args, **kwargs):
        raise RuntimeError("Wildcard listener failed!")

    emitter3.on("system.*", bad_wildcard)
    emitter3.on("system.*", lambda *a, **k: print("  [good-wild] Wildcard still works"))

    print("  Emitting 'system.crash' (bad wildcard listener):")
    emitter3.emit("system.crash")

    # ----------------------------------------------------------------
    # 5. remove_all()
    # ----------------------------------------------------------------
    print("\n--- 5. remove_all() ---")

    emitter4 = EventEmitter()

    def listener_a() -> None:
        print("  [removed] Listener A was called (should not happen)")

    def listener_b() -> None:
        print("  [alive] Listener B is still registered")

    emitter4.on("test_event", listener_a)
    emitter4.on("test_event", listener_b)

    print("  Before remove_all:")
    emitter4.emit("test_event")

    emitter4.remove_all("test_event")

    print("  After remove_all('test_event'):")
    emitter4.emit("test_event")

    # Clear everything
    emitter4.on("other", lambda: print("  [other] Other event"))
    emitter4.remove_all()
    print("  After remove_all() (no args):")
    emitter4.emit("other")  # Should not print anything
    print("  [info] No output above confirms all listeners removed.")

    # ----------------------------------------------------------------
    # 6. off() removes a specific listener
    # ----------------------------------------------------------------
    print("\n--- 6. off() - Remove Specific Listener ---")

    emitter5 = EventEmitter()

    def first_cb() -> None:
        print("  [cb1] First callback")

    def second_cb() -> None:
        print("  [cb2] Second callback")

    emitter5.on("specific", first_cb).on("specific", second_cb)

    print("  Before off():")
    emitter5.emit("specific")

    emitter5.off("specific", first_cb)

    print("  After off('specific', first_cb):")
    emitter5.emit("specific")

    print("\n" + "=" * 60)
    print("All demonstrations complete.")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")
    main()
