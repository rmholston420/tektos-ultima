"use client";

import { atom, map, computed } from "nanostores";
import type {
  ArtifactCreatedPayload,
  PlanProposedPayload,
  ResourceWarningPayload,
  ToolPermissionRequiredPayload,
  WSEnvelope,
} from "@/types/protocol";

// ---- Message / turn model ---------------------------------------------

export interface AssistantMessage {
  id: string;
  role: "user" | "assistant" | "system";
  text: string;
  reasoning?: string;
  created_at: string;
  completed: boolean;
  correlation_id?: string;
  /** Ordered tool_call_ids attached to this assistant turn. */
  tool_call_ids: string[];
  /** Optional usage summary attached at completion. */
  usage?: { prompt?: number; completion?: number; total?: number };
}

export interface ToolCallRecord {
  id: string;
  name: string;
  arguments?: Record<string, unknown>;
  status: "running" | "completed" | "errored";
  delta_chunks: string[];
  result?: unknown;
  error?: string;
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
  correlation_id?: string;
}

export interface Artifact {
  id: string;
  kind: ArtifactCreatedPayload["kind"];
  title: string;
  path?: string;
  url?: string;
  content_type?: string;
  bytes?: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PermissionRequest {
  request_id: string;
  tool_name: string;
  reason?: string;
  arguments?: Record<string, unknown>;
  created_at: string;
}

export interface PlanProposal {
  plan_id: string;
  steps: PlanProposedPayload["steps"];
  approved: boolean;
  created_at: string;
}

// ---- Session identity --------------------------------------------------

export const $sessionId = atom<string>("");
export const $sessionModel = atom<string | null>(null);
export const $sessionCwd = atom<string | null>(null);

// ---- Transcript --------------------------------------------------------

export const $messages = map<Record<string, AssistantMessage>>({});
export const $messageOrder = atom<string[]>([]);

export const $orderedMessages = computed(
  [$messages, $messageOrder],
  (byId, order) => order.map((id) => byId[id]).filter(Boolean),
);

/**
 * True whenever the newest assistant message is still open — the model is
 * actively generating (or the stream stalled after only reasoning). Used by
 * the GeneratingRow status row so the user can see a live "assistant is
 * working…" indicator instead of guessing whether the turn ever ended.
 */
export const $isGenerating = computed(
  [$messages, $messageOrder],
  (byId, order) => {
    for (let i = order.length - 1; i >= 0; i--) {
      const m = byId[order[i]];
      if (!m) continue;
      if (m.role !== "assistant") return false;
      return !m.completed;
    }
    return false;
  },
);

// ---- Tool calls --------------------------------------------------------

export const $toolCalls = map<Record<string, ToolCallRecord>>({});
export const $activeToolIds = atom<string[]>([]);

export const $activeTools = computed(
  [$toolCalls, $activeToolIds],
  (byId, ids) => ids.map((id) => byId[id]).filter(Boolean),
);

// ---- Artifacts ---------------------------------------------------------

export const $artifacts = map<Record<string, Artifact>>({});
export const $artifactOrder = atom<string[]>([]);

// ---- Pending user attention -------------------------------------------

export const $permissionQueue = atom<PermissionRequest[]>([]);
export const $planProposals = map<Record<string, PlanProposal>>({});

// ---- Resource + system notices ----------------------------------------

export const $resourceWarnings = atom<ResourceWarningPayload[]>([]);
export const $systemNotices = atom<
  Array<{ level: "info" | "warn" | "error"; message: string; at: string }>
>([]);

// ---- Reducer -----------------------------------------------------------

/**
 * Apply a single envelope to the session stores.
 *
 * Deterministic and side-effect-free apart from store writes. Unknown
 * event types are ignored (forward-compatible with backend additions).
 */
export function applyEnvelope(env: WSEnvelope): void {
  const now = env.timestamp ?? new Date().toISOString();

  switch (env.event_type) {
    case "session.created":
    case "session.ready": {
      if (env.session_id) $sessionId.set(env.session_id);
      const p = env.payload as { model?: string; cwd?: string };
      if (p.model) $sessionModel.set(p.model);
      if (p.cwd) $sessionCwd.set(p.cwd);
      return;
    }

    case "session.updated": {
      const p = env.payload as { model?: string; cwd?: string };
      if (p.model) $sessionModel.set(p.model);
      if (p.cwd) $sessionCwd.set(p.cwd);
      return;
    }

    case "assistant.delta": {
      const p = env.payload as { message_id: string; delta: string; reasoning?: string };
      const existing = $messages.get()[p.message_id];
      if (existing) {
        $messages.setKey(p.message_id, {
          ...existing,
          text: existing.text + p.delta,
          reasoning:
            (existing.reasoning ?? "") + (p.reasoning ?? ""),
        });
      } else {
        const msg: AssistantMessage = {
          id: p.message_id,
          role: "assistant",
          text: p.delta,
          reasoning: p.reasoning,
          created_at: now,
          completed: false,
          correlation_id: env.correlation_id,
          tool_call_ids: [],
        };
        $messages.setKey(p.message_id, msg);
        $messageOrder.set([...$messageOrder.get(), p.message_id]);
      }
      return;
    }

    case "assistant.completed": {
      const p = env.payload as {
        message_id: string;
        text: string;
        reasoning?: string;
        usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
      };
      const existing = $messages.get()[p.message_id];
      const msg: AssistantMessage = {
        id: p.message_id,
        role: "assistant",
        text: p.text,
        reasoning: p.reasoning,
        created_at: existing?.created_at ?? now,
        completed: true,
        correlation_id: env.correlation_id ?? existing?.correlation_id,
        tool_call_ids: existing?.tool_call_ids ?? [],
        usage: p.usage
          ? {
              prompt: p.usage.prompt_tokens,
              completion: p.usage.completion_tokens,
              total: p.usage.total_tokens,
            }
          : undefined,
      };
      $messages.setKey(p.message_id, msg);
      if (!$messageOrder.get().includes(p.message_id)) {
        $messageOrder.set([...$messageOrder.get(), p.message_id]);
      }
      return;
    }

    case "tool.started": {
      const p = env.payload as {
        tool_call_id: string;
        tool_name: string;
        arguments?: Record<string, unknown>;
      };
      $toolCalls.setKey(p.tool_call_id, {
        id: p.tool_call_id,
        name: p.tool_name,
        arguments: p.arguments,
        status: "running",
        delta_chunks: [],
        started_at: now,
        correlation_id: env.correlation_id,
      });
      $activeToolIds.set([...$activeToolIds.get(), p.tool_call_id]);
      // Attach to current assistant message if correlated
      if (env.correlation_id) {
        const msgs = $messages.get();
        for (const id of Object.keys(msgs)) {
          const m = msgs[id];
          if (m.correlation_id === env.correlation_id && !m.completed) {
            $messages.setKey(id, {
              ...m,
              tool_call_ids: [...m.tool_call_ids, p.tool_call_id],
            });
            break;
          }
        }
      }
      return;
    }

    case "tool.delta": {
      const p = env.payload as {
        tool_call_id: string;
        delta: string | Record<string, unknown>;
      };
      const t = $toolCalls.get()[p.tool_call_id];
      if (!t) return;
      const chunk = typeof p.delta === "string" ? p.delta : JSON.stringify(p.delta);
      $toolCalls.setKey(p.tool_call_id, {
        ...t,
        delta_chunks: [...t.delta_chunks, chunk],
      });
      return;
    }

    case "tool.completed": {
      const p = env.payload as {
        tool_call_id: string;
        tool_name: string;
        result?: unknown;
        error?: string;
        duration_ms?: number;
      };
      const t = $toolCalls.get()[p.tool_call_id];
      if (t) {
        $toolCalls.setKey(p.tool_call_id, {
          ...t,
          status: p.error ? "errored" : "completed",
          result: p.result,
          error: p.error,
          duration_ms: p.duration_ms,
          completed_at: now,
        });
      }
      $activeToolIds.set(
        $activeToolIds.get().filter((id) => id !== p.tool_call_id),
      );
      return;
    }

    case "tool.permission.required": {
      const p = env.payload as unknown as ToolPermissionRequiredPayload;
      $permissionQueue.set([
        ...$permissionQueue.get(),
        { ...p, created_at: now },
      ]);
      return;
    }

    case "system.message": {
      const p = env.payload as { level: "info" | "warn" | "error"; message: string };
      $systemNotices.set([
        ...$systemNotices.get(),
        { level: p.level, message: p.message, at: now },
      ]);
      return;
    }

    case "session.interrupted":
    case "session.failed": {
      const p = env.payload as { reason?: string; message?: string };
      $systemNotices.set([
        ...$systemNotices.get(),
        {
          level: env.event_type === "session.failed" ? "error" : "warn",
          message: p.message ?? p.reason ?? env.event_type,
          at: now,
        },
      ]);
      return;
    }

    case "resource.warning": {
      const p = env.payload as unknown as ResourceWarningPayload;
      $resourceWarnings.set([...$resourceWarnings.get(), p]);
      return;
    }

    case "model_switched": {
      const p = env.payload as { to_model: string };
      if (p.to_model) $sessionModel.set(p.to_model);
      return;
    }

    case "self_improvement.tick": {
      // Renderers subscribe directly; no reducer state needed yet.
      return;
    }

    case "plan.proposed": {
      const p = env.payload as unknown as PlanProposedPayload;
      $planProposals.setKey(p.plan_id, {
        plan_id: p.plan_id,
        steps: p.steps,
        approved: false,
        created_at: now,
      });
      return;
    }

    case "plan.approved": {
      const p = env.payload as { plan_id: string };
      const existing = $planProposals.get()[p.plan_id];
      if (existing) $planProposals.setKey(p.plan_id, { ...existing, approved: true });
      return;
    }

    case "artifact.created": {
      const p = env.payload as unknown as ArtifactCreatedPayload;
      $artifacts.setKey(p.artifact_id, {
        id: p.artifact_id,
        kind: p.kind,
        title: p.title,
        path: p.path,
        url: p.url,
        content_type: p.content_type,
        bytes: p.bytes,
        version: 1,
        created_at: now,
        updated_at: now,
      });
      $artifactOrder.set([...$artifactOrder.get(), p.artifact_id]);
      return;
    }

    case "artifact.updated": {
      const p = env.payload as {
        artifact_id: string;
        patch?: Partial<ArtifactCreatedPayload>;
        version?: number;
      };
      const existing = $artifacts.get()[p.artifact_id];
      if (!existing) return;
      $artifacts.setKey(p.artifact_id, {
        ...existing,
        ...p.patch,
        version: p.version ?? existing.version + 1,
        updated_at: now,
      });
      return;
    }

    default:
      return;
  }
}

/** Clear all session-scoped stores (used on session switch). */
export function resetSessionStores(): void {
  $sessionId.set("");
  $sessionModel.set(null);
  $sessionCwd.set(null);
  $messages.set({});
  $messageOrder.set([]);
  $toolCalls.set({});
  $activeToolIds.set([]);
  $artifacts.set({});
  $artifactOrder.set([]);
  $permissionQueue.set([]);
  $planProposals.set({});
  $resourceWarnings.set([]);
  $systemNotices.set([]);
}

/** Resolve the permission from the queue after user reply. */
export function resolvePermission(request_id: string): void {
  $permissionQueue.set(
    $permissionQueue.get().filter((r) => r.request_id !== request_id),
  );
}
