/**
 * Tektos-Ultima v1 — Protocol Client
 *
 * Connects to the FastAPI backend via normalized WebSocket protocol.
 * Handles envelope serialization, reconnection, and event dispatching.
 *
 * Exemplar pattern: Event-driven architecture with typed callbacks.
 */

import type { WSEnvelope, EventType, WSEventData } from "../../../src/tektos/protocol/envelope";

// ---------------------------------------------------------------------------
// Type definitions (mirrors backend protocol)
// ---------------------------------------------------------------------------

export interface WSEnvelopeClient {
  session_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  seq?: number;
  protocol_version: string;
  timestamp?: string;
}

export interface WSPromptMessage {
  type: "prompt";
  session_id: string;
  content: string;
  model?: string;
  cwd?: string;
  /** Optional: continue from a specific seq for resumable prompts */
  from_seq?: number;
}

export interface WSInterruptMessage {
  type: "interrupt";
  session_id: string;
}

export interface WSResumeMessage {
  type: "resume";
  session_id: string;
  from_seq: number;
}

export type WSOutgoing = WSPromptMessage | WSInterruptMessage | WSResumeMessage;

// ---------------------------------------------------------------------------
// Client state
// ---------------------------------------------------------------------------

export type ConnectionState = "disconnected" | "connecting" | "connected" | "reconnecting";

export interface ConnectionStateChange {
  state: ConnectionState;
  error?: string | null;
}

// ---------------------------------------------------------------------------
// Event handler types
// ---------------------------------------------------------------------------

export type EventHandler = (envelope: WSEnvelopeClient) => void;
export type ErrorHandler = (error: Error) => void;
export type StateHandler = (state: ConnectionStateChange) => void;

// ---------------------------------------------------------------------------
// ProtocolClient — main connection manager
// ---------------------------------------------------------------------------

export class ProtocolClient {
  private ws: WebSocket | null = null;
  private host: string;
  private port: number;
  private protocol: string;
  private handlers = new Map<EventType, Set<EventHandler>>();
  private errorHandlers = new Set<ErrorHandler>();
  private stateHandlers = new Set<StateHandler>();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  private state: ConnectionState = "disconnected";
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private lastPong: number = 0;
  private lastSessionId: string = "";

  constructor(options: {
    host?: string;
    port?: number;
    protocol?: string;
  } = {}) {
    this.host = options.host ?? "localhost";
    this.port = options.port ?? 8020;
    this.protocol = options.protocol ?? (typeof window !== "undefined" && window.location.protocol === "https:" ? "wss" : "ws");
  }

  private buildWsUrl(sessionId: string): string {
    return `${this.protocol}://${this.host}:${this.port}/ws/${sessionId}`;
  }

  // -----------------------------------------------------------------------
  // Connection lifecycle
  // -----------------------------------------------------------------------

  connect(): void {
    if (!this.lastSessionId) {
      // No session ID yet — skip WebSocket connection
      this.setState("disconnected");
      return;
    }

    if (this.ws && this.ws.readyState <= WebSocket.OPEN) {
      return; // Already connected or connecting
    }

    this.setState("connecting");
    this.reconnectAttempts++;

    try {
      const wsUrl = this.buildWsUrl(this.lastSessionId);
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000; // Reset backoff
        this.setState("connected");
        this.startHeartbeat();
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const envelope: WSEnvelopeClient = JSON.parse(event.data);
          this.dispatch(envelope);
        } catch (err) {
          this.onError(new Error("Failed to parse WebSocket message: " + err));
        }
      };

      this.ws.onclose = (event: CloseEvent) => {
        this.stopHeartbeat();
        this.setState("disconnected", event.reason || "Connection closed");

        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        this.setState("disconnected", "WebSocket error");
      };
    } catch (err) {
      this.onError(new Error("Failed to create WebSocket connection: " + err));
    }
  }

  /** Called when session ID changes — reconnect with new session */
  reconnect(): void {
    this.disconnect();
    this.connect();
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, "Client disconnect");
      this.ws = null;
    }
    this.stopHeartbeat();
    this.setState("disconnected");
  }

  // -----------------------------------------------------------------------
  // Messaging
  // -----------------------------------------------------------------------

  sendPrompt(message: string, options?: { model?: string; cwd?: string }): void {
    const envelope: WSOutgoing = {
      type: "prompt",
      session_id: options?.model ? `${this.lastSessionId}-${Date.now()}` : this.lastSessionId,
      prompt: message,
      model: options?.model,
      cwd: options?.cwd,
    };
    this.ws?.send(JSON.stringify(envelope));
  }

  sendInterrupt(): void {
    if (!this.lastSessionId) return;
    const envelope: WSOutgoing = {
      type: "interrupt",
      session_id: this.lastSessionId,
    };
    this.ws?.send(JSON.stringify(envelope));
  }

  sendResume(fromSeq: number): void {
    if (!this.lastSessionId) return;
    const envelope: WSOutgoing = {
      type: "resume",
      session_id: this.lastSessionId,
      from_seq: fromSeq,
    };
    this.ws?.send(JSON.stringify(envelope));
  }

  private lastSessionId = "";
  setSessionId(id: string): void {
    this.lastSessionId = id;
  }

  // -----------------------------------------------------------------------
  // Event handling
  // -----------------------------------------------------------------------

  on(eventType: EventType | "*", handler: EventHandler): void {
    const key = eventType === "*" ? "*" : eventType;
    if (!this.handlers.has(key)) {
      this.handlers.set(key, new Set());
    }
    this.handlers.get(key)!.add(handler);
  }

  off(eventType: EventType | "*", handler: EventHandler): void {
    const key = eventType === "*" ? "*" : eventType;
    this.handlers.get(key)?.delete(handler);
    if (this.handlers.get(key)?.size === 0) {
      this.handlers.delete(key);
    }
  }

  onError(handler: ErrorHandler): void {
    this.errorHandlers.add(handler);
  }

  offError(handler: ErrorHandler): void {
    this.errorHandlers.delete(handler);
  }

  onStateChange(handler: StateHandler): void {
    this.stateHandlers.add(handler);
  }

  offStateChange(handler: StateHandler): void {
    this.stateHandlers.delete(handler);
  }

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  private dispatch(envelope: WSEnvelopeClient): void {
    // Update session ID if received
    this.lastSessionId = envelope.session_id;

    // Dispatch to specific event handler
    const specificHandlers = this.handlers.get(envelope.event_type as EventType);
    if (specificHandlers) {
      for (const handler of specificHandlers) {
        try {
          handler(envelope);
        } catch (err) {
          this.onError(new Error("Event handler error: " + err));
        }
      }
    }

    // Dispatch to wildcard handler
    const wildcardHandlers = this.handlers.get("*");
    if (wildcardHandlers) {
      for (const handler of wildcardHandlers) {
        try {
          handler(envelope);
        } catch (err) {
          this.onError(new Error("Wildcard handler error: " + err));
        }
      }
    }
  }

  private setState(state: ConnectionState, error?: string | null): void {
    this.state = state;
    for (const handler of this.stateHandlers) {
      handler({ state, error: error ?? null });
    }
  }

  private onError(error: Error): void {
    for (const handler of this.errorHandlers) {
      try {
        handler(error);
      } catch (err) {
        console.error("Error handler threw:", err);
      }
    }
  }

  private scheduleReconnect(): void {
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectDelay = Math.min(delay, 30000); // Max 30s backoff
    this.setState("reconnecting", `Reconnecting in ${Math.round(delay / 1000)}s...`);

    setTimeout(() => {
      this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.lastPong = Date.now();
    this.heartbeatInterval = setInterval(() => {
      const elapsed = Date.now() - this.lastPong;
      if (elapsed > 15000) {
        // No pong for 15s — consider connection dead
        this.ws?.close(4000, "Heartbeat timeout");
      } else {
        this.ws?.send(JSON.stringify({ type: "ping" }));
      }
    }, 10000); // Ping every 10s
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }
}

// ---------------------------------------------------------------------------
// Event types (mirrors backend)
// ---------------------------------------------------------------------------

export const EventType = {
  SESSION_CREATED: "session.created",
  SESSION_READY: "session.ready",
  SESSION_UPDATED: "session.updated",
  ASSISTANT_DELTA: "assistant.delta",
  ASSISTANT_COMPLETED: "assistant.completed",
  TOOL_STARTED: "tool.started",
  TOOL_DELTA: "tool.delta",
  TOOL_COMPLETED: "tool.completed",
  TOOL_PERMISSION_REQUIRED: "tool.permission.required",
  SYSTEM_MESSAGE: "system.message",
  SESSION_INTERRUPTED: "session.interrupted",
  SESSION_FAILED: "session.failed",
  SELF_IMPROVEMENT_TICK: "self_improvement.tick",
  RESOURCE_WARNING: "resource.warning",
} as const;

export type EventType = (typeof EventType)[keyof typeof EventType];
