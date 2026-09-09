"""Tektos-Ultima-v1 — versioned WebSocket protocol envelope.

Adapted from PlexClaw's normalized envelope pattern. Frontend binds to
this contract, never to raw SDK object shapes.

Every event uses a versioned envelope:
{
  "type": "assistant.delta",
  "session_id": "uuid",
  "seq": 12,
  "payload": { "text": "hello" },
  "protocol_version": "1.0.0"
}

Required event types:
  - session.created / session.ready / session.updated
  - assistant.delta / assistant.completed
  - tool.started / tool.delta / tool.completed / tool.permission.required
  - system.message
  - session.interrupted / session.failed
  - self_improvement.tick / resource.warning
"""

from __future__ import annotations

import json as _json
import logging as _log
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

log = _log.getLogger("tektos.protocol")


# ---------------------------------------------------------------------------
# Protocol version
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class EventType(str, Enum):
    SESSION_CREATED = "session.created"
    SESSION_READY = "session.ready"
    SESSION_UPDATED = "session.updated"

    ASSISTANT_DELTA = "assistant.delta"
    ASSISTANT_REASONING = "assistant.reasoning"
    ASSISTANT_COMPLETED = "assistant.completed"

    TOOL_STARTED = "tool.started"
    TOOL_DELTA = "tool.delta"
    TOOL_COMPLETED = "tool.completed"
    TOOL_PERMISSION_REQUIRED = "tool.permission.required"

    SYSTEM_MESSAGE = "system.message"

    SESSION_INTERRUPTED = "session.interrupted"
    SESSION_FAILED = "session.failed"

    SELF_IMPROVEMENT_TICK = "self_improvement.tick"
    RESOURCE_WARNING = "resource.warning"
    LOOP_SAFETY_WARNING = "loop_safety.warning"

    PLAN_PROPOSED = "plan.proposed"
    PLAN_APPROVED = "plan.approved"

    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_UPDATED = "artifact.updated"


# ---------------------------------------------------------------------------
# WSEnvelope — the canonical WebSocket message shape
# ---------------------------------------------------------------------------


@dataclass
class WSEnvelope:
    """Normalized WebSocket envelope.

    seq is assigned by the event store's push() function, NOT passed as
    a parameter, to prevent duplicate sequence numbers (PlexClaw bug #6).
    """

    session_id: str
    event_type: str
    payload: dict[str, Any]
    protocol_version: str = PROTOCOL_VERSION
    seq: int = 0
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        return _json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> WSEnvelope:
        d = _json.loads(raw)
        return cls(
            session_id=d["session_id"],
            event_type=d.get("event_type", d.get("type", "")),
            payload=d["payload"],
            protocol_version=d.get("protocol_version", PROTOCOL_VERSION),
            seq=d.get("seq", 0),
            timestamp=d.get("timestamp", ""),
        )


# ---------------------------------------------------------------------------
# Envelope helpers — standardized construction (no dual-key pattern)
# ---------------------------------------------------------------------------


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_created(
    session_id: str,
    *,
    model: str | None = None,
    cwd: str | None = None,
) -> WSEnvelope:
    """Session initialized. Store-only, visible on replay.

    ``model`` and ``cwd`` are included so the frontend header can render
    the active model and working directory on first receipt, without
    needing a follow-up REST GET.
    """
    payload: dict[str, Any] = {
        "subtype": "session.created",
        "message": "Session created",
        "since_seq": 0,
    }
    if model is not None:
        payload["model"] = model
    if cwd is not None:
        payload["cwd"] = cwd
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.SESSION_CREATED,
        payload=payload,
    )


def session_ready(
    session_id: str,
    since_seq: int = 0,
    *,
    model: str | None = None,
    cwd: str | None = None,
) -> WSEnvelope:
    """Connected to LLM, ready for prompts.

    ``model`` and ``cwd`` are included so the frontend header can render
    the active model and working directory on first receipt.
    """
    payload: dict[str, Any] = {
        "message": "Session ready",
        "since_seq": since_seq,
    }
    if model is not None:
        payload["model"] = model
    if cwd is not None:
        payload["cwd"] = cwd
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.SESSION_READY,
        payload=payload,
    )


def session_updated(session_id: str, **fields: Any) -> WSEnvelope:
    """Metadata changed (rename, tag, model switch)."""
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.SESSION_UPDATED,
        payload={"changes": fields},
    )


def assistant_delta(session_id: str, text: str) -> WSEnvelope:
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.ASSISTANT_DELTA,
        payload={"text": text},
    )


def assistant_reasoning(session_id: str, text: str) -> WSEnvelope:
    """Model's private chain-of-thought.

    Kept distinct from ``assistant_delta`` so the frontend can render it in
    a reasoning panel and, more importantly, so history replay does not
    round-trip the model's own thoughts back into its context on the next
    turn.
    """
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.ASSISTANT_REASONING,
        payload={"text": text},
    )


def assistant_completed(session_id: str, stop_reason: str = "end_turn") -> WSEnvelope:
    """Emitted ONLY when stop_reason == 'end_turn' or saw_text is True.
    NOT from message_delta (PlexClaw bug #2 fix)."""
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.ASSISTANT_COMPLETED,
        payload={"stop_reason": stop_reason},
    )


def tool_started(
    session_id: str,
    tool_id: str,
    tool_name: str,
    tool_input: dict[str, Any] | None = None,
) -> WSEnvelope:
    """Tool use beginning. Includes tool_input in payload."""
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.TOOL_STARTED,
        payload={
            "tool_id": tool_id,
            "tool_name": tool_name,
            "tool_input": tool_input or {},
        },
    )


def tool_delta(
    session_id: str,
    tool_id: str,
    delta: str,
) -> WSEnvelope:
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.TOOL_DELTA,
        payload={"tool_id": tool_id, "delta": delta},
    )


def tool_completed(
    session_id: str,
    tool_id: str,
    status: str = "success",
    output: str = "",
) -> WSEnvelope:
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.TOOL_COMPLETED,
        payload={
            "tool_id": tool_id,
            "status": status,
            "output": output,
        },
    )


def tool_permission_required(
    session_id: str,
    tool_id: str,
    tool_name: str,
    tool_input: dict[str, Any],
) -> WSEnvelope:
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.TOOL_PERMISSION_REQUIRED,
        payload={
            "tool_id": tool_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
        },
    )


def system_message(
    session_id: str,
    message: str,
    level: str = "info",
) -> WSEnvelope:
    """System notification. Uses single key 'message' (no dual-key)."""
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.SYSTEM_MESSAGE,
        payload={
            "message": message,
            "level": level,
        },
    )


def session_interrupted(session_id: str) -> WSEnvelope:
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.SESSION_INTERRUPTED,
        payload={"message": "Session interrupted"},
    )


def session_failed(session_id: str, error: str) -> WSEnvelope:
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.SESSION_FAILED,
        payload={"error": error, "message": "Session failed"},
    )


def self_improvement_tick(
    session_id: str,
    metric_type: str,
    value: float,
    details: dict[str, Any] | None = None,
) -> WSEnvelope:
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.SELF_IMPROVEMENT_TICK,
        payload={
            "metric_type": metric_type,
            "value": value,
            "details": details or {},
        },
    )


def resource_warning(
    session_id: str,
    resource: str,
    current: float,
    threshold: float,
    message: str,
) -> WSEnvelope:
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.RESOURCE_WARNING,
        payload={
            "resource": resource,
            "current": current,
            "threshold": threshold,
            "message": message,
        },
    )


def loop_safety_warning(
    session_id: str,
    state: str,
    details: dict[str, Any] | None = None,
) -> WSEnvelope:
    """Emitted when loop safety thresholds are triggered."""
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.LOOP_SAFETY_WARNING,
        payload={
            "state": state,
            "details": details or {},
        },
    )


def plan_proposed(
    session_id: str,
    plan_id: str,
    steps: list[dict[str, Any]],
) -> WSEnvelope:
    """Planner has produced a plan; frontend renders it and awaits approval.

    Each step is ``{"id": str, "text": str, "requires_approval"?: bool}``.
    """
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.PLAN_PROPOSED,
        payload={
            "plan_id": plan_id,
            "steps": steps,
        },
    )


def plan_approved(
    session_id: str,
    plan_id: str,
    approved_by: str | None = None,
) -> WSEnvelope:
    """Plan has been approved (by the user or an auto-approver)."""
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.PLAN_APPROVED,
        payload={
            "plan_id": plan_id,
            "approved_by": approved_by,
        },
    )


def artifact_created(
    session_id: str,
    artifact_id: str,
    kind: str,
    title: str,
    *,
    path: str | None = None,
    url: str | None = None,
    content_type: str | None = None,
    bytes_len: int | None = None,
) -> WSEnvelope:
    """A new artifact (file, url, diff, or note) has been produced."""
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.ARTIFACT_CREATED,
        payload={
            "artifact_id": artifact_id,
            "kind": kind,
            "title": title,
            "path": path,
            "url": url,
            "content_type": content_type,
            "bytes": bytes_len,
        },
    )


def artifact_updated(
    session_id: str,
    artifact_id: str,
    *,
    patch: dict[str, Any] | None = None,
    version: int | None = None,
) -> WSEnvelope:
    """An existing artifact has been revised. ``patch`` is a partial update."""
    return WSEnvelope(
        session_id=session_id,
        event_type=EventType.ARTIFACT_UPDATED,
        payload={
            "artifact_id": artifact_id,
            "patch": patch or {},
            "version": version,
        },
    )
