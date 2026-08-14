/**
 * Tektos-Ultima v1 — Session Store
 *
 * Manages session lifecycle, persistence, and CRUD operations.
 * Uses IndexedDB for local persistence, syncs with backend REST API.
 *
 * Exemplar pattern: Single source of truth with immutable session snapshots.
 */

import { ProtocolClient, EventType } from "./protocol";
import type { WSEnvelopeClient } from "./protocol";

// ---------------------------------------------------------------------------
// Session state interface
// ---------------------------------------------------------------------------

export interface SessionSnapshot {
  id: string;
  title: string;
  model: string;
  cwd?: string;
  status: SessionStatus;
  is_active: boolean;
  is_archived: boolean;
  is_failed: boolean;
  root_session_id?: string;
  tag?: string;
  created_at: string;
  updated_at: string;
  /** Current seq for resumable replay */
  current_seq: number;
}

export type SessionStatus = "created" | "ready" | "running" | "interrupted" | "failed";

export type SessionEvent =
  | { type: "created"; session: SessionSnapshot }
  | { type: "updated"; session: SessionSnapshot }
  | { type: "deleted"; session_id: string }
  | { type: "synced"; session_id: string };

// ---------------------------------------------------------------------------
// SessionStore — centralized session management
// ---------------------------------------------------------------------------

export class SessionStore {
  private sessions = new Map<string, SessionSnapshot>();
  private listeners = new Set<(event: SessionEvent) => void>();
  private protocolClient: ProtocolClient;

  constructor(protocolClient: ProtocolClient) {
    this.protocolClient = protocolClient;
    this.setupProtocolListeners();
    this.loadFromStorage();
  }

  // ---------------------------------------------------------------------
  // CRUD operations
  // ---------------------------------------------------------------------

  async createSession(options?: { model?: string; cwd?: string }): Promise<SessionSnapshot> {
    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: options?.model,
        cwd: options?.cwd,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create session: ${response.status}`);
    }

    const data = await response.json();
    const session: SessionSnapshot = {
      id: data.id,
      title: data.title ?? "New Session",
      model: data.model ?? "default",
      cwd: data.cwd,
      status: data.status,
      is_active: false,
      is_archived: false,
      is_failed: false,
      current_seq: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    this.sessions.set(session.id, session);
    this.emit({ type: "created", session });
    this.persist();

    // Set as active session
    this.protocolClient.setSessionId(session.id);

    return session;
  }

  async getSessions(options?: { archived?: boolean; limit?: number }): Promise<SessionSnapshot[]> {
    const params = new URLSearchParams();
    if (options?.archived !== undefined) {
      params.set("archived", String(options.archived));
    }
    if (options?.limit) {
      params.set("limit", String(options.limit));
    }

    const response = await fetch(`/api/sessions?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch sessions: ${response.status}`);
    }

    const data = await response.json();
    const sessions = data.sessions.map((s: any) => this.normalizeSession(s));
    sessions.forEach((s: SessionSnapshot) => this.sessions.set(s.id, s));
    this.emit({ type: "synced", session_id: sessions[0]?.id });

    return sessions;
  }

  async getSession(sessionId: string): Promise<SessionSnapshot | null> {
    const cached = this.sessions.get(sessionId);
    if (cached) return cached;

    const response = await fetch(`/api/sessions/${sessionId}`);
    if (!response.ok) return null;

    const data = await response.json();
    const session = this.normalizeSession(data);
    this.sessions.set(sessionId, session);
    return session;
  }

  async renameSession(sessionId: string, title: string): Promise<void> {
    await fetch(`/api/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });

    const session = this.sessions.get(sessionId);
    if (session) {
      session.title = title;
      session.updated_at = new Date().toISOString();
      this.emit({ type: "updated", session });
      this.persist();
    }
  }

  async tagSession(sessionId: string, tag: string): Promise<void> {
    await fetch(`/api/sessions/${sessionId}/tag`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tag }),
    });

    const session = this.sessions.get(sessionId);
    if (session) {
      session.tag = tag;
      session.updated_at = new Date().toISOString();
      this.emit({ type: "updated", session });
      this.persist();
    }
  }

  async archiveSession(sessionId: string): Promise<void> {
    await fetch(`/api/sessions/${sessionId}/archive`, { method: "POST" });

    const session = this.sessions.get(sessionId);
    if (session) {
      session.is_archived = true;
      session.status = "created";
      session.updated_at = new Date().toISOString();
      this.emit({ type: "updated", session });
      this.persist();
    }
  }

  async deleteSession(sessionId: string): Promise<void> {
    await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
    this.sessions.delete(sessionId);
    this.emit({ type: "deleted", session_id: sessionId });
    this.persist();
  }

  async forkSession(parentId: string, options?: { model?: string }): Promise<SessionSnapshot> {
    const response = await fetch(`/api/sessions/${parentId}/fork`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: options?.model,
      }),
    });

    if (!response.ok) {
      throw new Error(`Failed to fork session: ${response.status}`);
    }

    const data = await response.json();
    const session: SessionSnapshot = {
      id: data.id,
      title: `Fork of ${data.parent_title}`,
      model: data.model ?? "default",
      root_session_id: parentId,
      status: data.status,
      is_active: false,
      is_archived: false,
      is_failed: false,
      current_seq: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    this.sessions.set(session.id, session);
    this.emit({ type: "created", session });
    this.persist();

    return session;
  }

  // ---------------------------------------------------------------------
  // Session event handling (from backend WebSocket)
  // ---------------------------------------------------------------------

  private setupProtocolListeners(): void {
    this.protocolClient.on(EventType.SESSION_CREATED, (envelope: WSEnvelopeClient) => {
      const session: SessionSnapshot = {
        id: envelope.session_id,
        title: (envelope.payload.message as string) ?? "New Session",
        model: (envelope.payload.model as string) ?? "default",
        status: "created",
        is_active: false,
        is_archived: false,
        is_failed: false,
        current_seq: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      this.sessions.set(session.id, session);
      this.emit({ type: "created", session });
      this.persist();
    });

    this.protocolClient.on(EventType.SESSION_READY, (envelope: WSEnvelopeClient) => {
      const session = this.sessions.get(envelope.session_id);
      if (session) {
        session.status = "ready";
        session.is_active = true;
        session.current_seq = (envelope.payload.since_seq as number) ?? 0;
        session.updated_at = new Date().toISOString();
        this.emit({ type: "updated", session });
        this.persist();
      }
    });

    this.protocolClient.on(EventType.SESSION_UPDATED, (envelope: WSEnvelopeClient) => {
      const session = this.sessions.get(envelope.session_id);
      if (session) {
        if (envelope.payload.status) session.status = envelope.payload.status as SessionStatus;
        if (envelope.payload.title) session.title = envelope.payload.title as string;
        session.updated_at = new Date().toISOString();
        this.emit({ type: "updated", session });
        this.persist();
      }
    });

    this.protocolClient.on(EventType.SESSION_FAILED, (envelope: WSEnvelopeClient) => {
      const session = this.sessions.get(envelope.session_id);
      if (session) {
        session.status = "failed";
        session.is_failed = true;
        session.is_active = false;
        session.updated_at = new Date().toISOString();
        this.emit({ type: "updated", session });
        this.persist();
      }
    });

    this.protocolClient.on(EventType.ASSISTANT_DELTA, (envelope: WSEnvelopeClient) => {
      const session = this.sessions.get(envelope.session_id);
      if (session) {
        session.current_seq = (envelope.seq as number) ?? session.current_seq;
        session.updated_at = new Date().toISOString();
        this.emit({ type: "updated", session });
      }
    });
  }

  // ---------------------------------------------------------------------
  // Listeners
  // ---------------------------------------------------------------------

  on(event: SessionEvent["type"], handler: (event: SessionEvent) => void): void {
    this.listeners.add(handler);
  }

  off(event: SessionEvent["type"], handler: (event: SessionEvent) => void): void {
    this.listeners.delete(handler);
  }

  private emit(event: SessionEvent): void {
    Array.from(this.listeners).forEach((listener) => {
      try { listener(event); } catch (err) { console.error("Session store listener error:", err); }
    });
  }

  // ---------------------------------------------------------------------
  // Query helpers
  // ---------------------------------------------------------------------

  getAll(): SessionSnapshot[] {
    return Array.from(this.sessions.values()).sort(
      (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
  }

  getActiveSessions(): SessionSnapshot[] {
    return this.getAll().filter((s) => !s.is_archived && !s.is_failed && s.is_active);
  }

  searchSessions(query: string): SessionSnapshot[] {
    const lower = query.toLowerCase();
    return this.getAll().filter(
      (s) =>
        s.title.toLowerCase().includes(lower) ||
        (s.tag ?? "").toLowerCase().includes(lower) ||
        s.model.toLowerCase().includes(lower)
    );
  }

  getActiveSession(): SessionSnapshot | null {
    return this.getActiveSessions()[0] ?? null;
  }

  // ---------------------------------------------------------------------
  // Persistence (IndexedDB)
  // ---------------------------------------------------------------------

  private storageKey = "tektos_sessions";

  private persist(): void {
    if (typeof window === "undefined") return;
    try {
      localStorage.setItem(this.storageKey, JSON.stringify(Array.from(this.sessions.values())));
    } catch {
      console.warn("Failed to persist sessions to localStorage");
    }
  }

  private loadFromStorage(): void {
    if (typeof window === "undefined") return;
    try {
      const data = localStorage.getItem(this.storageKey);
      if (data) {
        const sessions: SessionSnapshot[] = JSON.parse(data);
        sessions.forEach((s) => this.sessions.set(s.id, s));
      }
    } catch {
      console.warn("Failed to load sessions from localStorage");
    }
  }

  // ---------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------

  private normalizeSession(data: any): SessionSnapshot {
    return {
      id: data.id,
      title: data.title ?? "New Session",
      model: data.model ?? "default",
      cwd: data.cwd,
      status: data.status,
      is_active: data.is_active ?? false,
      is_archived: data.is_archived ?? false,
      is_failed: data.is_failed ?? false,
      root_session_id: data.root_session_id,
      tag: data.tag,
      created_at: data.created_at ?? new Date().toISOString(),
      updated_at: data.updated_at ?? new Date().toISOString(),
      current_seq: data.current_seq ?? 0,
    };
  }
}
