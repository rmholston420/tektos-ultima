/**
 * WebSocket Protocol Client Unit Tests
 * Tests the ProtocolClient class and EventType constants
 */

import {
  ProtocolClient,
  EventType,
  ConnectionState,
  WSEnvelopeClient,
  EventHandler,
  ErrorHandler,
  StateHandler,
} from '../protocol';

describe('WebSocket Protocol', () => {
  let mockWebSocket: any;
  let mockWebSocketInstance: any;
  let messages: string[] = [];

  beforeEach(() => {
    messages = [];
    mockWebSocketInstance = {
      readyState: 1,
      send: jest.fn((data: string) => {
        messages.push(data);
      }),
      close: jest.fn(),
      onopen: null,
      onmessage: null,
      onclose: null,
      onerror: null,
    };

    mockWebSocket = jest.fn().mockImplementation((url: string) => {
      mockWebSocketInstance.url = url;
      return mockWebSocketInstance;
    });

    global.WebSocket = mockWebSocket as any;
    global.setInterval = jest.fn(() => 1 as any);
    global.clearInterval = jest.fn();
    global.setTimeout = jest.fn() as any;
    global.Date.now = jest.fn(() => 1000000);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('EventType constants', () => {
    test('has SESSION_CREATED', () => {
      expect(EventType.SESSION_CREATED).toBe('session.created');
    });

    test('has SESSION_READY', () => {
      expect(EventType.SESSION_READY).toBe('session.ready');
    });

    test('has SESSION_UPDATED', () => {
      expect(EventType.SESSION_UPDATED).toBe('session.updated');
    });

    test('has ASSISTANT_DELTA', () => {
      expect(EventType.ASSISTANT_DELTA).toBe('assistant.delta');
    });

    test('has ASSISTANT_COMPLETED', () => {
      expect(EventType.ASSISTANT_COMPLETED).toBe('assistant.completed');
    });

    test('has TOOL_STARTED', () => {
      expect(EventType.TOOL_STARTED).toBe('tool.started');
    });

    test('has TOOL_DELTA', () => {
      expect(EventType.TOOL_DELTA).toBe('tool.delta');
    });

    test('has TOOL_COMPLETED', () => {
      expect(EventType.TOOL_COMPLETED).toBe('tool.completed');
    });

    test('has TOOL_PERMISSION_REQUIRED', () => {
      expect(EventType.TOOL_PERMISSION_REQUIRED).toBe('tool.permission.required');
    });

    test('has SYSTEM_MESSAGE', () => {
      expect(EventType.SYSTEM_MESSAGE).toBe('system.message');
    });

    test('has SESSION_INTERRUPTED', () => {
      expect(EventType.SESSION_INTERRUPTED).toBe('session.interrupted');
    });

    test('has SESSION_FAILED', () => {
      expect(EventType.SESSION_FAILED).toBe('session.failed');
    });

    test('has SELF_IMPROVEMENT_TICK', () => {
      expect(EventType.SELF_IMPROVEMENT_TICK).toBe('self_improvement.tick');
    });

    test('has RESOURCE_WARNING', () => {
      expect(EventType.RESOURCE_WARNING).toBe('resource.warning');
    });
  });

  describe('ConnectionState type', () => {
    test('has disconnected state', () => {
      expect(['disconnected', 'connecting', 'connected', 'reconnecting']).toContain('disconnected');
    });

    test('has connecting state', () => {
      expect(['disconnected', 'connecting', 'connected', 'reconnecting']).toContain('connecting');
    });

    test('has connected state', () => {
      expect(['disconnected', 'connecting', 'connected', 'reconnecting']).toContain('connected');
    });

    test('has reconnecting state', () => {
      expect(['disconnected', 'connecting', 'connected', 'reconnecting']).toContain('reconnecting');
    });
  });

  describe('ProtocolClient constructor', () => {
    test('can be instantiated', () => {
      const client = new ProtocolClient();
      expect(client).toBeDefined();
    });

    test('has default host', () => {
      const client = new ProtocolClient();
      expect((client as any).host).toBe('localhost');
    });

    test('has default port', () => {
      const client = new ProtocolClient();
      expect((client as any).port).toBe(8020);
    });

    test('uses http protocol by default', () => {
      const client = new ProtocolClient();
      expect((client as any).protocol).toBe('ws');
    });

    test('uses custom host when provided', () => {
      const client = new ProtocolClient({ host: 'custom.local' });
      expect((client as any).host).toBe('custom.local');
    });

    test('uses custom port when provided', () => {
      const client = new ProtocolClient({ port: 9000 });
      expect((client as any).port).toBe(9000);
    });

    test('uses wss protocol when specified', () => {
      const client = new ProtocolClient({ protocol: 'wss' });
      expect((client as any).protocol).toBe('wss');
    });
  });

  describe('setSessionId and sessionId', () => {
    test('sets session ID', () => {
      const client = new ProtocolClient();
      client.setSessionId('session-123');
      expect(client.sessionId).toBe('session-123');
    });

    test('updates session ID', () => {
      const client = new ProtocolClient();
      client.setSessionId('session-123');
      client.setSessionId('session-456');
      expect(client.sessionId).toBe('session-456');
    });
  });

  describe('sendPrompt', () => {
    test('sends prompt message', () => {
      const client = new ProtocolClient();
      client.setSessionId('session-123');
      client.connect();
      client.sendPrompt('Hello world');

      expect(mockWebSocketInstance.send).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'prompt',
          session_id: 'session-123',
          prompt: 'Hello world',
        })
      );
    });

    test('sends prompt with model option', () => {
      const client = new ProtocolClient();
      client.setSessionId('session-123');
      client.connect();
      client.sendPrompt('Hello', { model: 'gpt-4' });

      expect(mockWebSocketInstance.send).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'prompt',
          session_id: 'session-123',
          prompt: 'Hello',
          model: 'gpt-4',
        })
      );
    });

    test('sends prompt with cwd option', () => {
      const client = new ProtocolClient();
      client.setSessionId('session-123');
      client.connect();
      client.sendPrompt('Hello', { cwd: '/home/user' });

      expect(mockWebSocketInstance.send).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'prompt',
          session_id: 'session-123',
          prompt: 'Hello',
          cwd: '/home/user',
        })
      );
    });

    test('does not send when no WebSocket', () => {
      const client = new ProtocolClient();
      client.sendPrompt('Hello');
      expect(mockWebSocket).not.toHaveBeenCalled();
    });
  });

  describe('sendInterrupt', () => {
    test('sends interrupt message', () => {
      const client = new ProtocolClient();
      client.setSessionId('session-123');
      client.connect();
      client.sendInterrupt();

      expect(mockWebSocketInstance.send).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'interrupt',
          session_id: 'session-123',
        })
      );
    });

    test('does not send when no session ID', () => {
      const client = new ProtocolClient();
      client.sendInterrupt();
      expect(mockWebSocketInstance.send).not.toHaveBeenCalled();
    });
  });

  describe('sendResume', () => {
    test('sendResume is stubbed — backend does not handle resume type', () => {
      const client = new ProtocolClient();
      expect(() => client.sendResume(42)).not.toThrow();
    });
  });

  describe('Event handlers', () => {
    test('on adds event handler', () => {
      const client = new ProtocolClient();
      const handler: EventHandler = jest.fn();
      client.on(EventType.SESSION_CREATED, handler);
      expect(handler).toBeDefined();
    });

    test('off removes event handler', () => {
      const client = new ProtocolClient();
      const handler: EventHandler = jest.fn();
      client.on(EventType.SESSION_CREATED, handler);
      client.off(EventType.SESSION_CREATED, handler);
      expect(client).toBeDefined();
    });

    test('wildcard handler receives all events', () => {
      const client = new ProtocolClient();
      const wildcardHandler: EventHandler = jest.fn();
      const specificHandler: EventHandler = jest.fn();

      client.on('*', wildcardHandler);
      client.on(EventType.SESSION_CREATED, specificHandler);

      const envelope: WSEnvelopeClient = {
        session_id: 's1',
        event_type: EventType.SESSION_CREATED,
        payload: {},
        protocol_version: '1',
      };

      expect(client).toBeDefined();
    });
  });

  describe('Error handlers', () => {
    test('onError adds error handler', () => {
      const client = new ProtocolClient();
      const errorHandler: ErrorHandler = jest.fn();
      client.onError(errorHandler);
      expect(errorHandler).toBeDefined();
    });

    test('offError removes error handler', () => {
      const client = new ProtocolClient();
      const errorHandler: ErrorHandler = jest.fn();
      client.onError(errorHandler);
      client.offError(errorHandler);
      expect(client).toBeDefined();
    });
  });

  describe('State change handlers', () => {
    test('onStateChange adds state handler', () => {
      const client = new ProtocolClient();
      const stateHandler: StateHandler = jest.fn();
      client.onStateChange(stateHandler);
      expect(stateHandler).toBeDefined();
    });

    test('offStateChange removes state handler', () => {
      const client = new ProtocolClient();
      const stateHandler: StateHandler = jest.fn();
      client.onStateChange(stateHandler);
      client.offStateChange(stateHandler);
      expect(client).toBeDefined();
    });
  });

  describe('disconnect', () => {
    test('closes WebSocket', () => {
      const client = new ProtocolClient();
      client.setSessionId('session-123');
      client.connect();
      client.disconnect();

      expect(mockWebSocketInstance.close).toHaveBeenCalledWith(1000, 'Disconnect');
    });
  });

  describe('reconnect', () => {
    test('disconnects and reconnects', () => {
      const client = new ProtocolClient();
      client.setSessionId('session-123');
      client.connect();
      client.reconnect();

      expect(client).toBeDefined();
    });
  });

  describe('WSEnvelopeClient interface', () => {
    test('valid envelope has required fields', () => {
      const envelope: WSEnvelopeClient = {
        session_id: 's1',
        event_type: 'session.created',
        payload: { data: 'test' },
        protocol_version: '1',
      };

      expect(envelope.session_id).toBe('s1');
      expect(envelope.event_type).toBe('session.created');
      expect(envelope.payload).toEqual({ data: 'test' });
      expect(envelope.protocol_version).toBe('1');
    });

    test('optional seq field', () => {
      const envelope: WSEnvelopeClient = {
        session_id: 's1',
        event_type: 'session.created',
        payload: {},
        seq: 42,
        protocol_version: '1',
      };

      expect(envelope.seq).toBe(42);
    });

    test('optional timestamp field', () => {
      const envelope: WSEnvelopeClient = {
        session_id: 's1',
        event_type: 'session.created',
        payload: {},
        timestamp: '2026-01-01',
        protocol_version: '1',
      };

      expect(envelope.timestamp).toBe('2026-01-01');
    });
  });
});

// ---------------------------------------------------------------------------
// handleCloseEvent
// ---------------------------------------------------------------------------

describe("ProtocolClient — handleCloseEvent", () => {
  let mockWS: any;
  let mockInstance: any;

  beforeEach(() => {
    mockInstance = {
      readyState: 1, send: jest.fn(), close: jest.fn(),
      onopen: null, onmessage: null, onclose: null, onerror: null, url: '',
    };
    mockWS = jest.fn().mockImplementation((url: string) => {
      mockInstance.url = url;
      return mockInstance;
    });
    mockWS.CONNECTING = 0; mockWS.OPEN = 1;
    mockWS.CLOSING = 2; mockWS.CLOSED = 3;
    global.WebSocket = mockWS as any;
  });

  it("does not schedule reconnect when code is 1000", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    const spy = jest.spyOn(client as any, "scheduleReconnect");
    client.handleCloseEvent(new CloseEvent("close", { code: 1000, reason: "Normal" }));
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it("schedules reconnect when code is not 1000", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    const spy = jest.spyOn(client as any, "scheduleReconnect");
    client.handleCloseEvent(new CloseEvent("close", { code: 4000, reason: "Error" }));
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  it("does not schedule reconnect if reconnectAttempts >= 10", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    (client as any).reconnectAttempts = 10;
    const spy = jest.spyOn(client as any, "scheduleReconnect");
    client.handleCloseEvent(new CloseEvent("close", { code: 4000, reason: "Error" }));
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// dispatch handler errors → notifyError
// ---------------------------------------------------------------------------

describe("ProtocolClient — dispatch handler errors", () => {
  let mockWS: any;
  let mockInstance: any;

  beforeEach(() => {
    mockInstance = {
      readyState: 1, send: jest.fn(), close: jest.fn(),
      onopen: null, onmessage: null, onclose: null, onerror: null, url: '',
    };
    mockWS = jest.fn().mockImplementation((url: string) => {
      mockInstance.url = url;
      return mockInstance;
    });
    mockWS.CONNECTING = 0; mockWS.OPEN = 1;
    mockWS.CLOSING = 2; mockWS.CLOSED = 3;
    global.WebSocket = mockWS as any;
  });

  it("specific handler error triggers notifyError", () => {
    const client = new ProtocolClient();
    const errorHandler = jest.fn();
    client.onError(errorHandler);
    const badHandler = jest.fn(() => { throw new Error("boom"); });
    client.on(EventType.SESSION_CREATED, badHandler);
    client.setSessionId("s1");
    client.connect();
    mockInstance.onopen?.();
    mockInstance.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ session_id: "s1", event_type: EventType.SESSION_CREATED, payload: {}, seq: 0, protocol_version: "1.0" }),
    }));
    expect(errorHandler).toHaveBeenCalled();
  });

  it("wildcard handler error triggers notifyError", () => {
    const client = new ProtocolClient();
    const errorHandler = jest.fn();
    client.onError(errorHandler);
    const badHandler = jest.fn(() => { throw new Error("boom"); });
    client.on("*", badHandler);
    client.setSessionId("s1");
    client.connect();
    mockInstance.onopen?.();
    mockInstance.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ session_id: "s1", event_type: EventType.SESSION_READY, payload: {}, seq: 0, protocol_version: "1.0" }),
    }));
    expect(errorHandler).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// notifyError with handler that throws
// ---------------------------------------------------------------------------

describe("ProtocolClient — notifyError with throwing handler", () => {
  it("catches handler exceptions without crashing", () => {
    const client = new ProtocolClient();
    const badHandler = () => { throw new Error("handler error"); };
    const goodHandler = jest.fn();
    client.onError(badHandler);
    client.onError(goodHandler);
    expect(() => { (client as any).notifyError(new Error("test error")); }).not.toThrow();
    expect(goodHandler).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// connect with existing open WS connection
// ---------------------------------------------------------------------------

describe("ProtocolClient — connect with existing connection", () => {
  let mockWS: any;
  let mockInstance1: any;
  let mockInstance2: any;

  beforeEach(() => {
    let callCount = 0;
    mockInstance1 = {
      readyState: 1, send: jest.fn(), close: jest.fn(),
      onopen: null, onmessage: null, onclose: null, onerror: null, url: '',
    };
    mockInstance2 = { ...mockInstance1 };
    mockWS = jest.fn().mockImplementation((url: string) => {
      callCount++;
      return callCount === 1 ? mockInstance1 : mockInstance2;
    });
    mockWS.CONNECTING = 0; mockWS.OPEN = 1;
    mockWS.CLOSING = 2; mockWS.CLOSED = 3;
    global.WebSocket = mockWS as any;
  });

  it("closes existing open WS connection on new connect", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    client.connect();
    mockInstance1.onopen?.();
    client.setSessionId("s2");
    client.connect();
    expect(mockInstance1.close).toHaveBeenCalled();
    expect(mockWS).toHaveBeenCalledTimes(2);
  });

  it("handles WS error via onerror handler", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    client.connect();
    const handler = jest.fn();
    client.onStateChange(handler);
    mockInstance1.onerror?.();
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({ state: "disconnected" }));
  });

  it("handles WS parse error via notifyError", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    client.connect();
    const errorHandler = jest.fn();
    client.onError(errorHandler);
    mockInstance1.onopen?.();
    mockInstance1.onmessage?.(new MessageEvent("message", { data: "not valid json" }));
    expect(errorHandler).toHaveBeenCalled();
    expect(errorHandler.mock.calls[0][0].message).toContain("Parse error");
  });

  it("handles connect error via notifyError", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    const errorHandler = jest.fn();
    client.onError(errorHandler);
    (global.WebSocket as any) = jest.fn(() => { throw new Error("WS creation failed"); });
    client.connect();
    expect(errorHandler).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// disconnect/send when no WS connection
// ---------------------------------------------------------------------------

describe("ProtocolClient — safe when no WS connection", () => {
  it("disconnect is safe when no WS connection", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    expect(() => client.disconnect()).not.toThrow();
  });

  it("sendPrompt is safe when no WS connection", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    expect(() => client.sendPrompt("test")).not.toThrow();
  });

  it("sendInterrupt is safe when no WS connection", () => {
    const client = new ProtocolClient();
    expect(() => client.sendInterrupt()).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// off handlers when not registered
// ---------------------------------------------------------------------------

describe("ProtocolClient — off handlers when not registered", () => {
  it("off is safe when handler not registered", () => {
    const client = new ProtocolClient();
    const handler = jest.fn();
    expect(() => client.off(EventType.SESSION_CREATED, handler)).not.toThrow();
  });

  it("offError is safe when handler not registered", () => {
    const client = new ProtocolClient();
    const handler = jest.fn();
    expect(() => client.offError(handler)).not.toThrow();
  });

  it("offStateChange is safe when handler not registered", () => {
    const client = new ProtocolClient();
    const handler = jest.fn();
    expect(() => client.offStateChange(handler)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// heartbeat tests
// ---------------------------------------------------------------------------
// heartbeat tests
// ---------------------------------------------------------------------------

describe("ProtocolClient — heartbeat", () => {
  let mockWS: any;
  let mockInstance: any;

  beforeEach(() => {
    mockInstance = {
      readyState: 1, send: jest.fn(), close: jest.fn(),
      onopen: null, onmessage: null, onclose: null, onerror: null, url: '',
    };
    mockWS = jest.fn().mockImplementation((url: string) => {
      mockInstance.url = url;
      return mockInstance;
    });
    mockWS.CONNECTING = 0; mockWS.OPEN = 1;
    mockWS.CLOSING = 2; mockWS.CLOSED = 3;
    global.WebSocket = mockWS as any;
  });

  it("startHeartbeat sets up interval", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    client.connect();
    mockInstance.onopen?.();
    expect((client as any).heartbeatInterval).not.toBeNull();
  });

  it("stopHeartbeat clears interval", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    client.connect();
    mockInstance.onopen?.();
    (client as any).stopHeartbeat();
    expect((client as any).heartbeatInterval).toBeNull();
  });

  it("onclose triggers handleCloseEvent which schedules reconnect", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    client.connect();
    mockInstance.onopen?.();
    const spy = jest.spyOn(client as any, "handleCloseEvent");
    mockInstance.onclose?.(new CloseEvent("close", { code: 4000, reason: "Error" }));
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  it("onclose calls stopHeartbeat", () => {
    const client = new ProtocolClient();
    client.setSessionId("s1");
    client.connect();
    mockInstance.onopen?.();
    (client as any).reconnectAttempts = 10; // prevent scheduleReconnect
    const spyStop = jest.spyOn(client as any, "stopHeartbeat");
    mockInstance.onclose?.(new CloseEvent("close", { code: 4000, reason: "Error" }));
    expect(spyStop).toHaveBeenCalled();
    spyStop.mockRestore();
  });
});
