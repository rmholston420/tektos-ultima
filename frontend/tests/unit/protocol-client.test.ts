import { ProtocolClient } from "@/lib/protocol-client";
import type { WSEnvelope } from "@/types/protocol";

/** Minimal WebSocket mock capturing sent frames and driving lifecycle hooks. */
class MockWS {
  static OPEN = 1;
  static CLOSED = 3;
  readyState = 0;
  sent: string[] = [];
  onopen: ((e?: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e?: Event) => void) | null = null;

  constructor(public url: string) {}

  send(data: string): void {
    this.sent.push(data);
  }

  close(_code?: number, _reason?: string): void {
    this.readyState = MockWS.CLOSED;
    this.onclose?.({ code: 1000, reason: "test" } as CloseEvent);
  }

  open(): void {
    this.readyState = MockWS.OPEN;
    this.onopen?.();
  }

  emit(payload: unknown): void {
    this.onmessage?.({ data: typeof payload === "string" ? payload : JSON.stringify(payload) } as MessageEvent);
  }
}

// Provide a global WebSocket enum for readyState comparisons in client code.
(global as unknown as { WebSocket: { OPEN: number; CLOSED: number } }).WebSocket = {
  OPEN: 1,
  CLOSED: 3,
} as never;

describe("ProtocolClient", () => {
  test("dispatches raw envelope to specific and wildcard handlers", () => {
    const ws = new MockWS("ws://x");
    const c = new ProtocolClient({ wsFactory: () => ws as unknown as WebSocket });
    const seen: string[] = [];
    c.on("assistant.delta", (e) => seen.push("s:" + e.event_type));
    c.on("*", (e) => seen.push("w:" + e.event_type));
    c.connect();
    ws.open();
    ws.emit({
      session_id: "s",
      event_type: "assistant.delta",
      payload: { message_id: "m", delta: "hi" },
      protocol_version: "1.0.0",
    } satisfies WSEnvelope);
    expect(seen).toEqual(["s:assistant.delta", "w:assistant.delta"]);
  });

  test("handles JSON-RPC event notifications from gateway", () => {
    const ws = new MockWS("ws://x");
    const c = new ProtocolClient({ wsFactory: () => ws as unknown as WebSocket });
    const seen: string[] = [];
    c.on("*", (e) => seen.push(e.event_type));
    c.connect();
    ws.open();
    ws.emit({
      jsonrpc: "2.0",
      method: "event",
      params: { type: "session.ready", payload: { session_id: "s2", model: "m" } },
    });
    expect(seen).toContain("session.ready");
    expect(c.sessionId).toBe("s2");
  });

  test("sendPrompt queues before open and flushes after", () => {
    const ws = new MockWS("ws://x");
    const c = new ProtocolClient({ wsFactory: () => ws as unknown as WebSocket });
    c.setSessionId("s3");
    c.sendPrompt("hello");
    expect(ws.sent).toHaveLength(0);
    c.connect();
    ws.open();
    expect(ws.sent).toHaveLength(1);
    const parsed = JSON.parse(ws.sent[0]);
    expect(parsed.method).toBe("prompt.submit");
    expect(parsed.params.text).toBe("hello");
  });

  test("sendInterrupt sends when session set", () => {
    const ws = new MockWS("ws://x");
    const c = new ProtocolClient({ wsFactory: () => ws as unknown as WebSocket });
    c.setSessionId("s4");
    c.connect();
    ws.open();
    c.sendInterrupt();
    expect(JSON.parse(ws.sent[0]).method).toBe("session.interrupt");
  });

  test("state changes are broadcast", () => {
    const ws = new MockWS("ws://x");
    const c = new ProtocolClient({ wsFactory: () => ws as unknown as WebSocket });
    const states: string[] = [];
    c.onStateChange((s) => states.push(s.state));
    c.connect();
    expect(states).toContain("connecting");
    ws.open();
    expect(states).toContain("connected");
  });

  test("pong tracking is not dispatched as an event", () => {
    const ws = new MockWS("ws://x");
    const c = new ProtocolClient({ wsFactory: () => ws as unknown as WebSocket });
    const seen: string[] = [];
    c.on("*", (e) => seen.push(e.event_type));
    c.connect();
    ws.open();
    ws.emit({ type: "pong" });
    expect(seen).toHaveLength(0);
  });
});
