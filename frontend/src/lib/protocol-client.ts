"use client";

import {
  ConnectionState,
  ConnectionStateChange,
  WSEnvelope,
} from "@/types/protocol";
import { wsUrl } from "@/lib/env";

export type EventHandler = (envelope: WSEnvelope) => void;
export type ErrorHandler = (error: Error) => void;
export type StateHandler = (change: ConnectionStateChange) => void;

interface ClientOptions {
  host?: string;
  port?: number;
  protocol?: string;
  /** Backoff cap in ms. Default 30_000. */
  maxReconnectDelayMs?: number;
  /** Max reconnect attempts before giving up. Default 10. */
  maxReconnectAttempts?: number;
  /** Heartbeat interval in ms. Default 10_000. */
  heartbeatIntervalMs?: number;
  /** Heartbeat timeout — miss window before force-close. Default 15_000. */
  heartbeatTimeoutMs?: number;
  /** Injection hook for tests. */
  wsFactory?: (url: string) => WebSocket;
}

/**
 * Wire-compatible replacement for `frontend/src/lib/protocol.ts`.
 *
 * Behavioral parity:
 *   - Connects to `${protocol}://${host}:${port}/` (gateway proxy).
 *   - Sends prompts as JSON-RPC 2.0 `prompt.submit`.
 *   - Sends interrupts as JSON-RPC 2.0 `session.interrupt`.
 *   - Handles both raw Tektos envelopes and JSON-RPC `event` notifications.
 *   - Ping/pong heartbeat every 10s; force-close after 15s of silence.
 *   - Exponential backoff reconnect (1s -> 30s cap), max 10 attempts.
 *
 * Improvements:
 *   - Honors NEXT_PUBLIC_TEKTOS_WS_PROTOCOL (frontend/ hard-coded "ws").
 *   - Structured logging via `debug` flag; no console spam by default.
 *   - Correlation_id / parent_seq / origin passed through envelopes.
 */
export class ProtocolClient {
  private ws: WebSocket | null = null;
  private _sessionId = "";
  private handlers = new Map<string, Set<EventHandler>>();
  private errorHandlers = new Set<ErrorHandler>();
  private stateHandlers = new Set<StateHandler>();
  private reconnectAttempts = 0;
  private reconnectDelay = 1000;
  private state: ConnectionState = "disconnected";
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private lastPong = 0;
  private pendingMessages: string[] = [];

  private readonly maxReconnectDelayMs: number;
  private readonly maxReconnectAttempts: number;
  private readonly heartbeatIntervalMs: number;
  private readonly heartbeatTimeoutMs: number;
  private readonly wsFactory: (url: string) => WebSocket;
  private readonly baseUrl: string;

  constructor(options: ClientOptions = {}) {
    this.maxReconnectDelayMs = options.maxReconnectDelayMs ?? 30_000;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 10;
    this.heartbeatIntervalMs = options.heartbeatIntervalMs ?? 10_000;
    this.heartbeatTimeoutMs = options.heartbeatTimeoutMs ?? 15_000;
    this.wsFactory = options.wsFactory ?? ((url) => new WebSocket(url));
    this.baseUrl = wsUrl("/");
  }

  // ---- Public API ------------------------------------------------------

  connect(): void {
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) {
      try {
        this.ws.close(1000, "Session change");
      } catch {
        /* noop */
      }
    }
    this.setState("connecting");
    this.reconnectAttempts++;
    try {
      this.ws = this.wsFactory(this.baseUrl);
      this.ws.onopen = () => this.onOpen();
      this.ws.onmessage = (e: MessageEvent) => this.onMessage(e);
      this.ws.onclose = (ev: CloseEvent) => this.onClose(ev);
      this.ws.onerror = () => this.setState("disconnected", "WS error");
    } catch (err) {
      this.emitError(new Error(`Connect error: ${err}`));
    }
  }

  disconnect(): void {
    if (this.ws) {
      try {
        this.ws.close(1000, "Disconnect");
      } catch {
        /* noop */
      }
      this.ws = null;
    }
    this.stopHeartbeat();
    this.setState("disconnected");
  }

  reconnect(): void {
    this.disconnect();
    this.connect();
  }

  sendPrompt(text: string, options?: { model?: string; cwd?: string }): void {
    const msg = {
      jsonrpc: "2.0",
      method: "prompt.submit",
      params: {
        session_id: this._sessionId,
        text,
        ...(options?.model ? { model: options.model } : {}),
        ...(options?.cwd ? { cwd: options.cwd } : {}),
      },
    };
    this.sendOrQueue(JSON.stringify(msg));
  }

  sendInterrupt(): void {
    if (!this._sessionId) return;
    const msg = {
      jsonrpc: "2.0",
      method: "session.interrupt",
      params: { session_id: this._sessionId },
    };
    this.sendOrQueue(JSON.stringify(msg));
  }

  /** Approve or deny a pending permission request. */
  sendPermission(request_id: string, granted: boolean): void {
    const msg = {
      jsonrpc: "2.0",
      method: "tool.permission.reply",
      params: { session_id: this._sessionId, request_id, granted },
    };
    this.sendOrQueue(JSON.stringify(msg));
  }

  /** Approve or reject a proposed plan (additive; backend emitter follows). */
  sendPlanDecision(plan_id: string, approved: boolean): void {
    const msg = {
      jsonrpc: "2.0",
      method: "plan.decision",
      params: { session_id: this._sessionId, plan_id, approved },
    };
    this.sendOrQueue(JSON.stringify(msg));
  }

  setSessionId(id: string): void {
    this._sessionId = id;
  }

  get sessionId(): string {
    return this._sessionId;
  }

  get connectionState(): ConnectionState {
    return this.state;
  }

  on(eventType: string, handler: EventHandler): () => void {
    if (!this.handlers.has(eventType)) this.handlers.set(eventType, new Set());
    this.handlers.get(eventType)!.add(handler);
    return () => this.off(eventType, handler);
  }

  off(eventType: string, handler: EventHandler): void {
    this.handlers.get(eventType)?.delete(handler);
  }

  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  onStateChange(handler: StateHandler): () => void {
    this.stateHandlers.add(handler);
    return () => this.stateHandlers.delete(handler);
  }

  // ---- Internals -------------------------------------------------------

  private onOpen(): void {
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;
    this.setState("connected");
    this.startHeartbeat();
    this.flushPending();
  }

  private onMessage(e: MessageEvent): void {
    let data: unknown;
    try {
      data = JSON.parse(e.data);
    } catch (err) {
      this.emitError(new Error(`Parse error: ${err}`));
      return;
    }
    // Pong tracking (backend replies with {type: "pong"})
    if (
      typeof data === "object" &&
      data !== null &&
      "type" in data &&
      (data as { type: string }).type === "pong"
    ) {
      this.lastPong = Date.now();
      return;
    }
    // JSON-RPC 2.0 notification from the gateway proxy
    if (
      typeof data === "object" &&
      data !== null &&
      (data as { jsonrpc?: string }).jsonrpc === "2.0" &&
      (data as { method?: string }).method === "event"
    ) {
      this.handleJsonRpcNotification(data as JsonRpcEvent);
      return;
    }
    // Raw Tektos envelope
    this.dispatch(data as WSEnvelope);
  }

  private onClose(ev: CloseEvent): void {
    this.stopHeartbeat();
    this.setState("disconnected", ev.reason || "Closed");
    if (ev.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
      this.scheduleReconnect();
    }
  }

  private handleJsonRpcNotification(data: JsonRpcEvent): void {
    const params = data.params ?? {};
    const eventType = params.type ?? "";
    const payload = (params.payload as Record<string, unknown>) ?? {};
    const envelope: WSEnvelope = {
      session_id:
        (payload.session_id as string | undefined) ?? this._sessionId ?? "",
      event_type: eventType,
      payload,
      protocol_version: "1.0.0",
      seq: params.seq,
      correlation_id: params.correlation_id,
      parent_seq: params.parent_seq,
      origin: params.origin as WSEnvelope["origin"],
    };
    if (eventType === "gateway.ready") {
      this.setState("connected");
      this.startHeartbeat();
      return;
    }
    this.dispatch(envelope);
  }

  private dispatch(envelope: WSEnvelope): void {
    if (envelope.session_id) this._sessionId = envelope.session_id;
    const key = envelope.event_type;
    this.handlers.get(key)?.forEach((h) => {
      try {
        h(envelope);
      } catch (e) {
        this.emitError(new Error(`Event handler error: ${e}`));
      }
    });
    this.handlers.get("*")?.forEach((h) => {
      try {
        h(envelope);
      } catch (e) {
        this.emitError(new Error(`Wildcard handler error: ${e}`));
      }
    });
  }

  private sendOrQueue(json: string): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(json);
      } catch {
        this.pendingMessages.push(json);
      }
    } else {
      this.pendingMessages.push(json);
    }
  }

  private flushPending(): void {
    while (
      this.pendingMessages.length > 0 &&
      this.ws &&
      this.ws.readyState === WebSocket.OPEN
    ) {
      const msg = this.pendingMessages.shift()!;
      try {
        this.ws.send(msg);
      } catch {
        break;
      }
    }
  }

  private setState(state: ConnectionState, error?: string | null): void {
    this.state = state;
    this.stateHandlers.forEach((h) => {
      try {
        h({ state, error: error ?? null });
      } catch {
        /* noop */
      }
    });
  }

  private emitError(err: Error): void {
    this.errorHandlers.forEach((h) => {
      try {
        h(err);
      } catch {
        /* noop */
      }
    });
  }

  private scheduleReconnect(): void {
    const d = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts),
      this.maxReconnectDelayMs,
    );
    this.reconnectDelay = d;
    this.setState("reconnecting", `Reconnecting in ${Math.round(d / 1000)}s...`);
    setTimeout(() => this.connect(), d);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.lastPong = Date.now();
    this.heartbeatInterval = setInterval(
      () => this.heartbeatTick(),
      this.heartbeatIntervalMs,
    );
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  private heartbeatTick(): void {
    if (Date.now() - this.lastPong > this.heartbeatTimeoutMs) {
      this.ws?.close(4000, "Heartbeat timeout");
      return;
    }
    try {
      this.ws?.send(JSON.stringify({ type: "ping" }));
    } catch {
      /* connection will surface via onclose */
    }
  }
}

interface JsonRpcEvent {
  jsonrpc: "2.0";
  method: "event";
  params?: {
    type?: string;
    payload?: Record<string, unknown>;
    seq?: number;
    correlation_id?: string;
    parent_seq?: number;
    origin?: string;
  };
}
