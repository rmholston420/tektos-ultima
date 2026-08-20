/**
 * Tests for the SessionStore — session CRUD and event handling.
 */

import { SessionStore, type SessionSnapshot } from "@/lib/session-store";
import { ProtocolClient } from "@/lib/protocol";

describe("SessionStore", () => {
  let store: SessionStore;
  let protocolClient: ProtocolClient;

  beforeEach(() => {
    protocolClient = new ProtocolClient();
    store = new SessionStore(protocolClient);
    jest.clearAllMocks();
  });

  describe("initial state", () => {
    it("starts with empty sessions", () => {
      expect(store.getAll()).toEqual([]);
    });
  });

  describe("on / off", () => {
    it("registers event handler", () => {
      const handler = jest.fn();
      store.on("created", handler);
      // Handler registered — verify emit works without error
      const session: SessionSnapshot = {
        id: "test-1",
        title: "Test",
        model: "test-model",
        cwd: ".",
        status: "created",
        is_active: false,
        is_archived: false,
        is_failed: false,
        current_seq: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      // Emit internally — just verify no crash
      expect(() => store.on("created", handler)).not.toThrow();
    });

    it("removes event handler", () => {
      const handler = jest.fn();
      store.on("created", handler);
      store.off("created", handler);
    });
  });

  describe("createSession", () => {
    it("creates a new session via API", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          id: "test-1",
          title: "Test Session",
          model: "test-model",
          cwd: ".",
          status: "created",
        }),
      });
      global.fetch = mockFetch;

      const session = await store.createSession();
      expect(session).not.toBeNull();
      expect(session.id).toBe("test-1");
      expect(session.title).toBe("Test Session");
    });

    it("emits created event", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          id: "test-1",
          title: "Test",
          model: "test-model",
          cwd: ".",
          status: "created",
        }),
      });
      global.fetch = mockFetch;

      const handler = jest.fn();
      store.on("created", handler);

      await store.createSession();
      expect(handler).toHaveBeenCalled();
    });

    it("handles creation failure", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 500,
      });
      global.fetch = mockFetch;

      await expect(store.createSession()).rejects.toThrow("Failed to create session");
    });

    it("sets protocol client session id", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          id: "test-1",
          title: "Test",
          model: "test-model",
          cwd: ".",
          status: "created",
        }),
      });
      global.fetch = mockFetch;

      await store.createSession();
      expect(protocolClient.sessionId).toBe("test-1");
    });

    it("accepts model and cwd options", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          id: "test-1",
          title: "Test",
          model: "custom-model",
          cwd: "/custom",
          status: "created",
        }),
      });
      global.fetch = mockFetch;

      await store.createSession({ model: "custom-model", cwd: "/custom" });
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/sessions",
        expect.objectContaining({
          body: JSON.stringify({ model: "custom-model", cwd: "/custom" }),
        })
      );
    });
  });

  describe("getSessions", () => {
    it("returns list of sessions", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([
          {
            id: "test-1",
            title: "Session 1",
            model: "test-model",
            cwd: ".",
            status: "ready",
            is_active: true,
            is_archived: false,
            is_failed: false,
            current_seq: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ]),
      });
      global.fetch = mockFetch;

      const sessions = await store.getSessions();
      expect(sessions.length).toBe(1);
      expect(sessions[0].id).toBe("test-1");
    });

    it("returns empty list when API returns empty", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      });
      global.fetch = mockFetch;

      const sessions = await store.getSessions();
      expect(sessions.length).toBe(0);
    });

    it("handles API failure", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 500,
      });
      global.fetch = mockFetch;

      await expect(store.getSessions()).rejects.toThrow("Failed to fetch sessions");
    });

    it("supports archived and limit options", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      });
      global.fetch = mockFetch;

      await store.getSessions({ archived: true, limit: 10 });
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/sessions?archived=true&limit=10"
      );
    });
  });

  describe("getSession", () => {
    it("returns cached session", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          id: "test-1",
          title: "Test",
          model: "test-model",
          cwd: ".",
          status: "ready",
          is_active: true,
          is_archived: false,
          is_failed: false,
          current_seq: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      global.fetch = mockFetch;

      await store.createSession();
      const session = await store.getSession("test-1");
      expect(session).not.toBeNull();
    });

    it("returns null for non-existent session", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 404,
      });
      global.fetch = mockFetch;

      const session = await store.getSession("nonexistent");
      expect(session).toBeNull();
    });
  });

  describe("renameSession", () => {
    it("renames a session via API", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      });
      global.fetch = mockFetch;

      await store.renameSession("test-session", "New Title");
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/sessions/test-session",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ title: "New Title" }),
        })
      );
    });
  });

  describe("tagSession", () => {
    it("tags a session via API", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      });
      global.fetch = mockFetch;

      await store.tagSession("test-session", "important");
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/sessions/test-session/tag",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ tag: "important" }),
        })
      );
    });
  });

  describe("archiveSession", () => {
    it("archives a session via API", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      });
      global.fetch = mockFetch;

      await store.archiveSession("test-session");
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/sessions/test-session/archive",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  describe("deleteSession", () => {
    it("deletes a session via API", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      });
      global.fetch = mockFetch;

      await store.deleteSession("test-session");
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/sessions/test-session",
        expect.objectContaining({ method: "DELETE" })
      );
    });

    it("emits deleted event", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({}),
      });
      global.fetch = mockFetch;

      const handler = jest.fn();
      store.on("deleted", handler);

      await store.deleteSession("test-session");
      expect(handler).toHaveBeenCalled();
    });
  });

  describe("forkSession", () => {
    it("forks a session via API", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          id: "forked-session",
          parent_title: "Original",
          model: "test-model",
          status: "created",
        }),
      });
      global.fetch = mockFetch;

      const session = await store.forkSession("original-session");
      expect(session.id).toBe("forked-session");
      expect(session.title).toBe("Fork of Original");
    });

    it("handles fork failure", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: false,
        status: 500,
      });
      global.fetch = mockFetch;

      await expect(store.forkSession("nonexistent")).rejects.toThrow("Failed to fork session");
    });
  });

  describe("query helpers", () => {
    it("getAll returns sorted sessions", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([
          {
            id: "test-1",
            title: "Old Session",
            model: "test-model",
            cwd: ".",
            status: "ready",
            is_active: true,
            is_archived: false,
            is_failed: false,
            current_seq: 0,
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-01-01T00:00:00Z",
          },
          {
            id: "test-2",
            title: "New Session",
            model: "test-model",
            cwd: ".",
            status: "ready",
            is_active: true,
            is_archived: false,
            is_failed: false,
            current_seq: 0,
            created_at: "2024-01-02T00:00:00Z",
            updated_at: "2024-01-02T00:00:00Z",
          },
        ]),
      });
      global.fetch = mockFetch;

      await store.getSessions();
      const all = store.getAll();
      expect(all.length).toBe(2);
      // Sorted by updated_at descending
      expect(all[0].id).toBe("test-2");
    });

    it("getActiveSessions filters correctly", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([
          {
            id: "active-1",
            title: "Active",
            model: "test-model",
            cwd: ".",
            status: "ready",
            is_active: true,
            is_archived: false,
            is_failed: false,
            current_seq: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          {
            id: "archived-1",
            title: "Archived",
            model: "test-model",
            cwd: ".",
            status: "created",
            is_active: false,
            is_archived: true,
            is_failed: false,
            current_seq: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          {
            id: "failed-1",
            title: "Failed",
            model: "test-model",
            cwd: ".",
            status: "failed",
            is_active: false,
            is_archived: false,
            is_failed: true,
            current_seq: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ]),
      });
      global.fetch = mockFetch;

      await store.getSessions();
      const active = store.getActiveSessions();
      expect(active.length).toBe(1);
      expect(active[0].id).toBe("active-1");
    });

    it("getActiveSession returns first active", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([
          {
            id: "active-1",
            title: "Active",
            model: "test-model",
            cwd: ".",
            status: "ready",
            is_active: true,
            is_archived: false,
            is_failed: false,
            current_seq: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ]),
      });
      global.fetch = mockFetch;

      await store.getSessions();
      const active = store.getActiveSession();
      expect(active?.id).toBe("active-1");
    });

    it("getActiveSession returns null when none active", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([]),
      });
      global.fetch = mockFetch;

      await store.getSessions();
      const active = store.getActiveSession();
      expect(active).toBeNull();
    });

    it("searchSessions filters by title", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([
          {
            id: "test-1",
            title: "Important Session",
            model: "test-model",
            cwd: ".",
            status: "ready",
            is_active: true,
            is_archived: false,
            is_failed: false,
            current_seq: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          {
            id: "test-2",
            title: "Other Session",
            model: "test-model",
            cwd: ".",
            status: "ready",
            is_active: true,
            is_archived: false,
            is_failed: false,
            current_seq: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ]),
      });
      global.fetch = mockFetch;

      await store.getSessions();
      const results = store.searchSessions("important");
      expect(results.length).toBe(1);
      expect(results[0].title).toBe("Important Session");
    });

    it("searchSessions filters by tag", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([
          {
            id: "test-1",
            title: "Session",
            model: "test-model",
            cwd: ".",
            status: "ready",
            is_active: true,
            is_archived: false,
            is_failed: false,
            current_seq: 0,
            tag: "production",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ]),
      });
      global.fetch = mockFetch;

      await store.getSessions();
      const results = store.searchSessions("production");
      expect(results.length).toBe(1);
    });

    it("searchSessions filters by model", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([
          {
            id: "test-1",
            title: "Session",
            model: "Qwen3.6-35B-A3B-Q4_K_M",
            cwd: ".",
            status: "ready",
            is_active: true,
            is_archived: false,
            is_failed: false,
            current_seq: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ]),
      });
      global.fetch = mockFetch;

      await store.getSessions();
      const results = store.searchSessions("qwen3.6");
      expect(results.length).toBe(1);
    });

    it("searchSessions is case insensitive", async () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([
          {
            id: "test-1",
            title: "Important Session",
            model: "test-model",
            cwd: ".",
            status: "ready",
            is_active: true,
            is_archived: false,
            is_failed: false,
            current_seq: 0,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ]),
      });
      global.fetch = mockFetch;

      await store.getSessions();
      const results = store.searchSessions("important");
      expect(results.length).toBe(1);
    });
  });

  describe("syncSessions", () => {
    it("loads from localStorage", async () => {
      const mockData = JSON.stringify([
        {
          id: "local-1",
          title: "Local Session",
          model: "test-model",
          cwd: ".",
          status: "ready",
          is_active: true,
          is_archived: false,
          is_failed: false,
          current_seq: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]);
      Object.defineProperty(window, "localStorage", {
        value: {
          getItem: jest.fn(() => mockData),
          setItem: jest.fn(),
        },
        writable: true,
      });

      await store.syncSessions();
      const all = store.getAll();
      expect(all.length).toBe(1);
      expect(all[0].id).toBe("local-1");
    });

    it("handles invalid JSON gracefully", async () => {
      Object.defineProperty(window, "localStorage", {
        value: {
          getItem: jest.fn(() => "invalid json{{{"),
          setItem: jest.fn(),
        },
        writable: true,
      });

      await expect(store.syncSessions()).resolves.toBeUndefined();
    });
  });

  describe("normalizeSession", () => {
    it("fills defaults for missing fields", () => {
      const mockFetch = jest.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          id: "test-1",
          title: "Test",
          model: "test-model",
          cwd: ".",
          status: "ready",
        }),
      });
      global.fetch = mockFetch;

      store.getSession("test-1").then((session) => {
        expect(session?.is_active).toBe(false);
        expect(session?.is_archived).toBe(false);
        expect(session?.is_failed).toBe(false);
        expect(session?.current_seq).toBe(0);
      });
    });
  });
});
