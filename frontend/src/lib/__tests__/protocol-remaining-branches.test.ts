import { ProtocolClient, EventType } from '../protocol';
import type { WSEnvelopeClient } from '../protocol';
import { SessionStore, SessionEvent, SessionStatus } from '../session-store';

// ===========================================================================
// ProtocolClient — remaining branch coverage
// ===========================================================================

describe('ProtocolClient — setState and connect gaps', () => {
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
    global.clearInterval = jest.fn();
  });

  it('connect when no sessionId returns early', () => {
    const client = new ProtocolClient();
    const stateHandler = jest.fn();
    client.onStateChange(stateHandler);
    client.connect();
    expect(stateHandler).toHaveBeenCalledWith({ state: 'disconnected', error: null });
  });

  it('setState invokes stateHandlers', () => {
    const client = new ProtocolClient();
    const handler = jest.fn();
    client.onStateChange(handler);
    client.setSessionId('s1');
    client.connect();
    mockInstance.onopen?.();
    expect(handler).toHaveBeenCalledWith({ state: 'connected', error: null });
  });

  it('on with existing key adds handler to set', () => {
    const client = new ProtocolClient();
    const h1 = jest.fn();
    const h2 = jest.fn();
    client.on(EventType.SESSION_CREATED, h1);
    client.on(EventType.SESSION_CREATED, h2);
    client.setSessionId('s1');
    client.connect();
    mockInstance.onopen?.();
    mockInstance.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ session_id: 's1', event_type: EventType.SESSION_CREATED, payload: {}, protocol_version: '1.0' }),
    }));
    expect(h1).toHaveBeenCalled();
    expect(h2).toHaveBeenCalled();
  });

  it('off removes handler from existing set', () => {
    const client = new ProtocolClient();
    const handler = jest.fn();
    client.on(EventType.SESSION_CREATED, handler);
    client.off(EventType.SESSION_CREATED, handler);
    client.setSessionId('s1');
    client.connect();
    mockInstance.onopen?.();
    mockInstance.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ session_id: 's1', event_type: EventType.SESSION_CREATED, payload: {}, protocol_version: '1.0' }),
    }));
    expect(handler).not.toHaveBeenCalled();
  });

  it('off on non-existent key is a no-op', () => {
    const client = new ProtocolClient();
    // Should not throw when key doesn't exist
    expect(() => client.off(EventType.SESSION_CREATED, jest.fn())).not.toThrow();
  });

  it('onclose triggers handleCloseEvent', () => {
    const client = new ProtocolClient();
    client.setSessionId('s1');
    const spy = jest.spyOn(client as any, 'handleCloseEvent');
    client.connect();
    mockInstance.onclose?.(new CloseEvent('close', { code: 4000, reason: 'Error' }));
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });
});

// ===========================================================================
// SessionStore — ASSISTANT_DELTA if(session) body coverage
// ===========================================================================

describe('SessionStore — ASSISTANT_DELTA if(session) body', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient> & { _trigger: (event: string, envelope: WSEnvelopeClient) => void };
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    const listeners = new Map<string, Array<(envelope: WSEnvelopeClient) => void>>();
    mockProtocolClient = {
      on: jest.fn((event, handler) => {
        if (!listeners.has(event)) listeners.set(event, []);
        listeners.get(event)!.push(handler);
      }),
      emit: jest.fn(),
      connect: jest.fn(),
      disconnect: jest.fn(),
      setSessionId: jest.fn(),
      _trigger: (event: string, envelope: WSEnvelopeClient) => {
        const handlers = listeners.get(event) ?? [];
        handlers.forEach((h) => h(envelope));
      },
    } as any;
    store = new SessionStore(mockProtocolClient);
  });

  test('ASSISTANT_DELTA updates session when exists', () => {
    (store as any).sessions.set('ad-1', {
      id: 'ad-1', title: 'Delta Test', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 10,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const envelope: WSEnvelopeClient = {
      session_id: 'ad-1',
      event_type: 'assistant.delta',
      payload: { message: 'partial' },
      seq: 15,
      protocol_version: '1.0',
      timestamp: new Date().toISOString(),
    };
    mockProtocolClient._trigger(EventType.ASSISTANT_DELTA, envelope);

    const session = store.getAll()[0];
    expect(session.current_seq).toBe(15);
    expect(session.updated_at).toBeTruthy();
  });

  test('ASSISTANT_DELTA does nothing when session missing', () => {
    const envelope: WSEnvelopeClient = {
      session_id: 'nonexistent',
      event_type: 'assistant.delta',
      payload: {},
      protocol_version: '1.0',
      timestamp: new Date().toISOString(),
    };
    expect(() => mockProtocolClient._trigger(EventType.ASSISTANT_DELTA, envelope)).not.toThrow();
    expect(store.getAll()).toEqual([]);
  });
});
