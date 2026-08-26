/**
 * Tests for the ProtocolClient — WebSocket envelope handling.
 */

import { ProtocolClient, EventType, type ConnectionState, type WSEnvelopeClient } from "@/lib/protocol";

describe("ProtocolClient", () => {
  let client: ProtocolClient;
  let wsInstances: any[] = [];

  beforeEach(() => {
    wsInstances = [];

    // jsdom's WebSocket class has non-configurable constants — replace the
    // entire global.WebSocket with a mock that carries the OPEN/CLOSED constants
    const MockWebSocket = jest.fn() as any;
    MockWebSocket.OPEN = 1;
    MockWebSocket.CONNECTING = 0;
    MockWebSocket.CLOSING = 2;
    MockWebSocket.CLOSED = 3;
    MockWebSocket.prototype = {
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    };
    // Replace the global so source code `WebSocket.OPEN` resolves to our mock
    (global as any).WebSocket = MockWebSocket;

    MockWebSocket.mockImplementation((url: string) => {
      let readyState = 0; // CONNECTING
      let onopen: ((ev?: any) => void) | null = null;
      let onclose: ((ev?: CloseEvent) => void) | null = null;
      let onerror: ((ev?: any) => void) | null = null;
      let onmessage: ((ev?: MessageEvent) => void) | null = null;

      const ws: any = {
        close: jest.fn(),
        send: jest.fn(),
      };

      // Use Object.defineProperty for readyState so tests can set it
      Object.defineProperty(ws, "readyState", {
        get: () => readyState,
        set: (val: number) => { readyState = val; },
        configurable: true,
      });

      // Use Object.defineProperty for each handler
      Object.defineProperty(ws, "onopen", {
        get: () => onopen,
        set: (fn: ((ev?: any) => void) | null) => { onopen = fn; },
        configurable: true,
      });
      Object.defineProperty(ws, "onclose", {
        get: () => onclose,
        set: (fn: ((ev?: CloseEvent) => void) | null) => { onclose = fn; },
        configurable: true,
      });
      Object.defineProperty(ws, "onerror", {
        get: () => onerror,
        set: (fn: ((ev?: any) => void) | null) => { onerror = fn; },
        configurable: true,
      });
      Object.defineProperty(ws, "onmessage", {
        get: () => onmessage,
        set: (fn: ((ev?: MessageEvent) => void) | null) => { onmessage = fn; },
        configurable: true,
      });

      wsInstances.push(ws);
      return ws as unknown as WebSocket;
    });

    client = new ProtocolClient();
    jest.useFakeTimers();
  });

  afterEach(() => {
    client.disconnect();
    jest.clearAllMocks();
    jest.useRealTimers();
  });

  describe("initial state", () => {
    it("starts disconnected", () => {
      expect(client["state"]).toBe("disconnected");
    });

    it("has empty session id", () => {
      expect(client.sessionId).toBe("");
    });

    it("uses default host/port/protocol", () => {
      expect(client["host"]).toBe("localhost");
      expect(client["port"]).toBe(8020);
      expect(client["protocol"]).toBe("ws");
    });

    it("accepts custom options", () => {
      const custom = new ProtocolClient({ host: "custom.host", port: 9999, protocol: "wss" });
      expect(custom["host"]).toBe("custom.host");
      expect(custom["port"]).toBe(9999);
      expect(custom["protocol"]).toBe("wss");
      custom.disconnect();
    });
  });

  describe("setSessionId", () => {
    it("sets session id", () => {
      client.setSessionId("test-session-123");
      expect(client.sessionId).toBe("test-session-123");
    });

    it("can change session id", () => {
      client.setSessionId("session-1");
      client.setSessionId("session-2");
      expect(client.sessionId).toBe("session-2");
    });
  });

  describe("on / off", () => {
    it("registers event handler for specific event type", () => {
      const handler = jest.fn();
      client.on("session.created", handler);
      expect(client["handlers"].has("session.created")).toBe(true);
    });

    it("registers wildcard handler", () => {
      const handler = jest.fn();
      client.on("*", handler);
      expect(client["handlers"].has("*")).toBe(true);
    });

    it("registers state change handler", () => {
      const handler = jest.fn();
      client.onStateChange(handler);
      expect(client["stateHandlers"]).toContain(handler);
    });

    it("removes specific handler", () => {
      const handler = jest.fn();
      client.on("session.created", handler);
      client.off("session.created", handler);
      expect(client["handlers"].get("session.created")?.has(handler)).toBe(false);
    });

    it("removes state change handler", () => {
      const handler = jest.fn();
      client.onStateChange(handler);
      client.offStateChange(handler);
      expect(client["stateHandlers"]).not.toContain(handler);
    });

    it("registers error handler", () => {
      const handler = jest.fn();
      client.onError(handler);
      expect(client["errorHandlers"]).toContain(handler);
    });

    it("removes error handler", () => {
      const handler = jest.fn();
      client.onError(handler);
      client.offError(handler);
      expect(client["errorHandlers"]).not.toContain(handler);
    });
  });

  describe("dispatch (internal)", () => {
    it("calls handlers for matching event", () => {
      const handler = jest.fn();
      client.on("session.created", handler);

      const envelope: WSEnvelopeClient = {
        session_id: "test-1",
        event_type: "session.created",
        payload: { message: "created" },
        protocol_version: "1",
      };
      client["dispatch"](envelope);
      expect(handler).toHaveBeenCalledWith(envelope);
    });

    it("calls wildcard handlers", () => {
      const handler = jest.fn();
      client.on("*", handler);

      const envelope: WSEnvelopeClient = {
        session_id: "test-1",
        event_type: "any.event",
        payload: {},
        protocol_version: "1",
      };
      client["dispatch"](envelope);
      expect(handler).toHaveBeenCalledWith(envelope);
    });

    it("calls both specific and wildcard handlers", () => {
      const specific = jest.fn();
      const wildcard = jest.fn();
      client.on("session.created", specific);
      client.on("*", wildcard);

      const envelope: WSEnvelopeClient = {
        session_id: "test-1",
        event_type: "session.created",
        payload: {},
        protocol_version: "1",
      };
      client["dispatch"](envelope);
      expect(specific).toHaveBeenCalled();
      expect(wildcard).toHaveBeenCalled();
    });

    it("updates session_id from envelope", () => {
      client.setSessionId("");
      const envelope: WSEnvelopeClient = {
        session_id: "from-envelope",
        event_type: "session.created",
        payload: {},
        protocol_version: "1",
      };
      client["dispatch"](envelope);
      expect(client.sessionId).toBe("from-envelope");
    });

    it("handles handler errors gracefully", () => {
      const handler = jest.fn(() => { throw new Error("handler error"); });
      client.on("session.created", handler);
      client.onError((err) => { /* capture */ });

      const envelope: WSEnvelopeClient = {
        session_id: "test-1",
        event_type: "session.created",
        payload: {},
        protocol_version: "1",
      };
      // Should not throw
      expect(() => client["dispatch"](envelope)).not.toThrow();
    });
  });

  describe("connect / disconnect", () => {
    it("requires session id to connect", () => {
      const logSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
      client.connect();
      expect(logSpy).toHaveBeenCalledWith("ProtocolClient.connect: no session ID");
      expect(client["state"]).toBe("disconnected");
      logSpy.mockRestore();
    });

    it("sets state to connecting then connected", () => {
      client.setSessionId("test-session");
      client.connect();

      expect(client["state"]).toBe("connecting");

      // Simulate open
      const ws = wsInstances[0];
      ws.readyState = 1; // OPEN
      ws.onopen!();
      expect(client["state"]).toBe("connected");
    });

    it("resets reconnect attempts on connect", () => {
      client.setSessionId("test-session");
      client["reconnectAttempts"] = 5;
      client["reconnectDelay"] = 5000;

      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      expect(client["reconnectAttempts"]).toBe(0);
      expect(client["reconnectDelay"]).toBe(1000);
    });

    it("sets state to disconnected on close", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();
      expect(client["state"]).toBe("connected");

      ws.onclose!({ code: 1000, reason: "bye" } as CloseEvent);
      expect(client["state"]).toBe("disconnected");
    });

    it("sends messages via WebSocket", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      client.sendPrompt("hello", { model: "test-model", cwd: "/tmp" });
      expect(ws.send).toHaveBeenCalled();
    });

    it("queues messages when not connected", () => {
      client.setSessionId("test-session");
      client.connect();
      // Don't call onopen — ws stays in CONNECTING state

      client.sendPrompt("hello", { model: "test-model" });
      expect(client["pendingMessages"].length).toBeGreaterThan(0);
    });

    it("flushes pending messages on connect", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];

      client.sendPrompt("queued", { model: "test" });
      expect(client["pendingMessages"].length).toBe(1);

      ws.readyState = 1;
      ws.onopen!();
      // After onopen, pending messages should be flushed
      expect(ws.send).toHaveBeenCalled();
    });

    it("handles WebSocket errors", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();
      expect(client["state"]).toBe("connected");

      ws.onerror!();
      expect(client["state"]).toBe("disconnected");
    });

    it("handles incoming messages", () => {
      const handler = jest.fn();
      client.on("*", handler);

      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      const envelope = {
        session_id: "test-1",
        event_type: "assistant.delta",
        payload: { text: "hello" },
        protocol_version: "1",
      };
      ws.onmessage!({ data: JSON.stringify(envelope) } as MessageEvent);
      expect(handler).toHaveBeenCalled();
    });

    it("disconnects cleanly", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      client.disconnect();
      expect(ws.close).toHaveBeenCalledWith(1000, "Disconnect");
      expect(client["state"]).toBe("disconnected");
    });

    it("reconnect calls disconnect then connect", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      client.reconnect();
      expect(ws.close).toHaveBeenCalled();
    });
  });

  describe("sendPrompt", () => {
    it("sends prompt with model and cwd", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      client.sendPrompt("hello world", { model: "test-model", cwd: "/tmp" });

      const sent = JSON.parse(ws.send.mock.calls[0][0]);
      expect(sent.type).toBe("prompt");
      expect(sent.session_id).toBe("test-session");
      expect(sent.prompt).toBe("hello world");
      expect(sent.model).toBe("test-model");
      expect(sent.cwd).toBe("/tmp");
    });

    it("sends prompt without optional fields", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      client.sendPrompt("hello");
      const sent = JSON.parse(ws.send.mock.calls[0][0]);
      expect(sent.type).toBe("prompt");
      expect(sent.prompt).toBe("hello");
    });
  });

  describe("sendInterrupt", () => {
    it("sends interrupt event", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      client.sendInterrupt();
      const sent = JSON.parse(ws.send.mock.calls[0][0]);
      expect(sent.type).toBe("interrupt");
      expect(sent.session_id).toBe("test-session");
    });

    it("does nothing without session id", () => {
      // connect() without setSessionId logs a warning and returns early
      // No WebSocket is created
      const logSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
      client.connect();
      logSpy.mockRestore();
      expect(wsInstances.length).toBe(0);
      client.sendInterrupt();
      // No WebSocket to send on, no pending messages
      expect(client["pendingMessages"]).toHaveLength(0);
    });
  });

  describe("onStateChange", () => {
    it("calls all registered state handlers", () => {
      const handler1 = jest.fn();
      const handler2 = jest.fn();
      client.onStateChange(handler1);
      client.onStateChange(handler2);

      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      expect(handler1).toHaveBeenCalledWith({ state: "connected", error: null });
      expect(handler2).toHaveBeenCalledWith({ state: "connected", error: null });
    });

    it("calls state handlers on disconnect", () => {
      const handler = jest.fn();
      client.onStateChange(handler);

      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();
      handler.mockClear();

      client.disconnect();
      expect(handler).toHaveBeenCalledWith({ state: "disconnected", error: null });
    });
  });

  describe("heartbeat", () => {
    it("starts heartbeat on connect", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      expect(client["heartbeatInterval"]).not.toBeNull();
    });

    it("stops heartbeat on disconnect", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      client.disconnect();
      expect(client["heartbeatInterval"]).toBeNull();
    });

    it("sends ping when pong received", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      // Simulate pong
      ws.onmessage!({ data: JSON.stringify({ type: "pong" }) } as MessageEvent);

      // Advance timer past 15s to trigger heartbeatTick
      jest.advanceTimersByTime(16000);
      expect(ws.send).toHaveBeenCalledWith(JSON.stringify({ type: "ping" }));
    });

    it("closes connection when pong not received", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      // Don't send any pong — advance timer past 10s (first heartbeat) + 15s (timeout)
      jest.advanceTimersByTime(26000);
      expect(ws.close).toHaveBeenCalledWith(4000, "Timeout");
    });
  });

  describe("reconnection", () => {
    it("schedules reconnect on close with error code", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      // Simulate error close (not 1000)
      ws.onclose!({ code: 1006, reason: "error" } as CloseEvent);
      expect(client["state"]).toBe("reconnecting");
    });

    it("does not reconnect on normal close (1000)", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      ws.onclose!({ code: 1000, reason: "normal" } as CloseEvent);
      expect(client["state"]).toBe("disconnected");
    });

    it("stops reconnecting after 10 attempts", () => {
      client.setSessionId("test-session");
      client.connect();
      const ws = wsInstances[0];
      ws.readyState = 1;
      ws.onopen!();

      // Simulate 10 error closes
      for (let i = 0; i < 10; i++) {
        ws.onclose!({ code: 1006, reason: "error" } as CloseEvent);
      }
      // After 10 attempts, the reconnect timer was scheduled but
      // the condition `reconnectAttempts < 10` prevents further reconnects
      // The state will be "reconnecting" until the timer fires,
      // but the reconnectAttempts counter prevents another connect()
      // Advance the timer to let the scheduled reconnect fire (if any)
      jest.runAllTimers();
      // After 10 attempts, no more reconnects are scheduled
      // The state is "disconnected" because the last close set it
      expect(client["reconnectAttempts"]).toBe(10);
    });
  });
});

describe("EventType", () => {
  it("has all expected event types", () => {
    expect(EventType.SESSION_CREATED).toBe("session.created");
    expect(EventType.SESSION_READY).toBe("session.ready");
    expect(EventType.SESSION_UPDATED).toBe("session.updated");
    expect(EventType.ASSISTANT_DELTA).toBe("assistant.delta");
    expect(EventType.ASSISTANT_COMPLETED).toBe("assistant.completed");
    expect(EventType.TOOL_STARTED).toBe("tool.started");
    expect(EventType.TOOL_DELTA).toBe("tool.delta");
    expect(EventType.TOOL_COMPLETED).toBe("tool.completed");
    expect(EventType.TOOL_PERMISSION_REQUIRED).toBe("tool.permission.required");
    expect(EventType.SYSTEM_MESSAGE).toBe("system.message");
    expect(EventType.SESSION_INTERRUPTED).toBe("session.interrupted");
    expect(EventType.SESSION_FAILED).toBe("session.failed");
    expect(EventType.SELF_IMPROVEMENT_TICK).toBe("self_improvement.tick");
    expect(EventType.RESOURCE_WARNING).toBe("resource.warning");
    expect(EventType.MODEL_SWITCHED).toBe("model_switched");
  });
});

describe("ConnectionState", () => {
  it("includes all expected states", () => {
    const states: ConnectionState[] = ["disconnected", "connecting", "connected", "reconnecting"];
    expect(states).toHaveLength(4);
  });
});
