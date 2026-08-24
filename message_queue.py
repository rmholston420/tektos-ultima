"""Thread-safe message queue implementation using threading primitives."""

import threading
import time
import random


class MessageQueue:
    """A thread-safe message queue supporting blocking get operations.

    Uses a threading.Lock and threading.Condition internally to ensure
    that multiple producers and consumers can safely enqueue and dequeue
    messages without race conditions.

    Attributes:
        _queue: Internal list used as the message buffer.
        _lock: Lock for mutual exclusion.
        _not_empty: Condition variable signaled when a message is added.
        _not_full: Condition variable signaled when a message is removed
            (unused here since the queue has no fixed capacity, but kept
            for API completeness).
    """

    def __init__(self) -> None:
        """Initialize an empty MessageQueue."""
        self._queue: list = []
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)

    def put(self, message: str, timeout: float | None = None) -> bool:
        """Add a message to the back of the queue.

        This method is thread-safe. It acquires the lock, appends the
        message, and notifies any thread waiting in get().

        Args:
            message: The string message to enqueue.
            timeout: Optional timeout in seconds. Not used in this
                unbounded queue, but kept for API compatibility.

        Returns:
            True if the message was enqueued successfully.
        """
        with self._lock:
            self._queue.append(message)
            self._not_empty.notify()
        return True

    def get(self, timeout: float | None = None) -> str | None:
        """Remove and return the message at the front of the queue.

        This method blocks until a message is available. If a timeout
        is specified and no message arrives within that time, returns
        None.

        Args:
            timeout: Maximum seconds to wait. None means wait forever.

        Returns:
            The dequeued message string, or None if timeout elapsed.
        """
        with self._not_empty:
            if timeout is not None:
                deadline = time.monotonic() + timeout
                while not self._queue:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return None
                    self._not_empty.wait(timeout=remaining)
            else:
                while not self._queue:
                    self._not_empty.wait()
            message = self._queue.pop(0)
            self._not_full.notify()
            return message

    def size(self) -> int:
        """Return the number of messages currently in the queue.

        Returns:
            Integer count of messages.
        """
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """Check whether the queue contains any messages.

        Returns:
            True if the queue is empty, False otherwise.
        """
        with self._lock:
            return len(self._queue) == 0


def producer(q: MessageQueue, name: str, count: int) -> None:
    """Produce messages and put them into the queue.

    Args:
        q: The MessageQueue to produce into.
        name: Producer identifier for logging.
        count: Number of messages to produce.
    """
    for i in range(count):
        message = f"{name}-msg-{i}"
        q.put(message)
        print(f"[PRODUCER {name}] Sent: {message}")
        time.sleep(random.uniform(0.01, 0.05))


def consumer(q: MessageQueue, name: str, stop_event: threading.Event) -> None:
    """Consume messages from the queue until a stop signal arrives.

    Args:
        q: The MessageQueue to consume from.
        name: Consumer identifier for logging.
        stop_event: Event that, when set, signals the consumer to exit.
    """
    while not stop_event.is_set():
        message = q.get(timeout=0.1)
        if message is not None:
            print(f"[CONSUMER {name}] Received: {message}")
        else:
            # Timeout expired - check if we should stop
            if q.is_empty() and stop_event.is_set():
                break
    # Drain any remaining messages after stop signal
    while not q.is_empty():
        message = q.get(timeout=1.0)
        if message is not None:
            print(f"[CONSUMER {name}] Received: {message}")


def main() -> None:
    """Demonstrate the producer-consumer pattern using MessageQueue.

    Spawns three producer threads and two consumer threads. Producers
    each send 5 messages. After all producers finish, a stop event
    signals consumers to drain remaining messages and exit.
    """
    msg_queue = MessageQueue()
    stop_event = threading.Event()
    num_producers = 3
    num_consumers = 2
    messages_per_producer = 5

    producers = []
    consumers = []

    # Start consumers first so they are ready
    for i in range(num_consumers):
        t = threading.Thread(target=consumer, args=(msg_queue, f"C{i}", stop_event), daemon=True)
        t.start()
        consumers.append(t)

    # Start producers
    for i in range(num_producers):
        t = threading.Thread(target=producer, args=(msg_queue, f"P{i}", messages_per_producer))
        t.start()
        producers.append(t)

    # Wait for all producers to finish
    for t in producers:
        t.join()

    print("\n--- All producers finished ---")
    print(f"Queue size after producers: {msg_queue.size()}")

    # Signal consumers to stop once producers are done
    stop_event.set()

    # Wait for all consumers to finish
    for t in consumers:
        t.join()

    print(f"Queue size after consumers: {msg_queue.size()}")
    print("--- Demo complete ---")


if __name__ == "__main__":
    main()
