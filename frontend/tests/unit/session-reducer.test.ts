import {
  $activeToolIds,
  $artifactOrder,
  $artifacts,
  $messageOrder,
  $messages,
  $permissionQueue,
  $planProposals,
  $resourceWarnings,
  $sessionId,
  $sessionModel,
  $systemNotices,
  $toolCalls,
  applyEnvelope,
  resetSessionStores,
} from "@/lib/stores/session";
import type { WSEnvelope } from "@/types/protocol";

function env<P>(event_type: string, payload: P, extra: Partial<WSEnvelope> = {}): WSEnvelope {
  return {
    session_id: "sess-1",
    event_type,
    payload: payload as unknown as Record<string, unknown>,
    protocol_version: "1.0.0",
    ...extra,
  };
}

beforeEach(() => resetSessionStores());

describe("applyEnvelope", () => {
  test("session.ready sets identity", () => {
    applyEnvelope(env("session.ready", { model: "granite-4.1", cwd: "/home/user" }));
    expect($sessionId.get()).toBe("sess-1");
    expect($sessionModel.get()).toBe("granite-4.1");
  });

  test("assistant.delta accumulates then completed finalizes", () => {
    applyEnvelope(env("assistant.delta", { message_id: "m1", delta: "Hello, " }));
    applyEnvelope(env("assistant.delta", { message_id: "m1", delta: "world." }));
    expect($messages.get()["m1"].text).toBe("Hello, world.");
    expect($messageOrder.get()).toEqual(["m1"]);
    applyEnvelope(
      env("assistant.completed", {
        message_id: "m1",
        text: "Hello, world.",
        usage: { prompt_tokens: 12, completion_tokens: 3, total_tokens: 15 },
      }),
    );
    expect($messages.get()["m1"].completed).toBe(true);
    expect($messages.get()["m1"].usage?.total).toBe(15);
  });

  test("tool lifecycle populates activeToolIds and attaches to correlated message", () => {
    applyEnvelope(
      env("assistant.delta", { message_id: "m2", delta: "..." }, { correlation_id: "c1" }),
    );
    applyEnvelope(
      env(
        "tool.started",
        { tool_call_id: "t1", tool_name: "bash", arguments: { cmd: "ls" } },
        { correlation_id: "c1" },
      ),
    );
    expect($activeToolIds.get()).toEqual(["t1"]);
    expect($toolCalls.get()["t1"].status).toBe("running");
    expect($messages.get()["m2"].tool_call_ids).toEqual(["t1"]);
    applyEnvelope(env("tool.delta", { tool_call_id: "t1", delta: "out" }));
    applyEnvelope(
      env("tool.completed", {
        tool_call_id: "t1",
        tool_name: "bash",
        result: { code: 0 },
        duration_ms: 42,
      }),
    );
    expect($activeToolIds.get()).toEqual([]);
    expect($toolCalls.get()["t1"].status).toBe("completed");
    expect($toolCalls.get()["t1"].duration_ms).toBe(42);
    expect($toolCalls.get()["t1"].delta_chunks).toEqual(["out"]);
  });

  test("tool.completed with error marks errored", () => {
    applyEnvelope(env("tool.started", { tool_call_id: "t2", tool_name: "bash" }));
    applyEnvelope(env("tool.completed", { tool_call_id: "t2", tool_name: "bash", error: "boom" }));
    expect($toolCalls.get()["t2"].status).toBe("errored");
    expect($toolCalls.get()["t2"].error).toBe("boom");
  });

  test("permission and system notices queue", () => {
    applyEnvelope(env("tool.permission.required", {
      request_id: "p1", tool_name: "bash", reason: "root",
    }));
    expect($permissionQueue.get()).toHaveLength(1);
    applyEnvelope(env("system.message", { level: "warn", message: "watch out" }));
    expect($systemNotices.get()[0].level).toBe("warn");
  });

  test("resource.warning appends", () => {
    applyEnvelope(env("resource.warning", { kind: "vram", message: "80% used" }));
    expect($resourceWarnings.get()).toHaveLength(1);
  });

  test("model_switched updates model", () => {
    applyEnvelope(env("model_switched", { to_model: "qwen3-coder" }));
    expect($sessionModel.get()).toBe("qwen3-coder");
  });

  test("artifact.created + updated bumps version", () => {
    applyEnvelope(env("artifact.created", {
      artifact_id: "a1", kind: "file", title: "plan.md",
    }));
    expect($artifactOrder.get()).toEqual(["a1"]);
    expect($artifacts.get()["a1"].version).toBe(1);
    applyEnvelope(env("artifact.updated", { artifact_id: "a1" }));
    expect($artifacts.get()["a1"].version).toBe(2);
  });

  test("plan.proposed then plan.approved", () => {
    applyEnvelope(env("plan.proposed", {
      plan_id: "pl1",
      steps: [{ id: "s1", text: "do thing", requires_approval: true }],
    }));
    expect($planProposals.get()["pl1"].approved).toBe(false);
    applyEnvelope(env("plan.approved", { plan_id: "pl1" }));
    expect($planProposals.get()["pl1"].approved).toBe(true);
  });

  test("unknown event type is ignored", () => {
    expect(() => applyEnvelope(env("some.new.event.type", { anything: 1 }))).not.toThrow();
  });

  test("resetSessionStores clears state", () => {
    applyEnvelope(env("assistant.delta", { message_id: "x", delta: "..." }));
    resetSessionStores();
    expect(Object.keys($messages.get())).toHaveLength(0);
  });
});
