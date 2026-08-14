"""
Tektos-Ultima v1 — Protocol Envelope Tests

Tests WSEnvelope serialization/deserialization, event builders,
EventType enum, and protocol version compliance.
"""

import json
from datetime import datetime, timezone
from tektos.protocol.envelope import (
    PROTOCOL_VERSION,
    WSEnvelope,
    EventType,
    session_ready,
    session_interrupted,
    system_message,
    assistant_delta,
    assistant_completed,
    tool_started,
    tool_delta,
    tool_completed,
    session_created,
    session_updated,
    session_failed,
    tool_permission_required,
    self_improvement_tick,
    resource_warning,
    loop_safety_warning,
)


class TestWSEnvelope:
    def test_defaults(self):
        env = WSEnvelope(
            session_id="test-123",
            event_type="system.message",
            payload={"text": "hello"},
            protocol_version="1.0.0",
        )
        assert env.session_id == "test-123"
        assert env.event_type == "system.message"
        assert env.payload == {"text": "hello"}
        assert env.seq == 0
        assert env.protocol_version == "1.0.0"
        assert env.timestamp  # auto-generated

    def test_serializes_to_json(self):
        env = WSEnvelope(
            session_id="s1",
            event_type="system.message",
            payload={"text": "hi"},
            seq=5,
            protocol_version="1.0.0",
        )
        data = json.loads(env.to_json())
        assert data["session_id"] == "s1"
        assert data["event_type"] == "system.message"
        assert data["payload"]["text"] == "hi"
        assert data["seq"] == 5
        assert data["protocol_version"] == "1.0.0"
        assert "timestamp" in data

    def test_serializes_unicode_payload(self):
        env = WSEnvelope(
            session_id="s1",
            event_type="assistant.delta",
            payload={"text": "こんにちは 🌟"},
            protocol_version=PROTOCOL_VERSION,
        )
        data = json.loads(env.to_json())
        assert data["payload"]["text"] == "こんにちは 🌟"

    def test_deserializes_with_type_key(self):
        raw = json.dumps({
            "session_id": "sess-42",
            "type": "prompt",
            "payload": {"prompt": "write a function"},
        })
        env = WSEnvelope.from_json(raw)
        assert env.session_id == "sess-42"
        assert env.event_type == "prompt"

    def test_deserializes_with_event_type_key(self):
        raw = json.dumps({
            "session_id": "sess-42",
            "event_type": "system.message",
            "payload": {"text": "hello"},
        })
        env = WSEnvelope.from_json(raw)
        assert env.session_id == "sess-42"
        assert env.event_type == "system.message"

    def test_deserializes_with_default_version(self):
        raw = json.dumps({
            "session_id": "s1",
            "event_type": "system.message",
            "payload": {},
        })
        env = WSEnvelope.from_json(raw)
        assert env.protocol_version == PROTOCOL_VERSION

    def test_deserializes_with_custom_version(self):
        raw = json.dumps({
            "session_id": "s1",
            "event_type": "system.message",
            "payload": {},
            "protocol_version": "0.9.0",
        })
        env = WSEnvelope.from_json(raw)
        assert env.protocol_version == "0.9.0"

    def test_deserializes_preserves_seq(self):
        raw = json.dumps({
            "session_id": "s1",
            "event_type": "system.message",
            "payload": {},
            "seq": 42,
        })
        env = WSEnvelope.from_json(raw)
        assert env.seq == 42

    def test_timestamp_auto_generated(self):
        before = datetime.now(timezone.utc)
        env = WSEnvelope(
            session_id="s1", event_type="system.message", payload={}
        )
        after = datetime.now(timezone.utc)
        ts = datetime.fromisoformat(env.timestamp)
        assert before <= ts <= after

    def test_timestamp_custom(self):
        custom_ts = "2025-01-01T00:00:00+00:00"
        env = WSEnvelope(
            session_id="s1",
            event_type="system.message",
            payload={},
            timestamp=custom_ts,
        )
        assert env.timestamp == custom_ts

    def test_serializes_no_seq(self):
        env = WSEnvelope(
            session_id="s1",
            event_type="system.message",
            payload={},
        )
        data = json.loads(env.to_json())
        assert data["seq"] == 0


class TestEventType:
    def test_session_created_value(self):
        assert EventType.SESSION_CREATED == "session.created"

    def test_session_ready_value(self):
        assert EventType.SESSION_READY == "session.ready"

    def test_assistant_delta_value(self):
        assert EventType.ASSISTANT_DELTA == "assistant.delta"

    def test_tool_started_value(self):
        assert EventType.TOOL_STARTED == "tool.started"

    def test_tool_completed_value(self):
        assert EventType.TOOL_COMPLETED == "tool.completed"

    def test_system_message_value(self):
        assert EventType.SYSTEM_MESSAGE == "system.message"

    def test_session_interrupted_value(self):
        assert EventType.SESSION_INTERRUPTED == "session.interrupted"

    def test_self_improvement_tick_value(self):
        assert EventType.SELF_IMPROVEMENT_TICK == "self_improvement.tick"

    def test_loop_safety_warning_value(self):
        assert EventType.LOOP_SAFETY_WARNING == "loop_safety.warning"

    def test_is_string(self):
        assert isinstance(EventType.SESSION_CREATED, str)


class TestSessionReady:
    def test_returns_valid_envelope(self):
        env = session_ready("sess-123", since_seq=0)
        assert isinstance(env, WSEnvelope)
        assert env.session_id == "sess-123"
        assert env.event_type == EventType.SESSION_READY
        assert env.payload["since_seq"] == 0

    def test_default_since_seq(self):
        env = session_ready("sess-123")
        assert env.payload["since_seq"] == 0

    def test_serializable(self):
        env = session_ready("sess-456", since_seq=10)
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.SESSION_READY
        assert data["payload"]["since_seq"] == 10


class TestSessionCreated:
    def test_returns_valid_envelope(self):
        env = session_created("sess-123")
        assert isinstance(env, WSEnvelope)
        assert env.session_id == "sess-123"
        assert env.event_type == EventType.SESSION_CREATED
        assert env.payload["subtype"] == "session.created"
        assert "message" in env.payload

    def test_serializable(self):
        env = session_created("s1")
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.SESSION_CREATED


class TestSessionUpdated:
    def test_returns_valid_envelope(self):
        env = session_updated("sess-123", title="new title", tag="dev")
        assert isinstance(env, WSEnvelope)
        assert env.session_id == "sess-123"
        assert env.event_type == EventType.SESSION_UPDATED
        assert env.payload["changes"]["title"] == "new title"
        assert env.payload["changes"]["tag"] == "dev"

    def test_serializable(self):
        env = session_updated("s1", model="qwen3.6")
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.SESSION_UPDATED
        assert data["payload"]["changes"]["model"] == "qwen3.6"


class TestSessionInterrupted:
    def test_returns_valid_envelope(self):
        env = session_interrupted("sess-789")
        assert isinstance(env, WSEnvelope)
        assert env.session_id == "sess-789"
        assert env.event_type == EventType.SESSION_INTERRUPTED
        assert "message" in env.payload

    def test_serializable(self):
        env = session_interrupted("s1")
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.SESSION_INTERRUPTED


class TestSessionFailed:
    def test_returns_valid_envelope(self):
        env = session_failed("sess-123", "timeout")
        assert isinstance(env, WSEnvelope)
        assert env.session_id == "sess-123"
        assert env.event_type == EventType.SESSION_FAILED
        assert env.payload["error"] == "timeout"
        assert "message" in env.payload

    def test_serializable(self):
        env = session_failed("s1", "OOM")
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.SESSION_FAILED
        assert data["payload"]["error"] == "OOM"


class TestSystemMessage:
    def test_returns_valid_envelope(self):
        env = system_message("sess-1", "info text", "info")
        assert isinstance(env, WSEnvelope)
        assert env.session_id == "sess-1"
        assert env.event_type == EventType.SYSTEM_MESSAGE
        assert env.payload["message"] == "info text"
        assert env.payload["level"] == "info"

    def test_default_level(self):
        env = system_message("sess-1", "msg")
        assert env.payload["level"] == "info"

    def test_warning_level(self):
        env = system_message("sess-1", "warn", "warning")
        assert env.payload["level"] == "warning"

    def test_error_level(self):
        env = system_message("sess-1", "err", "error")
        assert env.payload["level"] == "error"

    def test_serializable(self):
        env = system_message("s1", "test msg", "info")
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.SYSTEM_MESSAGE
        assert data["payload"]["message"] == "test msg"


class TestAssistantDelta:
    def test_returns_valid_envelope(self):
        env = assistant_delta("sess-1", "partial text")
        assert env.session_id == "sess-1"
        assert env.event_type == EventType.ASSISTANT_DELTA
        assert env.payload["text"] == "partial text"

    def test_serializable(self):
        env = assistant_delta("s1", "delta")
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.ASSISTANT_DELTA


class TestAssistantCompleted:
    def test_returns_valid_envelope(self):
        env = assistant_completed("sess-1", "end_turn")
        assert env.session_id == "sess-1"
        assert env.event_type == EventType.ASSISTANT_COMPLETED
        assert env.payload["stop_reason"] == "end_turn"

    def test_default_stop_reason(self):
        env = assistant_completed("sess-1")
        assert env.payload["stop_reason"] == "end_turn"

    def test_serializable(self):
        env = assistant_completed("s1", "max_tokens")
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.ASSISTANT_COMPLETED
        assert data["payload"]["stop_reason"] == "max_tokens"


class TestToolStarted:
    def test_returns_valid_envelope(self):
        env = tool_started("sess-1", "tool-abc", "run_shell", {"cmd": "ls"})
        assert env.session_id == "sess-1"
        assert env.event_type == EventType.TOOL_STARTED
        assert env.payload["tool_id"] == "tool-abc"
        assert env.payload["tool_name"] == "run_shell"
        assert env.payload["tool_input"] == {"cmd": "ls"}

    def test_default_input(self):
        env = tool_started("sess-1", "tool-abc", "run_shell")
        assert env.payload["tool_input"] == {}

    def test_serializable(self):
        env = tool_started("s1", "t1", "edit_file", {"path": "x.py"})
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.TOOL_STARTED
        assert data["payload"]["tool_name"] == "edit_file"


class TestToolDelta:
    def test_returns_valid_envelope(self):
        env = tool_delta("sess-1", "tool-abc", "output chunk")
        assert env.session_id == "sess-1"
        assert env.event_type == EventType.TOOL_DELTA
        assert env.payload["tool_id"] == "tool-abc"
        assert env.payload["delta"] == "output chunk"

    def test_serializable(self):
        env = tool_delta("s1", "t1", "data")
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.TOOL_DELTA
        assert data["payload"]["delta"] == "data"


class TestToolCompleted:
    def test_returns_valid_envelope(self):
        env = tool_completed("sess-1", "tool-abc", "success", "exit 0")
        assert env.session_id == "sess-1"
        assert env.event_type == EventType.TOOL_COMPLETED
        assert env.payload["tool_id"] == "tool-abc"
        assert env.payload["status"] == "success"
        assert env.payload["output"] == "exit 0"

    def test_default_status(self):
        env = tool_completed("sess-1", "tool-abc")
        assert env.payload["status"] == "success"
        assert env.payload["output"] == ""

    def test_serializable(self):
        env = tool_completed("s1", "t1", "failed", "error msg")
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.TOOL_COMPLETED
        assert data["payload"]["status"] == "failed"


class TestToolPermissionRequired:
    def test_returns_valid_envelope(self):
        env = tool_permission_required("sess-1", "tool-abc", "run_shell", {"cmd": "rm -rf /"})
        assert env.session_id == "sess-1"
        assert env.event_type == EventType.TOOL_PERMISSION_REQUIRED
        assert env.payload["tool_id"] == "tool-abc"
        assert env.payload["tool_name"] == "run_shell"
        assert env.payload["tool_input"] == {"cmd": "rm -rf /"}

    def test_serializable(self):
        env = tool_permission_required("s1", "t1", "edit_file", {"path": "x.py"})
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.TOOL_PERMISSION_REQUIRED
        assert data["payload"]["tool_name"] == "edit_file"


class TestSelfImprovementTick:
    def test_returns_valid_envelope(self):
        env = self_improvement_tick("sess-1", "test_rate", 0.95, {"tasks": 10})
        assert env.session_id == "sess-1"
        assert env.event_type == EventType.SELF_IMPROVEMENT_TICK
        assert env.payload["metric_type"] == "test_rate"
        assert env.payload["value"] == 0.95
        assert env.payload["details"]["tasks"] == 10

    def test_default_details(self):
        env = self_improvement_tick("sess-1", "rate", 0.5)
        assert env.payload["details"] == {}

    def test_serializable(self):
        env = self_improvement_tick("s1", "speed", 1.2)
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.SELF_IMPROVEMENT_TICK
        assert data["payload"]["value"] == 1.2


class TestResourceWarning:
    def test_returns_valid_envelope(self):
        env = resource_warning("sess-1", "gpu", 95.0, 90.0, "GPU thermal limit")
        assert env.session_id == "sess-1"
        assert env.event_type == EventType.RESOURCE_WARNING
        assert env.payload["resource"] == "gpu"
        assert env.payload["current"] == 95.0
        assert env.payload["threshold"] == 90.0
        assert env.payload["message"] == "GPU thermal limit"

    def test_serializable(self):
        env = resource_warning("s1", "memory", 50.0, 80.0, "Low RAM")
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.RESOURCE_WARNING
        assert data["payload"]["resource"] == "memory"
        assert data["payload"]["current"] == 50.0


class TestLoopSafetyWarning:
    def test_returns_valid_envelope(self):
        env = loop_safety_warning("sess-1", "max_iterations_exceeded", {"step": 50})
        assert env.session_id == "sess-1"
        assert env.event_type == EventType.LOOP_SAFETY_WARNING
        assert env.payload["state"] == "max_iterations_exceeded"
        assert env.payload["details"]["step"] == 50

    def test_default_details(self):
        env = loop_safety_warning("sess-1", "idle_timeout")
        assert env.payload["details"] == {}

    def test_serializable(self):
        env = loop_safety_warning("s1", "tool_chain_too_long")
        data = json.loads(env.to_json())
        assert data["event_type"] == EventType.LOOP_SAFETY_WARNING
        assert data["payload"]["state"] == "tool_chain_too_long"


class TestProtocolVersion:
    def test_version_format(self):
        assert PROTOCOL_VERSION == "1.0.0"

    def test_version_is_string(self):
        assert isinstance(PROTOCOL_VERSION, str)

    def test_version_parts(self):
        parts = PROTOCOL_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)