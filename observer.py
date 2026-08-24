"""Observer Pattern – concise Python implementation."""

from __future__ import annotations


class Observer:
    """Abstract observer."""

    def update(self, message: str) -> None:
        raise NotImplementedError


class Subject:
    """Manages observers and notifies them on state change."""

    def __init__(self) -> None:
        self._observers: list[Observer] = []

    def attach(self, observer: Observer) -> None:
        self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        self._observers.remove(observer)

    def notify(self, message: str) -> None:
        for ob in self._observers:
            ob.update(message)


class ConcreteSubject(Subject):
    """Subject that tracks a state value."""

    def __init__(self) -> None:
        super().__init__()
        self._state: str = ""

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, value: str) -> None:
        self._state = value
        self.notify(value)


class ConcreteObserver(Observer):
    """Observer that prints received messages."""

    def __init__(self, name: str) -> None:
        self._name = name

    def update(self, message: str) -> None:
        print(f"[{self._name}] received: {message}")


def main() -> None:
    subject = ConcreteSubject()

    alice = ConcreteObserver("Alice")
    bob = ConcreteObserver("Bob")

    subject.attach(alice)
    subject.attach(bob)

    subject.state = "hello"   # both notified
    subject.detach(bob)
    subject.state = "world"   # only alice notified


if __name__ == "__main__":
    main()
