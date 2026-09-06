"""Event Sourcing System in Python."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ── Event ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Event:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    aggregate_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "timestamp", self.timestamp or datetime.now(timezone.utc))


# ── Aggregate Base ───────────────────────────────────────────────────────────

class AggregateRoot:
    """Base class for all aggregates. Tracks version and applies events."""

    def __init__(self, aggregate_id: str | None = None) -> None:
        self.aggregate_id: str = aggregate_id or str(uuid.uuid4())
        self.version: int = 0
        self._uncommitted: list[Event] = []

    def apply_event(self, event: Event) -> None:
        """Apply a single event to state. Override in subclasses."""
        raise NotImplementedError

    def snapshot(self) -> dict[str, Any]:
        """Return current state as a serialisable dict."""
        raise NotImplementedError

    def load_snapshot(self, data: dict[str, Any], version: int) -> None:
        """Restore state from a snapshot."""
        raise NotImplementedError

    def append_event(self, event_type: str, data: dict[str, Any] | None = None) -> Event:
        event = Event(
            type=event_type,
            aggregate_id=self.aggregate_id,
            data=data or {},
        )
        self._uncommitted.append(event)
        return event

    def commit(self) -> list[Event]:
        events = self._uncommitted[:]
        self._uncommitted.clear()
        return events


# ── Event Store ──────────────────────────────────────────────────────────────

class EventStore:
    """In-memory event store with snapshot support."""

    def __init__(self) -> None:
        self._events: dict[str, list[Event]] = defaultdict(list)
        self._snapshots: dict[str, tuple[int, dict]] = {}

    def append(self, events: list[Event], expected_version: int) -> int:
        """Append events with optimistic concurrency control.

        Raises RuntimeError on version mismatch.
        """
        agg_id = events[0].aggregate_id
        current_version = len(self._events.get(agg_id, []))
        if current_version != expected_version:
            raise RuntimeError(
                f"Concurrency conflict: expected version {expected_version}, "
                f"but current version is {current_version}"
            )
        for ev in events:
            self._events[agg_id].append(ev)
        return expected_version + len(events)

    def replay_events(self, aggregate_id: str) -> list[Event]:
        return list(self._events.get(aggregate_id, []))

    def get_snapshot(self, aggregate_id: str) -> tuple[int, dict[str, Any]] | None:
        snap = self._snapshots.get(aggregate_id)
        if snap:
            return snap
        return None

    def save_snapshot(self, aggregate_id: str, version: int, state: dict) -> None:
        self._snapshots[aggregate_id] = (version, state)


# ── Projection ───────────────────────────────────────────────────────────────

class Projection:
    """Builds a read-model by subscribing to events."""

    def __init__(self, store: EventStore) -> None:
        self.store = store
        self._handlers: dict[str, callable] = {}
        self.state: dict[str, Any] = {}

    def on(self, event_type: str, handler: callable) -> Projection:
        self._handlers[event_type] = handler
        return self

    def build(self) -> None:
        all_events: list[Event] = []
        for events in self.store._events.values():
            all_events.extend(events)
        all_events.sort(key=lambda e: e.timestamp)
        for ev in all_events:
            if ev.type in self._handlers:
                self._handlers[ev.type](ev)

    def get(self, key: str) -> Any:
        return self.state.get(key)


# ── Command Handler ──────────────────────────────────────────────────────────

class Command:
    """Base class for commands."""


class CommandHandler:
    """Generic command handler: validate → apply → persist."""

    def __init__(self, event_store: EventStore) -> None:
        self.event_store = event_store

    def handle(self, command: Command) -> None:
        self.validate(command)
        aggregate = self.load(command)
        self.apply(command, aggregate)
        self.persist(aggregate)

    def validate(self, command: Command) -> None:
        pass

    def load(self, command: Command) -> AggregateRoot:
        raise NotImplementedError

    def apply(self, command: Command, aggregate: AggregateRoot) -> None:
        raise NotImplementedError

    def persist(self, aggregate: AggregateRoot) -> None:
        events = aggregate.commit()
        if events:
            new_version = self.event_store.append(events, aggregate.version)
            aggregate.version = new_version


# ── Bank Account Domain ──────────────────────────────────────────────────────

@dataclass
class DepositCommand:
    account_id: str
    amount: float


@dataclass
class WithdrawCommand:
    account_id: str
    amount: float


class BankAccount(AggregateRoot):
    def __init__(self, account_id: str | None = None) -> None:
        super().__init__(account_id)
        self._balance: float = 0.0
        self._owner: str = ""

    def apply_event(self, event: Event) -> None:
        match event.type:
            case "AccountCreated":
                self._owner = event.data["owner"]
            case "MoneyDeposited":
                self._balance += event.data["amount"]
            case "MoneyWithdrawn":
                self._balance -= event.data["amount"]

    def snapshot(self) -> dict[str, Any]:
        return {"balance": self._balance, "owner": self._owner}

    def load_snapshot(self, data: dict[str, Any], version: int) -> None:
        self._balance = data["balance"]
        self._owner = data["owner"]
        self.version = version

    def create(self, owner: str) -> None:
        if self.version > 0:
            return
        self.apply_event(self.append_event("AccountCreated", {"owner": owner}))

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        self.apply_event(self.append_event("MoneyDeposited", {"amount": amount}))

    def withdraw(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self._balance:
            raise ValueError("Insufficient funds")
        self.apply_event(self.append_event("MoneyWithdrawn", {"amount": amount}))

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def owner(self) -> str:
        return self._owner


# ── Bank Command Handlers ────────────────────────────────────────────────────

class DepositHandler(CommandHandler):
    def validate(self, cmd: DepositCommand) -> None:
        if cmd.amount <= 0:
            raise ValueError("Deposit must be positive")

    def load(self, cmd: DepositCommand) -> BankAccount:
        account = BankAccount(cmd.account_id)
        snap = self.event_store.get_snapshot(cmd.account_id)
        if snap:
            account.load_snapshot(snap[1], snap[0])
        else:
            events = self.event_store.replay_events(cmd.account_id)
            for ev in events:
                account.apply_event(ev)
            account.version = len(events)
        return account

    def apply(self, cmd: DepositCommand, account: BankAccount) -> None:
        account.deposit(cmd.amount)


class WithdrawHandler(CommandHandler):
    def validate(self, cmd: WithdrawCommand) -> None:
        if cmd.amount <= 0:
            raise ValueError("Withdrawal must be positive")

    def load(self, cmd: WithdrawCommand) -> BankAccount:
        account = BankAccount(cmd.account_id)
        snap = self.event_store.get_snapshot(cmd.account_id)
        if snap:
            account.load_snapshot(snap[1], snap[0])
        else:
            events = self.event_store.replay_events(cmd.account_id)
            for ev in events:
                account.apply_event(ev)
            account.version = len(events)
        return account

    def apply(self, cmd: WithdrawCommand, account: BankAccount) -> None:
        account.withdraw(cmd.amount)


# ── Projection for Read Model ────────────────────────────────────────────────

class AccountBalanceProjection(Projection):
    def build_read_model(self) -> dict[str, float]:
        self.on("MoneyDeposited", lambda e: self._update(e.aggregate_id, e.data["amount"]))
        self.on("MoneyWithdrawn", lambda e: self._update(e.aggregate_id, -e.data["amount"]))
        self.build()
        return self.state

    def _update(self, account_id: str, delta: float) -> None:
        self.state[account_id] = self.state.get(account_id, 0.0) + delta


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    store = EventStore()
    deposit_handler = DepositHandler(store)
    withdraw_handler = WithdrawHandler(store)

    # 1. Create account
    acct = BankAccount("acct-1")
    acct.create("Alice")
    store.append(acct.commit(), 0)
    acct.version = 1

    # 2. Deposit
    deposit_handler.handle(DepositCommand("acct-1", 500.0))
    print(f"Balance after deposit 500:  ${acct.balance:.2f}")

    # 3. Withdraw
    withdraw_handler.handle(WithdrawCommand("acct-1", 150.0))
    print(f"Balance after withdraw 150: ${acct.balance:.2f}")

    # 4. Deposit again
    deposit_handler.handle(DepositCommand("acct-1", 1000.0))
    print(f"Balance after deposit 1000: ${acct.balance:.2f}")

    # 5. Verify via replay
    acct2 = BankAccount("acct-1")
    for ev in store.replay_events("acct-1"):
        acct2.apply_event(ev)
    print(f"Replay balance:              ${acct2.balance:.2f}")
    assert acct2.balance == 1350.0

    # 6. Optimistic concurrency test
    acct3 = BankAccount("acct-1")
    for ev in store.replay_events("acct-1"):
        acct3.apply_event(ev)
    acct3.deposit(10.0)
    try:
        store.append(acct3.commit(), 0)
    except RuntimeError as e:
        print(f"Concurrency error caught: {e}")

    # 7. Projection: build read model
    projection = AccountBalanceProjection(store)
    balances = projection.build_read_model()
    print(f"Projection read model: {balances}")
    assert balances["acct-1"] == 1350.0

    # 8. Snapshot example
    store.save_snapshot("acct-1", acct.version, acct.snapshot())
    snap = store.get_snapshot("acct-1")
    print(f"Snapshot: version={snap[0]}, state={snap[1]}")

    print("\nAll checks passed.")
