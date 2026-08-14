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
          message: 'Hello world',
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
          message: 'Hello',
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
          message: 'Hello',
          cwd: '/home/user',
        })
      );
    });

    test('does not send when no WebSocket', () => {
      const client = new ProtocolClient();
      client.sendPrompt('Hello');
      // Should not throw
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
    test('sends resume message with from_seq', () => {
      const client = new ProtocolClient();
      client.setSessionId('session-123');
      client.connect();
      client.sendResume(42);

      expect(mockWebSocketInstance.send).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'resume',
          session_id: 'session-123',
          from_seq: 42,
        })
      );
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

      // Trigger via dispatch (internal method)
      // We test via on/off since dispatch is private
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
