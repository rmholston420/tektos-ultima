/**
 * Session Store Unit Tests
 * Tests the SessionStore class and related types
 */

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
  } as unknown as jest.Mocked<ProtocolClient> & { _trigger: (event: string, envelope: WSEnvelopeClient) => void };

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
// SessionSnapshot interface
// ===========================================================================

describe('SessionSnapshot interface', () => {
  test('valid snapshot has all required fields', () => {
    const session: SessionSnapshot = {
      id: '1',
      title: 'Test',
      model: 'gpt-4',
      status: 'ready',
      is_active: true,
      is_archived: false,
      is_failed: false,
      current_seq: 0,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    };

    expect(session.id).toBe('1');
    expect(session.title).toBe('Test');
    expect(session.model).toBe('gpt-4');
    expect(session.status).toBe('ready');
    expect(session.is_active).toBe(true);
  });

  test('optional fields are truly optional', () => {
    const session: SessionSnapshot = {
      id: '1',
      title: 'Test',
      model: 'gpt-4',
      status: 'ready',
      is_active: true,
      is_archived: false,
      is_failed: false,
      current_seq: 0,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    };

    expect(session.cwd).toBeUndefined();
    expect(session.root_session_id).toBeUndefined();
    expect(session.tag).toBeUndefined();
  });

  test('supports cwd field', () => {
    const session: SessionSnapshot = {
      id: '1',
      title: 'Test',
      model: 'gpt-4',
      cwd: '/home/user/project',
      status: 'ready',
      is_active: true,
      is_archived: false,
      is_failed: false,
      current_seq: 0,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    };

    expect(session.cwd).toBe('/home/user/project');
  });

  test('supports tag field', () => {
    const session: SessionSnapshot = {
      id: '1',
      title: 'Test',
      model: 'gpt-4',
      status: 'ready',
      is_active: true,
      is_archived: false,
      is_failed: false,
      tag: 'important',
      current_seq: 0,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    };

    expect(session.tag).toBe('important');
  });
});

// ===========================================================================
// SessionStatus type
// ===========================================================================

describe('SessionStatus type', () => {
  test('has all valid status values', () => {
    const statuses: SessionStatus[] = ['created', 'ready', 'running', 'interrupted', 'failed'];
    expect(statuses).toContain('created');
    expect(statuses).toContain('ready');
    expect(statuses).toContain('running');
    expect(statuses).toContain('interrupted');
    expect(statuses).toContain('failed');
  });
});

// ===========================================================================
// SessionEvent type
// ===========================================================================

describe('SessionEvent type', () => {
  test('created event has session', () => {
    const event: SessionEvent = {
      type: 'created',
      session: {
        id: '1', title: 'Test', model: 'gpt-4',
        status: 'created', is_active: true, is_archived: false,
        is_failed: false, current_seq: 0,
        created_at: '2026-01-01', updated_at: '2026-01-01',
      },
    };

    expect(event.type).toBe('created');
    expect(event.session.id).toBe('1');
  });

  test('updated event has session', () => {
    const event: SessionEvent = {
      type: 'updated',
      session: {
        id: '1', title: 'Updated', model: 'gpt-4',
        status: 'ready', is_active: true, is_archived: false,
        is_failed: false, current_seq: 1,
        created_at: '2026-01-01', updated_at: '2026-01-02',
      },
    };

    expect(event.type).toBe('updated');
    expect(event.session.title).toBe('Updated');
  });

  test('deleted event has session_id', () => {
    const event: SessionEvent = {
      type: 'deleted',
      session_id: '1',
    };

    expect(event.type).toBe('deleted');
    expect(event.session_id).toBe('1');
  });

  test('synced event has session_id', () => {
    const event: SessionEvent = {
      type: 'synced',
      session_id: '1',
    };

    expect(event.type).toBe('synced');
    expect(event.session_id).toBe('1');
  });
});

// ===========================================================================
// SessionStore — query helpers (no side effects)
// ===========================================================================

describe('SessionStore — query helpers', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('getAll returns empty array initially', () => {
    const sessions = store.getAll();
    expect(sessions).toEqual([]);
  });

  test('getActiveSessions returns empty array initially', () => {
    const sessions = store.getActiveSessions();
    expect(sessions).toEqual([]);
  });

  test('getActiveSession returns null initially', () => {
    const session = store.getActiveSession();
    expect(session).toBeNull();
  });

  test('searchSessions returns empty with no sessions', () => {
    const results = store.searchSessions('test');
    expect(results).toEqual([]);
  });

  test('getAll sorts by updated_at descending', () => {
    const session1: SessionSnapshot = {
      id: '1', title: 'Old', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };
    const session2: SessionSnapshot = {
      id: '2', title: 'New', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-02', updated_at: '2026-01-03',
    };

    (store as any).sessions.set('1', session1);
    (store as any).sessions.set('2', session2);

    const sessions = store.getAll();
    expect(sessions[0].title).toBe('New');
    expect(sessions[1].title).toBe('Old');
  });

  test('getActiveSessions filters archived', () => {
    const active: SessionSnapshot = {
      id: '1', title: 'Active', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };
    const archived: SessionSnapshot = {
      id: '2', title: 'Archived', model: 'gpt-4',
      status: 'ready', is_active: false, is_archived: true,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };

    (store as any).sessions.set('1', active);
    (store as any).sessions.set('2', archived);

    const activeSessions = store.getActiveSessions();
    expect(activeSessions).toHaveLength(1);
    expect(activeSessions[0].title).toBe('Active');
  });

  test('getActiveSessions filters failed', () => {
    const failed: SessionSnapshot = {
      id: '1', title: 'Failed', model: 'gpt-4',
      status: 'failed', is_active: false, is_archived: false,
      is_failed: true, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };

    (store as any).sessions.set('1', failed);

    const activeSessions = store.getActiveSessions();
    expect(activeSessions).toHaveLength(0);
  });

  test('getActiveSession returns first active or null', () => {
    const session1: SessionSnapshot = {
      id: '1', title: 'First', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };

    (store as any).sessions.set('1', session1);

    const active = store.getActiveSession();
    expect(active).not.toBeNull();
    expect(active!.title).toBe('First');
  });

  test('searchSessions matches by title', () => {
    const session: SessionSnapshot = {
      id: '1', title: 'My Test Session', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };

    (store as any).sessions.set('1', session);

    const results = store.searchSessions('test');
    expect(results).toHaveLength(1);
  });

  test('searchSessions matches by tag', () => {
    const session: SessionSnapshot = {
      id: '1', title: 'Session', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0, tag: 'important',
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };

    (store as any).sessions.set('1', session);

    const results = store.searchSessions('important');
    expect(results).toHaveLength(1);
  });

  test('searchSessions matches by model', () => {
    const session: SessionSnapshot = {
      id: '1', title: 'Session', model: 'claude-3',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };

    (store as any).sessions.set('1', session);

    const results = store.searchSessions('claude');
    expect(results).toHaveLength(1);
  });

  test('searchSessions is case insensitive', () => {
    const session: SessionSnapshot = {
      id: '1', title: 'My Test Session', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };

    (store as any).sessions.set('1', session);

    const results = store.searchSessions('TEST');
    expect(results).toHaveLength(1);
  });

  test('searchSessions returns empty when no match', () => {
    (store as any).sessions.set('1', {
      id: '1', title: 'Session A', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const results = store.searchSessions('nonexistent');
    expect(results).toEqual([]);
  });
});

// ===========================================================================
// SessionStore — on/off listeners
// ===========================================================================

describe('SessionStore — listeners', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('on adds listener', () => {
    const handler = jest.fn();
    store.on('created', handler);
    expect(handler).toBeDefined();
  });

  test('off removes listener', () => {
    const handler = jest.fn();
    store.on('created', handler);
    store.off('created', handler);
    expect(store).toBeDefined();
  });

  test('listener receives event data', () => {
    const handler = jest.fn();
    store.on('created', handler);

    const mockSession: SessionSnapshot = {
      id: '1', title: 'Test', model: 'gpt-4',
      status: 'created', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };

    (store as any).emit({ type: 'created', session: mockSession });
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'created',
        session: expect.objectContaining({ id: '1' }),
      })
    );
  });

  test('listener errors are caught without crashing', () => {
    const badHandler = jest.fn(() => { throw new Error('boom'); });
    store.on('created', badHandler);

    const mockSession: SessionSnapshot = {
      id: '1', title: 'Test', model: 'gpt-4',
      status: 'created', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };

    // Should not throw
    expect(() => (store as any).emit({ type: 'created', session: mockSession })).not.toThrow();
    expect(badHandler).toHaveBeenCalled();
  });
});

// ===========================================================================
// SessionStore — Persistence
// ===========================================================================

describe('SessionStore — persistence', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('persist stores sessions to localStorage', () => {
    const mockSession: SessionSnapshot = {
      id: '1', title: 'Test', model: 'gpt-4',
      status: 'created', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    };
    (store as any).sessions.set('1', mockSession);
    (store as any).persist();

    const stored = localStorage.getItem('tektos_sessions');
    expect(stored).toBeTruthy();
    const parsed = JSON.parse(stored!);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].id).toBe('1');
  });

  test('persist serializes all sessions', () => {
    (store as any).sessions.set('1', {
      id: '1', title: 'A', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });
    (store as any).sessions.set('2', {
      id: '2', title: 'B', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 5,
      created_at: '2026-01-02', updated_at: '2026-01-03',
    });
    (store as any).persist();

    const stored = localStorage.getItem('tektos_sessions');
    expect(JSON.parse(stored!)).toHaveLength(2);
  });

  test('persist handles localStorage errors gracefully', () => {
    const mockSession: SessionSnapshot = {
      id: '1', title: 'Test', model: 'gpt-4',
      status: 'created', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0, created_at: '2026-01-01', updated_at: '2026-01-01',
    };
    (store as any).sessions.set('1', mockSession);

    // Spy on console.warn
    jest.spyOn(console, 'warn').mockImplementation();

    // Store original localStorage
    const origLocalStorage = global.localStorage;

    // Make the entire localStorage throw
    Object.defineProperty(global, 'localStorage', {
      value: {
        getItem: () => { throw new Error('storage error'); },
        setItem: () => { throw new Error('storage error'); },
        removeItem: () => { throw new Error('storage error'); },
      },
      writable: true,
      configurable: true,
    });

    // Should not throw
    expect(() => (store as any).persist()).not.toThrow();
    expect(console.warn).toHaveBeenCalledWith('Failed to persist sessions to localStorage');

    // Restore original localStorage
    Object.defineProperty(global, 'localStorage', { value: origLocalStorage, writable: true, configurable: true });
    jest.restoreAllMocks();
  });

  test('loadFromStorage loads sessions', () => {
    const mockSessions = [
      {
        id: '1', title: 'Test', model: 'gpt-4',
        status: 'ready', is_active: true, is_archived: false,
        is_failed: false, current_seq: 0,
        created_at: '2026-01-01', updated_at: '2026-01-01',
      },
    ];
    localStorage.setItem('tektos_sessions', JSON.stringify(mockSessions));

    // Reload
    const freshStore = new SessionStore(mockProtocolClient);
    (freshStore as any).loadFromStorage();

    const sessions = freshStore.getAll();
    expect(sessions).toHaveLength(1);
    expect(sessions[0].title).toBe('Test');
  });

  test('loadFromStorage handles corrupt data gracefully', () => {
    const mockConsoleWarn = jest.spyOn(console, 'warn').mockImplementation(() => {});
    localStorage.setItem('tektos_sessions', 'not json');

    // Should not throw
    expect(() => (store as any).loadFromStorage()).not.toThrow();
    expect(store.getAll()).toEqual([]);
    mockConsoleWarn.mockRestore();
  });

  test('loadFromStorage handles missing key', () => {
    localStorage.removeItem('tektos_sessions');
    expect(() => (store as any).loadFromStorage()).not.toThrow();
    expect(store.getAll()).toEqual([]);
  });
});

// ===========================================================================
// SessionStore — CRUD operations (mocked fetch)
// ===========================================================================

describe('SessionStore — createSession', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('createSession calls POST /api/sessions', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 's1', title: 'My Session', model: 'qwen3.6:35b', status: 'created', cwd: '/home' }),
    });

    const session = await store.createSession({ model: 'qwen3.6:35b', cwd: '/home' });

    expect(session.id).toBe('s1');
    expect(session.title).toBe('My Session');
    expect(session.model).toBe('qwen3.6:35b');
    expect(session.cwd).toBe('/home');
    expect(session.status).toBe('created');
    expect(session.is_active).toBe(false);
    expect(session.current_seq).toBe(0);
  });

  test('createSession adds session to store', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 's1', title: 'My Session', model: 'gpt-4', status: 'created' }),
    });

    await store.createSession();

    const all = store.getAll();
    expect(all).toHaveLength(1);
    expect(all[0].id).toBe('s1');
  });

  test('createSession emits created event', async () => {
    const handler = jest.fn();
    store.on('created', handler);

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 's1', title: 'My Session', model: 'gpt-4', status: 'created' }),
    });

    await store.createSession();

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler.mock.calls[0][0].type).toBe('created');
  });

  test('createSession persists to localStorage', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 's1', title: 'My Session', model: 'gpt-4', status: 'created' }),
    });

    await store.createSession();

    const stored = localStorage.getItem('tektos_sessions');
    expect(stored).toBeTruthy();
    expect(JSON.parse(stored!)).toHaveLength(1);
  });

  test('createSession sets session id on protocol client', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 's1', title: 'My Session', model: 'gpt-4', status: 'created' }),
    });

    await store.createSession();

    expect(mockProtocolClient.setSessionId).toHaveBeenCalledWith('s1');
  });

  test('createSession uses defaults when response omits fields', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 's1' }),
    });

    const session = await store.createSession();

    expect(session.title).toBe('New Session');
    expect(session.model).toBe('default');
    expect(session.status).toBe(undefined); // response didn't provide it
  });

  test('createSession throws on API failure', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await expect(store.createSession()).rejects.toThrow('Failed to create session');
  });
});

// ===========================================================================
// SessionStore — getSessions
// ===========================================================================

describe('SessionStore — getSessions', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('getSessions calls GET /api/sessions', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sessions: [{ id: 's1', title: 'A', model: 'gpt-4', status: 'ready', is_active: true }] }),
    });

    await store.getSessions();

    expect(fetch).toHaveBeenCalledWith('/api/sessions?');
  });

  test('getSessions normalizes and stores sessions', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sessions: [{ id: 's1', title: 'A', model: 'gpt-4', status: 'ready', is_active: true, is_archived: false, is_failed: false, current_seq: 0 }] }),
    });

    const sessions = await store.getSessions();
    expect(sessions).toHaveLength(1);
    expect(sessions[0].title).toBe('A');
    expect(sessions[0].is_archived).toBe(false);
  });

  test('getSessions passes query params', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ sessions: [] }),
    });

    await store.getSessions({ archived: true, limit: 10 });

    expect(fetch).toHaveBeenCalledWith('/api/sessions?archived=true&limit=10');
  });

  test('getSessions throws on API failure', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await expect(store.getSessions()).rejects.toThrow('Failed to fetch sessions');
  });
});

// ===========================================================================
// SessionStore — getSession
// ===========================================================================

describe('SessionStore — getSession', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('getSession returns cached session', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Cached', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    const session = await store.getSession('s1');
    expect(session!.title).toBe('Cached');
    expect(fetch).not.toHaveBeenCalled();
  });

  test('getSession fetches from API when not cached', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 's1', title: 'Fetched', model: 'gpt-4',
        status: 'ready', is_active: false, is_archived: false,
        is_failed: false, current_seq: 0,
      }),
    });

    const session = await store.getSession('s1');
    expect(session).not.toBeNull();
    expect(session!.title).toBe('Fetched');
    expect(session).toBe(store.getAll()[0]);
  });

  test('getSession returns null on 404', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    const session = await store.getSession('nonexistent');
    expect(session).toBeNull();
  });

  test('getSession stores fetched result in cache', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 's1', title: 'Fetched', model: 'gpt-4',
        status: 'ready', is_active: false, is_archived: false,
        is_failed: false, current_seq: 0,
      }),
    });

    await store.getSession('s1');
    const cached = store.getAll();
    expect(cached).toHaveLength(1);
    expect(cached[0].id).toBe('s1');
  });
});

// ===========================================================================
// SessionStore — renameSession
// ===========================================================================

describe('SessionStore — renameSession', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('renameSession calls PATCH endpoint', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Old', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.renameSession('s1', 'New Title');

    expect(fetch).toHaveBeenCalledWith('/api/sessions/s1', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'New Title' }),
    });
  });

  test('renameSession updates title in store', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Old', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.renameSession('s1', 'New Title');

    const session = store.getAll()[0];
    expect(session.title).toBe('New Title');
  });

  test('renameSession emits updated event', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Old', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const handler = jest.fn();
    store.on('updated', handler);
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.renameSession('s1', 'New Title');

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler.mock.calls[0][0].type).toBe('updated');
    expect(handler.mock.calls[0][0].session.title).toBe('New Title');
  });

  test('renameSession persists', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Old', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.renameSession('s1', 'New Title');

    const stored = JSON.parse(localStorage.getItem('tektos_sessions')!);
    expect(stored[0].title).toBe('New Title');
  });

  test('renameSession does nothing for missing session', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await expect(store.renameSession('nonexistent', 'Title')).resolves.toBeUndefined();
    expect(store.getAll()).toHaveLength(0);
  });
});

// ===========================================================================
// SessionStore — tagSession
// ===========================================================================

describe('SessionStore — tagSession', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('tagSession calls POST /api/sessions/:id/tag', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.tagSession('s1', 'important');

    expect(fetch).toHaveBeenCalledWith('/api/sessions/s1/tag', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag: 'important' }),
    });
  });

  test('tagSession updates tag in store', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.tagSession('s1', 'important');

    expect(store.getAll()[0].tag).toBe('important');
  });

  test('tagSession emits updated event', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const handler = jest.fn();
    store.on('updated', handler);
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.tagSession('s1', 'urgent');

    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'updated', session: expect.objectContaining({ tag: 'urgent' }) })
    );
  });

  test('tagSession persists', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.tagSession('s1', 'urgent');
    const stored = JSON.parse(localStorage.getItem('tektos_sessions')!);
    expect(stored[0].tag).toBe('urgent');
  });
});

// ===========================================================================
// SessionStore — archiveSession
// ===========================================================================

describe('SessionStore — archiveSession', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('archiveSession calls POST archive endpoint', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 5,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.archiveSession('s1');

    expect(fetch).toHaveBeenCalledWith('/api/sessions/s1/archive', { method: 'POST' });
  });

  test('archiveSession sets is_archived=true and status=created', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 5,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.archiveSession('s1');

    const session = store.getAll()[0];
    expect(session.is_archived).toBe(true);
    expect(session.status).toBe('created');
  });

  test('archiveSession emits updated event', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 5,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const handler = jest.fn();
    store.on('updated', handler);
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.archiveSession('s1');

    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'updated', session: expect.objectContaining({ is_archived: true }) })
    );
  });

  test('archiveSession persists', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 5,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.archiveSession('s1');

    const stored = JSON.parse(localStorage.getItem('tektos_sessions')!);
    expect(stored[0].is_archived).toBe(true);
  });
});

// ===========================================================================
// SessionStore — deleteSession
// ===========================================================================

describe('SessionStore — deleteSession', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('deleteSession calls DELETE endpoint', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.deleteSession('s1');

    expect(fetch).toHaveBeenCalledWith('/api/sessions/s1', { method: 'DELETE' });
  });

  test('deleteSession removes session from store', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.deleteSession('s1');

    expect(store.getAll()).toHaveLength(0);
  });

  test('deleteSession emits deleted event', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const handler = jest.fn();
    store.on('deleted', handler);
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.deleteSession('s1');

    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'deleted', session_id: 's1' })
    );
  });

  test('deleteSession persists', async () => {
    (store as any).sessions.set('s1', {
      id: 's1', title: 'Test', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true });

    await store.deleteSession('s1');

    const stored = localStorage.getItem('tektos_sessions');
    expect(stored).toBe('[]');
  });
});

// ===========================================================================
// SessionStore — forkSession
// ===========================================================================

describe('SessionStore — forkSession', () => {
  let store: SessionStore;

  function setupForkStore(): SessionStore {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    const mockProtocolClient = createMockProtocolClient();
    const s = new SessionStore(mockProtocolClient);
    return s;
  }

  test('forkSession calls POST fork endpoint', async () => {
    store = setupForkStore();
    const mockResponse = {
      ok: true,
      json: async () => ({ id: 's2', parent_title: 'Parent', model: 'gpt-4', status: 'created' }),
    };
    (global.fetch as jest.Mock).mockResolvedValueOnce(mockResponse);
    await store.forkSession('s1');
    expect(fetch).toHaveBeenCalledWith('/api/sessions/s1/fork', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
  });

  test('forkSession creates new session with root_session_id', async () => {
    store = setupForkStore();
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ id: 's2', parent_title: 'Parent', model: 'gpt-4', status: 'created' }),
      })
    );
    await store.forkSession('s1');
    const sessions = store.getAll();
    expect(sessions).toHaveLength(1);
    expect(sessions[0].id).toBe('s2');
    expect(sessions[0].root_session_id).toBe('s1');
    expect(sessions[0].title).toBe('Fork of Parent');
    expect(sessions[0].current_seq).toBe(0);
    (global.fetch as jest.Mock).mockRestore();
  });

  test('forkSession emits created event', async () => {
    store = setupForkStore();
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ id: 's2', parent_title: 'Parent', model: 'gpt-4', status: 'created' }),
      })
    );
    const handler = jest.fn();
    store.on('created', handler);
    await store.forkSession('s1');
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'created', session: expect.objectContaining({ root_session_id: 's1' }) })
    );
    (global.fetch as jest.Mock).mockRestore();
  });

  test('forkSession uses provided model option', async () => {
    store = setupForkStore();
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ id: 's2', parent_title: 'Parent', model: 'claude-3', status: 'created' }),
      })
    );
    await store.forkSession('s1', { model: 'claude-3' });
    const sessions = store.getAll();
    expect(sessions[0].model).toBe('claude-3');
    (global.fetch as jest.Mock).mockRestore();
  });

  test('forkSession throws on API failure', async () => {
    store = setupForkStore();
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({ ok: false, status: 500 })
    );
    await expect(store.forkSession('s1')).rejects.toThrow('Failed to fork session: 500');
    (global.fetch as jest.Mock).mockRestore();
  });

  test('forkSession persists', async () => {
    store = setupForkStore();
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({ id: 's2', parent_title: 'Parent', model: 'gpt-4', status: 'created' }),
      })
    );
    await store.forkSession('s1');
    const stored = localStorage.getItem('tektos_sessions');
    expect(JSON.parse(stored!)).toHaveLength(1);
    expect(JSON.parse(stored!)[0].root_session_id).toBe('s1');
    (global.fetch as jest.Mock).mockRestore();
  });
});

// ===========================================================================
// SessionStore — normalizeSession
// ===========================================================================

describe('SessionStore — normalizeSession', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('sets defaults for missing fields', () => {
    const raw = { id: '1', title: 'Test', model: 'gpt-4', status: 'ready' };
    const normalized = (store as any).normalizeSession(raw);

    expect(normalized.is_active).toBe(false);
    expect(normalized.is_archived).toBe(false);
    expect(normalized.is_failed).toBe(false);
    expect(normalized.current_seq).toBe(0);
  });

  test('preserves provided values', () => {
    const raw = {
      id: '1', title: 'Test', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: true,
      is_failed: true, current_seq: 42, tag: 'x',
      root_session_id: 'parent-1', cwd: '/home',
      created_at: '2026-01-01', updated_at: '2026-01-02',
    };
    const normalized = (store as any).normalizeSession(raw);

    expect(normalized.id).toBe('1');
    expect(normalized.is_active).toBe(true);
    expect(normalized.is_archived).toBe(true);
    expect(normalized.is_failed).toBe(true);
    expect(normalized.current_seq).toBe(42);
    expect(normalized.tag).toBe('x');
    expect(normalized.root_session_id).toBe('parent-1');
    expect(normalized.cwd).toBe('/home');
  });

  test('defaults title to "New Session"', () => {
    const raw = { id: '1', model: 'gpt-4', status: 'ready' };
    const normalized = (store as any).normalizeSession(raw);

    expect(normalized.title).toBe('New Session');
  });

  test('defaults model to "default"', () => {
    const raw = { id: '1', title: 'Test', status: 'ready' };
    const normalized = (store as any).normalizeSession(raw);

    expect(normalized.model).toBe('default');
  });

  test('defaults current_seq to 0', () => {
    const raw = { id: '1', title: 'Test', model: 'gpt-4', status: 'ready' };
    const normalized = (store as any).normalizeSession(raw);

    expect(normalized.current_seq).toBe(0);
  });
});

// ===========================================================================
// SessionStore — Error handling
// ===========================================================================

describe('SessionStore — error handling', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient>;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('createSession throws on API failure', async () => {
    (global as any).fetch = jest.fn().mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await expect(store.createSession()).rejects.toThrow('Failed to create session');
  });

  test('getSessions throws on API failure', async () => {
    (global as any).fetch = jest.fn().mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await expect(store.getSessions()).rejects.toThrow('Failed to fetch sessions');
  });

  test('getSession returns null on 404', async () => {
    (global as any).fetch = jest.fn().mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    const session = await store.getSession('nonexistent');
    expect(session).toBeNull();
  });

  test('forkSession throws on API failure', async () => {
    (global as any).fetch = jest.fn().mockResolvedValueOnce({
      ok: false,
      status: 500,
    });

    await expect(store.forkSession('1')).rejects.toThrow('Failed to fork session');
  });
});

// ===========================================================================
// SessionStore — protocol event handlers
// ===========================================================================

describe('SessionStore — protocol event handlers', () => {
  let mockProtocolClient: jest.Mocked<ProtocolClient> & { _trigger: (event: string, envelope: WSEnvelopeClient) => void };
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    mockProtocolClient = createMockProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

  test('SESSION_CREATED handler creates session from envelope', () => {
    const handler = jest.fn();
    store.on('created', handler);

    mockProtocolClient._trigger(EventType.SESSION_CREATED,
      makeEnvelope('ws-s1', { message: 'From WS', model: 'qwen3.6' })
    );

    expect(store.getAll()).toHaveLength(1);
    const session = store.getAll()[0];
    expect(session.id).toBe('ws-s1');
    expect(session.title).toBe('From WS');
    expect(session.model).toBe('qwen3.6');
    expect(session.status).toBe('created');
    expect(handler).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'created', session: expect.objectContaining({ id: 'ws-s1' }) })
    );
  });

  test('SESSION_CREATED uses defaults for missing payload fields', () => {
    mockProtocolClient._trigger(EventType.SESSION_CREATED,
      makeEnvelope('ws-s2', {})
    );

    const session = store.getAll()[0];
    expect(session.title).toBe('New Session'); // message undefined → "New Session" fallback
    expect(session.model).toBe('default');
  });

  test('SESSION_READY updates existing session', () => {
    (store as any).sessions.set('ws-r1', {
      id: 'ws-r1', title: 'Readying', model: 'gpt-4',
      status: 'created', is_active: false, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const handler = jest.fn();
    store.on('updated', handler);

    mockProtocolClient._trigger(EventType.SESSION_READY,
      makeEnvelope('ws-r1', { since_seq: 42 })
    );

    const session = store.getAll()[0];
    expect(session.status).toBe('ready');
    expect(session.is_active).toBe(true);
    expect(session.current_seq).toBe(42);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  test('SESSION_READY does nothing for unknown session', () => {
    mockProtocolClient._trigger(EventType.SESSION_READY,
      makeEnvelope('unknown', {})
    );

    expect(store.getAll()).toHaveLength(0);
  });

  test('SESSION_UPDATED mutates session fields from envelope payload', () => {
    (store as any).sessions.set('ws-u1', {
      id: 'ws-u1', title: 'Old', model: 'gpt-4',
      status: 'ready', is_active: true, is_archived: false,
      is_failed: false, current_seq: 5,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const handler = jest.fn();
    store.on('updated', handler);

    mockProtocolClient._trigger(EventType.SESSION_UPDATED,
      makeEnvelope('ws-u1', { status: 'running', title: 'New Title' })
    );

    const session = store.getAll()[0];
    expect(session.status).toBe('running');
    expect(session.title).toBe('New Title');
    expect(handler).toHaveBeenCalled();
  });

  test('SESSION_FAILED sets failed state', () => {
    (store as any).sessions.set('ws-f1', {
      id: 'ws-f1', title: 'Running', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 10,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const handler = jest.fn();
    store.on('updated', handler);

    mockProtocolClient._trigger(EventType.SESSION_FAILED,
      makeEnvelope('ws-f1', {})
    );

    const session = store.getAll()[0];
    expect(session.status).toBe('failed');
    expect(session.is_failed).toBe(true);
    expect(session.is_active).toBe(false);
    expect(handler).toHaveBeenCalled();
  });

  test('ASSISTANT_DELTA updates current_seq', () => {
    (store as any).sessions.set('ws-d1', {
      id: 'ws-d1', title: 'Delta', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    const handler = jest.fn();
    store.on('updated', handler);

    mockProtocolClient._trigger(EventType.ASSISTANT_DELTA,
      makeEnvelope('ws-d1', { message: 'partial' }, 99)
    );

    const session = store.getAll()[0];
    expect(session.current_seq).toBe(99);
    expect(handler).toHaveBeenCalled();
  });

  test('ASSISTANT_DELTA preserves seq when envelope has none', () => {
    (store as any).sessions.set('ws-d2', {
      id: 'ws-d2', title: 'Delta', model: 'gpt-4',
      status: 'running', is_active: true, is_archived: false,
      is_failed: false, current_seq: 42,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    // Build envelope without seq field (undefined, not 0)
    const envelope: WSEnvelopeClient = {
      session_id: 'ws-d2',
      event_type: 'assistant.delta',
      payload: { message: 'partial' },
      seq: undefined,
      protocol_version: '1.0',
      timestamp: new Date().toISOString(),
    };
    mockProtocolClient._trigger(EventType.ASSISTANT_DELTA, envelope);

    const session = store.getAll()[0];
    expect(session.current_seq).toBe(42); // preserved old value
  });

  test('all protocol handlers persist to localStorage', () => {
    (store as any).sessions.set('ws-p1', {
      id: 'ws-p1', title: 'Persist', model: 'gpt-4',
      status: 'created', is_active: false, is_archived: false,
      is_failed: false, current_seq: 0,
      created_at: '2026-01-01', updated_at: '2026-01-01',
    });

    mockProtocolClient._trigger(EventType.SESSION_READY,
      makeEnvelope('ws-p1', { since_seq: 5 })
    );

    const stored = localStorage.getItem('tektos_sessions');
    expect(stored).toBeTruthy();
    const parsed = JSON.parse(stored!);
    expect(parsed[0].is_active).toBe(true);
  });
});
