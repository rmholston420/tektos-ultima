/**
 * Tektos-Ultima v1 — Nervous System Panel
 *
 * Live visualization of the nervous system: event bus subscriptions and
 * active session state transitions. Shows real-time event stream and
 * session state machine status.
 *
 * Data sources:
 * - GET /health → event_bus.stats, state_machine.stats
 * - WebSocket → session.state_change events
 * - GET /api/sessions → session list with current status
 */

"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";

// ─── Types ──────────────────────────────────────────────────────────────────

interface EventBusStats {
  published: number;
  dropped: number;
  subscriptions: number;
  event_types_subscribed: string[];
}

interface StateMachineStats {
  total_sessions: number;
  state_distribution: Record<string, number>;
  transitions_completed: number;
  invalid_attempts: number;
}

interface HealthData {
  ok: boolean;
  protocol_version: string;
  llm_url: string;
  llm_model: string;
  active_sessions: number;
  event_bus: EventBusStats;
  state_machine: StateMachineStats;
}

interface SessionState {
  id: string;
  title: string;
  status: string;
  model: string;
  updated_at: number;
}

interface StateChangeEvent {
  session_id: string;
  from_state: string;
  to_state: string;
  reason: string;
  timestamp: string;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const STATE_COLORS: Record<string, string> = {
  created: "text-blue-400",
  ready: "text-green-400",
  running: "text-yellow-400",
  interrupted: "text-orange-400",
  failed: "text-red-400",
  idle: "text-gray-400",
  archived: "text-gray-500",
};

const STATE_BADGES: Record<string, string> = {
  created: "INIT",
  ready: "IDLE",
  running: "ACTIVE",
  interrupted: "STOP",
  failed: "ERR",
  idle: "SLEEP",
  archived: "BOX",
};

function formatStateChange(from: string, to: string): string {
  const arrow = to === "failed" ? "⚠" : "→";
  return `${from} ${arrow} ${to}`;
}

function getGlassClass() {
  return "bg-white/5 backdrop-blur-lg border border-white/10 rounded-xl shadow-lg";
}

// ─── Component ──────────────────────────────────────────────────────────────

export function NervousSystemPanel() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [sessions, setSessions] = useState<SessionState[]>([]);
  const [recentEvents, setRecentEvents] = useState<StateChangeEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const eventBufferRef = useRef<StateChangeEvent[]>([]);
  const MAX_EVENTS = 50;

  // Connect WebSocket for state_change events
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event_type === "session.state_change" || data.to_state) {
          const evt: StateChangeEvent = {
            session_id: data.session_id || "unknown",
            from_state: data.from_state || "?",
            to_state: data.to_state || "?",
            reason: data.reason || "",
            timestamp: new Date().toISOString(),
          };
          eventBufferRef.current = [evt, ...eventBufferRef.current].slice(0, MAX_EVENTS);
          setRecentEvents([...eventBufferRef.current]);
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onerror = () => {
      // WebSocket errors are expected if backend isn't running
    };

    return () => {
      ws.close();
    };
  }, []);

  // Fetch health stats
  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error("Health check failed");
      const data = await res.json();
      setHealth(data);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  // Fetch sessions
  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch("/api/sessions");
      if (!res.ok) throw new Error("Failed to fetch sessions");
      const data = await res.json();
      setSessions(data);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    fetchSessions();
    const interval = setInterval(() => {
      fetchHealth();
      fetchSessions();
    }, 2000);
    return () => clearInterval(interval);
  }, [fetchHealth, fetchSessions]);

  // ─── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse" />
        <h2 className="text-lg font-semibold text-text-primary">
          Nervous System
        </h2>
        <span className="text-xs text-text-muted">Event Bus + State Machine</span>
      </div>

      {/* Status bar */}
      <div className="flex items-center gap-2 text-xs">
        {error ? (
          <span className="text-red-400">⚠ {error}</span>
        ) : (
          <span className="text-green-400">● Live</span>
        )}
        <span className="text-text-muted">·</span>
        <span className="text-text-muted">
          Refreshing every 2s
        </span>
      </div>

      {/* Event Bus Stats */}
      <div className={getGlassClass()}>
        <div className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">
            Event Bus (Pub/Sub)
          </h3>
          {health?.event_bus ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <div className="text-2xl font-bold text-text-primary">
                  {health.event_bus.published.toLocaleString()}
                </div>
                <div className="text-xs text-text-muted">Events Published</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-text-primary">
                  {health.event_bus.subscriptions}
                </div>
                <div className="text-xs text-text-muted">Subscriptions</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-text-primary">
                  {health.event_bus.dropped}
                </div>
                <div className="text-xs text-text-muted">Dropped (backpressure)</div>
              </div>
              <div>
                <div className="text-xs text-text-muted truncate">
                  {health.event_bus.event_types_subscribed.join(", ")}
                </div>
                <div className="text-xs text-text-muted">Event Types</div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-text-muted">Loading...</div>
          )}
        </div>
      </div>

      {/* State Machine Stats */}
      <div className={getGlassClass()}>
        <div className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">
            State Machine (FSM)
          </h3>
          {health?.state_machine ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <div className="text-2xl font-bold text-text-primary">
                  {health.state_machine.total_sessions}
                </div>
                <div className="text-xs text-text-muted">Active Sessions</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-text-primary">
                  {health.state_machine.transitions_completed.toLocaleString()}
                </div>
                <div className="text-xs text-text-muted">Transitions</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-text-primary">
                  {health.state_machine.invalid_attempts}
                </div>
                <div className="text-xs text-text-muted">Invalid Attempts</div>
              </div>
              <div>
                <div className="flex flex-wrap gap-1">
                  {Object.entries(health.state_machine.state_distribution || {}).map(
                    ([state, count]) => (
                      <span
                        key={state}
                        className={`text-xs px-2 py-0.5 rounded ${
                          STATE_COLORS[state] || "text-gray-400"
                        } bg-opacity-10 bg-gray-400`}
                      >
                        {STATE_BADGES[state] || state}: {count}
                      </span>
                    )
                  )}
                </div>
                <div className="text-xs text-text-muted mt-1">State Distribution</div>
              </div>
            </div>
          ) : (
            <div className="text-sm text-text-muted">Loading...</div>
          )}
        </div>
      </div>

      {/* VSM Layer Subscriptions */}
      <div className={getGlassClass()}>
        <div className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">
            VSM Layer Subscriptions
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-purple-400 font-mono text-xs">S1</span>
              <span className="text-text-secondary">Coding Agent</span>
              <span className="text-text-muted text-xs">→ tool.*, assistant.*</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-blue-400 font-mono text-xs">S2</span>
              <span className="text-text-secondary">Event Stream</span>
              <span className="text-text-muted text-xs">→ *</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-green-400 font-mono text-xs">S3</span>
              <span className="text-text-secondary">Manager</span>
              <span className="text-text-muted text-xs">→ session.*, resource.*, loop_safety.*</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-yellow-400 font-mono text-xs">S4</span>
              <span className="text-text-secondary">Planner</span>
              <span className="text-text-muted text-xs">→ self_improvement.*</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-red-400 font-mono text-xs">S5</span>
              <span className="text-text-secondary">Axioms</span>
              <span className="text-text-muted text-xs">→ session.failed</span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent State Changes */}
      <div className={getGlassClass()}>
        <div className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">
            Recent State Changes
          </h3>
          {recentEvents.length === 0 ? (
            <div className="text-sm text-text-muted">
              No state changes yet — create a session to see transitions
            </div>
          ) : (
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {recentEvents.slice(0, 20).map((evt, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 text-xs font-mono py-1 border-b border-border/30"
                >
                  <span className="text-text-muted w-16 truncate" title={evt.session_id}>
                    {evt.session_id.slice(0, 8)}
                  </span>
                  <span className={STATE_COLORS[evt.to_state] || "text-text-secondary"}>
                    {formatStateChange(evt.from_state, evt.to_state)}
                  </span>
                  {evt.reason && (
                    <span className="text-text-muted ml-auto truncate max-w-32">
                      ({evt.reason})
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Active Sessions */}
      <div className={getGlassClass()}>
        <div className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">
            Active Sessions ({sessions.length})
          </h3>
          {sessions.length === 0 ? (
            <div className="text-sm text-text-muted">No active sessions</div>
          ) : (
            <div className="space-y-2">
              {sessions.slice(0, 10).map((s) => (
                <div
                  key={s.id}
                  className="flex items-center gap-3 text-sm"
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      s.status === "running"
                        ? "bg-yellow-400 animate-pulse"
                        : s.status === "failed"
                          ? "bg-red-400"
                          : "bg-green-400"
                    }`}
                  />
                  <span className="text-text-secondary font-mono text-xs w-16 truncate">
                    {s.id.slice(0, 8)}
                  </span>
                  <span className={STATE_COLORS[s.status] || "text-text-secondary"}>
                    {STATE_BADGES[s.status] || s.status}
                  </span>
                  {s.title && (
                    <span className="text-text-muted text-xs truncate">
                      {s.title}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
