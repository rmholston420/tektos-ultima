"use client";

export type EventType = "session.created" | "session.ready" | "session.updated" | "assistant.delta" | "assistant.completed" | "tool.started" | "tool.delta" | "tool.completed" | "tool.permission.required" | "system.message" | "session.interrupted" | "session.failed" | "self_improvement.tick" | "resource.warning";

export interface WSEnvelopeClient {
  session_id: string; event_type: string; payload: Record<string, unknown>; seq?: number; protocol_version: string; timestamp?: string;
}

export type ConnectionState = "disconnected" | "connecting" | "connected" | "reconnecting";
export interface ConnectionStateChange { state: ConnectionState; error?: string | null; }
export type EventHandler = (envelope: WSEnvelopeClient) => void;
export type ErrorHandler = (error: Error) => void;
export type StateHandler = (state: ConnectionStateChange) => void;

export class ProtocolClient {
  private ws: WebSocket | null = null;
  private _sessionId = "";
  private handlers = new Map<string, Set<EventHandler>>();
  private errorHandlers: ErrorHandler[] = [];
  private stateHandlers: StateHandler[] = [];
  private reconnectAttempts = 0;
  private reconnectDelay = 1000;
  private state: ConnectionState = "disconnected";
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private lastPong = 0;
  private lastPingSent = 0;
  private host = "localhost";
  private port = 8020;
  private protocol = "ws";

  constructor(options?: { host?: string; port?: number; protocol?: string }) {
    if (options?.host) this.host = options.host;
    if (options?.port) this.port = options.port;
    if (options?.protocol) this.protocol = options.protocol;
    else if (typeof window !== "undefined" && window.location.protocol === "https:") this.protocol = "wss";
  }

  private notifyError(err: Error): void {
    this.errorHandlers.forEach((h) => { try { h(err); } catch (_) { console.error("Handler threw", _); } });
  }

  connect(): void {
    // If an old WS connection is open (e.g., from a previous session), close it first
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) {
      try { this.ws.close(1000, "Session change"); } catch (_) {}
    }
    if (!this._sessionId) { this.setState("disconnected"); return; }
    this.setState("connecting");
    this.reconnectAttempts++;
    try {
      this.ws = new WebSocket(`${this.protocol}://${this.host}:${this.port}/ws/${this._sessionId}`);
      this.ws.onopen = () => { this.reconnectAttempts = 0; this.reconnectDelay = 1000; this.setState("connected"); this.startHeartbeat(); };
      this.ws.onmessage = (e: MessageEvent) => { try { this.dispatch(JSON.parse(e.data)); } catch (err) { this.notifyError(new Error("Parse error: " + err)); } };
      this.ws.onclose = (ev) => { this.stopHeartbeat(); this.setState("disconnected", ev.reason || "Closed"); if (ev.code !== 1000 && this.reconnectAttempts < 10) this.scheduleReconnect(); };
      this.ws.onerror = () => this.setState("disconnected", "WS error");
    } catch (err) { this.notifyError(new Error("Connect error: " + err)); }
  }

  disconnect(): void { if (this.ws) { this.ws.close(1000, "Disconnect"); this.ws = null; } this.stopHeartbeat(); this.setState("disconnected"); }
  reconnect(): void { this.disconnect(); this.connect(); }
  sendPrompt(message: string, options?: { model?: string; cwd?: string }): void {
    const msg: any = { type: "prompt", session_id: this._sessionId, prompt: message };
    if (options?.model) msg.model = options.model;
    if (options?.cwd) msg.cwd = options.cwd;
    this.ws?.send(JSON.stringify(msg));
  }
  sendInterrupt(): void { if (this._sessionId) this.ws?.send(JSON.stringify({ type: "interrupt", session_id: this._sessionId })); }
  sendResume(fromSeq: number): void { /* Not implemented on backend — no 'resume' message type */ }
  setSessionId(id: string): void { this._sessionId = id; }
  get sessionId(): string { return this._sessionId; }

  on(eventType: string | "*", handler: EventHandler): void {
    const key = eventType === "*" ? "*" : eventType;
    if (!this.handlers.has(key)) this.handlers.set(key, new Set());
    this.handlers.get(key)!.add(handler);
  }

  off(eventType: string | "*", handler: EventHandler): void {
    const key = eventType === "*" ? "*" : eventType;
    this.handlers.get(key)?.delete(handler);
  }

  onError(handler: ErrorHandler): void { this.errorHandlers.push(handler); }
  offError(handler: ErrorHandler): void { const i = this.errorHandlers.indexOf(handler); if (i >= 0) this.errorHandlers.splice(i, 1); }
  onStateChange(handler: StateHandler): void { this.stateHandlers.push(handler); }
  offStateChange(handler: StateHandler): void { const i = this.stateHandlers.indexOf(handler); if (i >= 0) this.stateHandlers.splice(i, 1); }

  private dispatch(envelope: WSEnvelopeClient): void {
    this._sessionId = envelope.session_id;
    const eventKey = envelope.event_type;
    const specific = this.handlers.get(eventKey);
    if (specific) specific.forEach((h) => { try { h(envelope); } catch (e) { this.notifyError(new Error("Event handler error: " + e)); } });
    const wildcard = this.handlers.get("*");
    if (wildcard) wildcard.forEach((h) => { try { h(envelope); } catch (e) { this.notifyError(new Error("Wildcard handler error: " + e)); } });
  }

  private setState(s: ConnectionState, e?: string | null): void {
    this.state = s;
    this.stateHandlers.forEach((h) => h({ state: s, error: e ?? null }));
  }

  private scheduleReconnect(): void {
    const d = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectDelay = d;
    this.setState("reconnecting", `Reconnecting in ${Math.round(d / 1000)}s...`);
    setTimeout(() => this.connect(), d);
  }

  private startHeartbeat(): void {
    this.lastPong = Date.now();
    this.lastPingSent = 0;
    this.heartbeatInterval = setInterval(() => {
      this.lastPingSent = Date.now();
      if (Date.now() - this.lastPong > 15000) this.ws?.close(4000, "Timeout");
      else this.ws?.send(JSON.stringify({ type: "ping" }));
    }, 10000);
  }

  private stopHeartbeat(): void { if (this.heartbeatInterval) { clearInterval(this.heartbeatInterval); this.heartbeatInterval = null; } }
}

export const EventType = {
  SESSION_CREATED: "session.created", SESSION_READY: "session.ready", SESSION_UPDATED: "session.updated",
  ASSISTANT_DELTA: "assistant.delta", ASSISTANT_COMPLETED: "assistant.completed",
  TOOL_STARTED: "tool.started", TOOL_DELTA: "tool.delta", TOOL_COMPLETED: "tool.completed",
  TOOL_PERMISSION_REQUIRED: "tool.permission.required", SYSTEM_MESSAGE: "system.message",
  SESSION_INTERRUPTED: "session.interrupted", SESSION_FAILED: "session.failed",
  SELF_IMPROVEMENT_TICK: "self_improvement.tick", RESOURCE_WARNING: "resource.warning",
} as const;
