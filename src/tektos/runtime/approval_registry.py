"""Tektos-Ultima runtime — pending-approval registry.

The runtime SDK calls ``on_tool_approval(tool_id, tool_name)`` when a
tool needs human authorization. That callback blocks on an
``asyncio.Event`` until the human (WebSocket UI or Telegram bot) sends
back an approve/reject decision. Historically each transport carried its
own local event and dict, which meant the transport handler had no way
to resolve pending approvals that lived inside another coroutine's
closure. See the 2026-09-08 stub audit, P8 and P9.

This module centralises the bookkeeping so both transports can drive
the same approval waiter.

Design notes
------------
- One registry instance per session (keyed inside ``ApprovalRegistry``).
- Each ``PendingApproval`` carries its own ``asyncio.Event`` so waiters
  scale independently; resolving one does not wake unrelated approvals.
- Resolution is idempotent: a second ``approve``/``reject`` for the same
  ``tool_id`` is a no-op that returns ``False`` so callers can detect it
  and respond with a helpful error to the user.
- ``wait_for_decision`` supports an optional timeout and returns
  ``False`` on timeout, matching the historical WebSocket handler
  behaviour (a missing decision is treated as a rejection).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingApproval:
    """One in-flight approval request for a specific tool call."""

    tool_id: str
    tool_name: str
    session_id: str
    approved: bool = False
    resolved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    event: asyncio.Event = field(default_factory=asyncio.Event)

    def resolve(self, approved: bool) -> bool:
        """Set the decision and wake any waiter. Returns True on first resolve."""
        if self.resolved:
            return False
        self.approved = approved
        self.resolved = True
        self.event.set()
        return True


class ApprovalRegistry:
    """Session-scoped registry of pending tool approvals.

    Usage
    -----
    >>> registry = ApprovalRegistry()
    >>> pending = registry.register("session-1", "tool-42", "shell")
    >>> # from the SDK approval callback:
    >>> approved = await registry.wait_for_decision(
    ...     "session-1", "tool-42", timeout=30.0
    ... )
    >>> # from the WebSocket / Telegram approve handler:
    >>> registry.approve("session-1", "tool-42")   # returns True
    """

    def __init__(self) -> None:
        # session_id -> tool_id -> PendingApproval
        self._pending: dict[str, dict[str, PendingApproval]] = {}
        self._lock = asyncio.Lock()

    def register(
        self,
        session_id: str,
        tool_id: str,
        tool_name: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> PendingApproval:
        """Register a new pending approval and return its handle."""
        pending = PendingApproval(
            tool_id=tool_id,
            tool_name=tool_name,
            session_id=session_id,
            metadata=metadata or {},
        )
        self._pending.setdefault(session_id, {})[tool_id] = pending
        return pending

    def get(self, session_id: str, tool_id: str) -> PendingApproval | None:
        """Look up an existing pending approval, or None if not registered."""
        return self._pending.get(session_id, {}).get(tool_id)

    def list_pending(self, session_id: str) -> list[PendingApproval]:
        """Return all still-unresolved approvals for a session."""
        return [p for p in self._pending.get(session_id, {}).values() if not p.resolved]

    def approve(self, session_id: str, tool_id: str) -> bool:
        """Approve a pending tool call. Returns True if it was still pending."""
        pending = self.get(session_id, tool_id)
        if pending is None:
            return False
        return pending.resolve(True)

    def reject(self, session_id: str, tool_id: str) -> bool:
        """Reject a pending tool call. Returns True if it was still pending."""
        pending = self.get(session_id, tool_id)
        if pending is None:
            return False
        return pending.resolve(False)

    async def wait_for_decision(
        self,
        session_id: str,
        tool_id: str,
        *,
        timeout: float | None = None,
    ) -> bool:
        """Wait until the given approval is resolved or the timeout fires.

        Returns True if approved. Returns False if rejected, if the timeout
        expires, or if no such approval was registered.
        """
        pending = self.get(session_id, tool_id)
        if pending is None:
            return False
        try:
            if timeout is None:
                await pending.event.wait()
            else:
                await asyncio.wait_for(pending.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            # Treat timeout as rejection; leave the entry so a late
            # approve/reject is detected as a no-op rather than silently
            # succeeding after the SDK moved on.
            pending.resolve(False)
            return False
        return pending.approved

    def discard(self, session_id: str, tool_id: str) -> None:
        """Forget a resolved approval to keep the registry bounded."""
        session_map = self._pending.get(session_id)
        if session_map is None:
            return
        session_map.pop(tool_id, None)
        if not session_map:
            self._pending.pop(session_id, None)

    def clear_session(self, session_id: str) -> None:
        """Drop all pending approvals for a session (e.g. on WS disconnect)."""
        for pending in list(self._pending.get(session_id, {}).values()):
            # Wake any lingering waiter so their coroutine can exit.
            pending.resolve(False)
        self._pending.pop(session_id, None)


# Process-wide default registry. Transport handlers reach for this
# unless explicitly wired to a different one (tests inject their own).
_DEFAULT_REGISTRY: ApprovalRegistry | None = None


def get_approval_registry() -> ApprovalRegistry:
    """Return (and lazily create) the process-wide approval registry."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = ApprovalRegistry()
    return _DEFAULT_REGISTRY


def reset_approval_registry() -> None:
    """Test helper: clear the process-wide registry."""
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None
