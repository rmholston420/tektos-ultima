/**
 * Tektos WebSocket wire protocol.
 *
 * The backend emits 15 event types envelope-wrapped, plus JSON-RPC 2.0
 * notifications from the gateway proxy. See docs/design/frontend-redesign-
 * plan-2026-09-08.md §5 for the additive fields the frontend2 shell
 * renders opportunistically when present.
 *
 * All new fields are optional. Envelopes lacking them behave identically
 * to the legacy protocol, so backend emitters can be added incrementally.
 */

export const EVENT_TYPES = [
  "session.created",
  "session.ready",
  "session.updated",
  "assistant.delta",
  "assistant.completed",
  "tool.started",
  "tool.delta",
  "tool.completed",
  "tool.permission.required",
  "system.message",
  "session.interrupted",
  "session.failed",
  "self_improvement.tick",
  "resource.warning",
  "model_switched",
  // Additive events (frontend renders placeholders; backend emitters follow-up).
  "plan.proposed",
  "plan.approved",
  "artifact.created",
  "artifact.updated",
] as const;

export type EventType = (typeof EVENT_TYPES)[number];

export interface WSEnvelope<P = Record<string, unknown>> {
  session_id: string;
  event_type: string;
  payload: P;
  seq?: number;
  protocol_version: string;
  timestamp?: string;
  /** Additive: correlates multi-step tool runs to the assistant turn that spawned them. */
  correlation_id?: string;
  /** Additive: parent seq inside the same session for tree reconstruction. */
  parent_seq?: number;
  /** Additive: origin of the event ("user" | "assistant" | "tool" | "system"). */
  origin?: "user" | "assistant" | "tool" | "system";
}

export type ConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting";

export interface ConnectionStateChange {
  state: ConnectionState;
  error?: string | null;
}

// ---- Event payload shapes (partial — extended in later phases) ---------

export interface SessionReadyPayload {
  session_id: string;
  model?: string;
  cwd?: string;
}

export interface AssistantDeltaPayload {
  message_id: string;
  delta: string;
  reasoning?: string;
}

export interface AssistantCompletedPayload {
  message_id: string;
  text: string;
  reasoning?: string;
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
}

export interface ToolStartedPayload {
  tool_call_id: string;
  tool_name: string;
  arguments?: Record<string, unknown>;
  correlation_id?: string;
}

export interface ToolDeltaPayload {
  tool_call_id: string;
  delta: string | Record<string, unknown>;
}

export interface ToolCompletedPayload {
  tool_call_id: string;
  tool_name: string;
  result?: unknown;
  error?: string;
  duration_ms?: number;
}

export interface ToolPermissionRequiredPayload {
  request_id: string;
  tool_name: string;
  reason?: string;
  arguments?: Record<string, unknown>;
}

export interface SystemMessagePayload {
  level: "info" | "warn" | "error";
  message: string;
}

export interface ResourceWarningPayload {
  kind: "memory" | "vram" | "disk" | "cpu";
  used_bytes?: number;
  total_bytes?: number;
  message: string;
}

export interface ModelSwitchedPayload {
  from_model?: string;
  to_model: string;
  reason?: string;
}

export interface SelfImprovementTickPayload {
  epoch: number;
  metrics?: Record<string, number>;
  note?: string;
}

// ---- Additive event payloads (frontend renders now, backend to follow) ---

export interface PlanProposedPayload {
  plan_id: string;
  steps: Array<{ id: string; text: string; requires_approval?: boolean }>;
}

export interface PlanApprovedPayload {
  plan_id: string;
  approved_by?: string;
}

export interface ArtifactCreatedPayload {
  artifact_id: string;
  kind: "file" | "url" | "diff" | "note";
  title: string;
  path?: string;
  url?: string;
  content_type?: string;
  bytes?: number;
}

export interface ArtifactUpdatedPayload {
  artifact_id: string;
  patch?: Partial<ArtifactCreatedPayload>;
  version?: number;
}
