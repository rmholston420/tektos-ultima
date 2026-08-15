import { SessionStore, SessionSnapshot, SessionEvent, SessionStatus } from '../session-store';
import { ProtocolClient, EventType } from '../protocol';
import type { WSEnvelopeClient } from '../protocol';

// Mock fetch
global.fetch = jest.fn();

// ---------------------------------------------------------------------------
// Helper: build a minimal ProtocolClient mock that doesn't fire real listeners
// ---------------------------------------------------------------------------

function createMockProtocolClient(): jest.Mocked<ProtocolClient> & { _trigger: (event: string, envelope: WSEnvelopeClient) => void } {
  const listeners = new Map<string, Array<(envelope: WSEnvelopeClient) => void>>();
  const mock = {
    on: jest.fn(),
    emit: jest.fn(),
    connect: jest.fn(),
    disconnect: jest.fn(),
    setSessionId: jest.fn(),
    _trigger: (event: string, envelope: WSEnvelopeClient) => {
      const handlers = listeners.get(event) ?? [];
      handlers.forEach((h) => h(envelope));
    },
  } as jest.Mocked<ProtocolClient> & { _trigger: (event: string, envelope: WSEnvelopeClient) => void };

  mock.on.mockImplementation((event, handler) => {
    if (!listeners.has(event)) listeners.set(event, []);
    listeners.get(event)!.push(handler);
  });

  return mock;
}

// ---------------------------------------------------------------------------
// Helpers for constructing envelope payloads
// ---------------------------------------------------------------------------

function makeEnvelope(sessionId: string, payload: Record<string, unknown>, seq?: number): WSEnvelopeClient {
  return {
    session_id: sessionId,
    event_type: 'test',
    payload,
    seq: seq ?? 0,
    protocol_version: '1.0',
    timestamp: new Date().toISOString(),
  } as WSEnvelopeClient;
}

// ===========================================================================
// SessionStore — tagSession/branch coverage
// ===========================================================================

describe('SessionStore — tagSession branch coverage', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('tagSession updates existing session (if session branch)', async () => {
    const mockSession: SessionSnapshot = {
      id: 'tag-1', title: 'Tag Test', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };
    (store as any).sessions.set('tag-1', mockSession);

    await store.tagSession('tag-1', 'important');

    const session = store.getAll()[0];
    expect(session.tag).toBe('important');
  });

  test('tagSession with non-existent session (no if-branch hit)', async () => {
    await store.tagSession('nonexistent', 'important');
    // Should not throw even though session doesn't exist
    expect(store.getAll()).toEqual([]);
  });

  test('archiveSession updates existing session (if session branch)', async () => {
    const mockSession: SessionSnapshot = {
      id: 'arch-1', title: 'Archive Test', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };
    (store as any).sessions.set('arch-1', mockSession);
    (global as any).fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'arch-1' }),
    });

    await store.archiveSession('arch-1');

    const session = store.getAll()[0];
    expect(session.is_archived).toBe(true);
    expect(session.status).toBe('created');
  });

  test('archiveSession with non-existent session (no if-branch hit)', async () => {
    (global as any).fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'nonexistent' }),
    });

    await store.archiveSession('nonexistent');
    // Should not throw even though session doesn't exist in store
    expect(store.getAll()).toEqual([]);
  });
});

// ===========================================================================
// SessionStore — SESSION_UPDATED branch coverage
// ===========================================================================

describe('SessionStore — SESSION_UPDATED branches', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('SESSION_UPDATED updates status branch', () => {
    (store as any).sessions.set('upd-1', {
      id: 'upd-1', title: 'Update Status', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const envelope: WSEnvelopeClient = makeEnvelope('upd-1', { status: 'ready' });
    mockProtocolClient._trigger(EventType.SESSION_UPDATED, envelope);

    const session = store.getAll()[0];
    expect(session.status).toBe('ready');
  });

  test('SESSION_UPDATED updates title branch', () => {
    (store as any).sessions.set('upd-2', {
      id: 'upd-2', title: 'Old Title', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const envelope: WSEnvelopeClient = makeEnvelope('upd-2', { title: 'New Title' });
    mockProtocolClient._trigger(EventType.SESSION_UPDATED, envelope);

    const session = store.getAll()[0];
    expect(session.title).toBe('New Title');
  });

  test('SESSION_UPDATED with no session (if-branch not hit)', () => {
    const envelope: WSEnvelopeClient = makeEnvelope('nonexistent', { status: 'ready' });
    // Should not throw
    expect(() => mockProtocolClient._trigger(EventType.SESSION_UPDATED, envelope)).not.toThrow();
  });
});

// ===========================================================================
// SessionStore — SESSION_FAILED branch coverage
// ===========================================================================

describe('SessionStore — SESSION_FAILED branch', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('SESSION_FAILED sets failed status', () => {
    (store as any).sessions.set('fail-1', {
      id: 'fail-1', title: 'Fail Test', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    mockProtocolClient._trigger(EventType.SESSION_FAILED, makeEnvelope('fail-1', {}));

    const session = store.getAll()[0];
    expect(session.is_failed).toBe(true);
    expect(session.status).toBe('failed');
    expect(session.is_active).toBe(false);
  });

  test('SESSION_FAILED with no session (if-branch not hit)', () => {
    mockProtocolClient._trigger(EventType.SESSION_FAILED, makeEnvelope('nonexistent', {}));
    // Should not throw
    expect(() => mockProtocolClient._trigger(EventType.SESSION_FAILED, makeEnvelope('nonexistent', {}))).not.toThrow();
  });
});

// ===========================================================================
// SessionStore — forkSession branch coverage
// ===========================================================================

describe('SessionStore — forkSession branch coverage', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('forkSession creates new session with parent title', async () => {
    (global as any).fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 'fork-1',
        parent_title: 'Original Session',
        model: 'gpt-4',
        status: 'created',
      }),
    });

    const result = await store.forkSession('parent-1');
    expect(result.title).toBe('Fork of Original Session');
    expect(result.model).toBe('gpt-4');
    expect(result.root_session_id).toBe('parent-1');
    expect(result.is_active).toBe(false);
  });

  test('forkSession uses default model when response omits it', async () => {
    (global as any).fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 'fork-2',
        parent_title: 'Original',
        status: 'created',
        // model field omitted
      }),
    });

    const result = await store.forkSession('parent-2');
    expect(result.model).toBe('default');
  });
});

// ===========================================================================
// SessionStore — persist/loadFromStorage branch coverage
// ===========================================================================

describe('SessionStore — persist/loadFromStorage branches', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('persist serializes all sessions to localStorage', () => {
    (store as any).sessions.set('pers-1', {
      id: 'pers-1', title: 'Persist', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (store as any).persist();

    const stored = localStorage.getItem('tektos_sessions');
    expect(stored).toBeTruthy();
    const parsed = JSON.parse(stored!);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].id).toBe('pers-1');
  });

  test('loadFromStorage restores sessions from localStorage', () => {
    const mockSessions = [
      {
        id: 'load-1', title: 'Loaded', model: 'gpt-4',
        status: 'ready', is_active: true, is_archived: false,
        is_failed: false, current_seq: 5,
        created_at: '2026-01-01', updated_at: '2026-01-01',
      },
    ];
    localStorage.setItem('tektos_sessions', JSON.stringify(mockSessions));

    (store as any).loadFromStorage();

    const sessions = store.getAll();
    expect(sessions).toHaveLength(1);
    expect(sessions[0].id).toBe('load-1');
    expect(sessions[0].title).toBe('Loaded');
  });

  test('loadFromStorage handles corrupted JSON gracefully', () => {
    localStorage.setItem('tektos_sessions', 'not valid json');

    // Should not throw
    expect(() => (store as any).loadFromStorage()).not.toThrow();
  });

  test('loadFromStorage with no data in localStorage', () => {
    localStorage.removeItem('tektos_sessions');

    (store as any).loadFromStorage();

    expect(store.getAll()).toEqual([]);
  });
});

// ===========================================================================
// SessionStore — comprehensive event handler coverage
// ===========================================================================

describe('SessionStore — comprehensive event handler coverage', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('SESSION_READY activates session and sets current_seq', () => {
    (store as any).sessions.set('sr-1', {
      id: 'sr-1', title: 'Ready Test', model: 'gpt-4',
      status: 'running', is_active: false, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    mockProtocolClient._trigger(EventType.SESSION_READY, makeEnvelope('sr-1', { since_seq: 42 }));

    const session = store.getAll()[0];
    expect(session.status).toBe('ready');
    expect(session.is_active).toBe(true);
    expect(session.current_seq).toBe(42);
  });

  test('ASSISTANT_DELTA updates current_seq when envelope has seq', () => {
    (store as any).sessions.set('ad-1', {
      id: 'ad-1', title: 'Delta Test', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const envelope: WSEnvelopeClient = makeEnvelope('ad-1', { message: 'partial' }, 99);
    mockProtocolClient._trigger(EventType.ASSISTANT_DELTA, envelope);

    const session = store.getAll()[0];
    expect(session.current_seq).toBe(99);
  });

  test('multiple protocol events all update store', () => {
    (store as any).sessions.set('multi-1', {
      id: 'multi-1', title: 'Multi', model: 'gpt-4',
      status: 'running', is_active: false, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    // Trigger SESSION_READY
    mockProtocolClient._trigger(EventType.SESSION_READY, makeEnvelope('multi-1', { since_seq: 10 }));
    expect(store.getAll()[0].is_active).toBe(true);
    expect(store.getAll()[0].current_seq).toBe(10);

    // Trigger SESSION_UPDATED with title
    mockProtocolClient._trigger(EventType.SESSION_UPDATED, makeEnvelope('multi-1', { title: 'Updated Title' }));
    expect(store.getAll()[0].title).toBe('Updated Title');

    // Trigger ASSISTANT_DELTA (updates in-memory but doesn't call persist)
    mockProtocolClient._trigger(EventType.ASSISTANT_DELTA, makeEnvelope('multi-1', {}, 20));
    expect(store.getAll()[0].current_seq).toBe(20);

    // Verify localStorage was persisted by previous events (SESSION_READY, SESSION_UPDATED)
    const stored = localStorage.getItem('tektos_sessions');
    expect(stored).toBeTruthy();
    const parsed = JSON.parse(stored!);
    expect(parsed[0].title).toBe('Updated Title');
  });
});

// ===========================================================================
// SessionStore — ?? fallback branches
// ===========================================================================

describe('SessionStore — ?? fallback branches', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('SESSION_READY uses 0 when since_seq is falsy (?? fallback)', () => {
    (store as any).sessions.set('null-1', {
      id: 'null-1', title: 'Null Seq', model: 'gpt-4',
      status: 'running', is_active: false, is_archived: false,
      is_failed: false, current_seq: 99,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    // Build envelope with no since_seq at all (undefined, not 0)
    const envelope: WSEnvelopeClient = {
      session_id: 'null-1',
      event_type: 'session.ready',
      payload: {},
      protocol_version: '1.0',
      timestamp: new Date().toISOString(),
    };
    mockProtocolClient._trigger(EventType.SESSION_READY, envelope);

    const session = store.getAll()[0];
    expect(session.status).toBe('ready');
    expect(session.is_active).toBe(true);
    expect(session.current_seq).toBe(0); // ?? fallback to 0
  });

  test('ASSISTANT_DELTA preserves old seq when envelope.seq is falsy (?? fallback)', () => {
    (store as any).sessions.set('null-2', {
      id: 'null-2', title: 'Null Delta', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 77,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const envelope: WSEnvelopeClient = {
      session_id: 'null-2',
      event_type: 'assistant.delta',
      payload: { message: 'partial' },
      protocol_version: '1.0',
      timestamp: new Date().toISOString(),
    };
    mockProtocolClient._trigger(EventType.ASSISTANT_DELTA, envelope);

    const session = store.getAll()[0];
    expect(session.current_seq).toBe(77); // ?? fallback preserves old value
  });
});
