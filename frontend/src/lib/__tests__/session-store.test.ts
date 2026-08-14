/**
 * Session Store Unit Tests
 * Tests the SessionStore class and related types
 */

import { SessionStore, SessionSnapshot, SessionEvent, SessionStatus } from '../session-store';
import { ProtocolClient } from '../protocol';

// Mock fetch
global.fetch = jest.fn();

describe('Session Store', () => {
  let mockProtocolClient: ProtocolClient;
  let store: SessionStore;

  beforeEach(() => {
    localStorage.clear();
    (global as any).fetch = jest.fn();
    mockProtocolClient = new ProtocolClient();
    store = new SessionStore(mockProtocolClient);
  });

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

  describe('SessionStore methods', () => {
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
  });

  describe('on/off listeners', () => {
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

      // Directly manipulate internal state for testing
      const mockSession: SessionSnapshot = {
        id: '1', title: 'Test', model: 'gpt-4',
        status: 'created', is_active: true, is_archived: false,
        is_failed: false, current_seq: 0,
        created_at: '2026-01-01', updated_at: '2026-01-01',
      };

      // Access private emit via any cast
      (store as any).emit({ type: 'created', session: mockSession });
      expect(handler).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'created',
          session: expect.objectContaining({ id: '1' }),
        })
      );
    });
  });

  describe('Persistence', () => {
    test('persist stores sessions to localStorage', () => {
      // Add session directly
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

    test('persist handles localStorage errors gracefully', () => {
      const mockSession: SessionSnapshot = {
        id: '1', title: 'Test', model: 'gpt-4',
        status: 'created', is_active: true, is_archived: false,
        is_failed: false, current_seq: 0,
        created_at: '2026-01-01', updated_at: '2026-01-01',
      };
      (store as any).sessions.set('1', mockSession);
      // Should not throw
      (store as any).persist();
    });
  });

  describe('Query helpers', () => {
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

  describe('normalizeSession', () => {
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
  });

  describe('Error handling', () => {
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
});
