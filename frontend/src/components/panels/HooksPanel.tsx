/**
 * Tektos-Ultima v1 — Hooks Panel
 *
 * Displays the runtime event-hook registry:
 * - Every registered event type
 * - The ordered list of handlers bound to it
 * - Manual "fire" for the built-in event catalog (via /api/hooks/fire)
 *
 * The backend does not track per-hook execution counts or success rate, so
 * we intentionally do not display fake metrics here.
 */

"use client";

import React, { useCallback, useEffect, useState } from "react";

interface HookGroup {
  event_type: string;
  handlers: string[];
}

interface HooksResponse {
  hooks?: HookGroup[];
  error?: string;
}

// Event types accepted by /api/hooks/fire (mirror src/tektos/main.py::_FireHookBody).
const FIREABLE_EVENTS = [
  "user_prompt_submit",
  "pre_tool_use",
  "post_tool_use",
  "session_start",
  "session_end",
  "notification",
];

export function HooksPanel() {
  const [hooks, setHooks] = useState<HookGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [firing, setFiring] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/hooks");
      const data = (await res.json()) as HooksResponse;
      if (data.error) {
        setError(data.error);
        setHooks([]);
      } else {
        setHooks(Array.isArray(data.hooks) ? data.hooks : []);
        setError(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setHooks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  const fireHook = useCallback(async (eventType: string) => {
    setFiring(eventType);
    setLastResult(null);
    try {
      const res = await fetch("/api/hooks/fire", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_type: eventType }),
      });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body?.detail || body?.error || `HTTP ${res.status}`);
      }
      setLastResult(`Fired ${eventType} → ${JSON.stringify(body).slice(0, 200)}`);
    } catch (e) {
      setLastResult(`Failed to fire ${eventType}: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setFiring(null);
    }
  }, []);

  const registeredEventTypes = new Set(hooks.map((h) => h.event_type));
  const totalHandlers = hooks.reduce((n, h) => n + (h.handlers?.length ?? 0), 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="panel-card">
          <div className="text-2xl font-bold text-accent">{hooks.length}</div>
          <div className="text-sm text-text-muted">Event Types</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-status-success">{totalHandlers}</div>
          <div className="text-sm text-text-muted">Registered Handlers</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-text-primary">{FIREABLE_EVENTS.length}</div>
          <div className="text-sm text-text-muted">Fireable Events</div>
        </div>
      </div>

      {error && (
        <div className="rounded border border-status-error/40 bg-status-error/10 p-3 text-xs text-status-error">
          {error}
        </div>
      )}

      <div className="space-y-3">
        {hooks.length === 0 && !error && (
          <div className="rounded border border-border p-4 text-xs text-text-muted text-center">
            No hook handlers registered yet.
          </div>
        )}
        {hooks.map((group) => (
          <div key={group.event_type} className="panel-card">
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3">
                  <span className="w-2.5 h-2.5 rounded-full bg-status-success" />
                  <h3 className="font-medium text-text-primary font-mono">{group.event_type}</h3>
                  <span className="text-xs bg-bg-3 px-2 py-0.5 rounded-full text-text-muted">
                    {group.handlers?.length ?? 0} handler{(group.handlers?.length ?? 0) === 1 ? "" : "s"}
                  </span>
                </div>
                {group.handlers && group.handlers.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2 ml-5">
                    {group.handlers.map((name, i) => (
                      <span
                        key={`${group.event_type}-${i}-${name}`}
                        className="text-xs font-mono text-text-secondary bg-bg-3 px-2 py-0.5 rounded"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              {FIREABLE_EVENTS.includes(group.event_type) && (
                <button
                  onClick={() => fireHook(group.event_type)}
                  disabled={firing === group.event_type}
                  className="text-xs px-3 py-1.5 rounded border border-border text-text-secondary hover:bg-bg-3 disabled:opacity-40"
                >
                  {firing === group.event_type ? "Firing…" : "Fire"}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="panel-card">
        <div className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
          Manual Trigger
        </div>
        <div className="flex flex-wrap gap-2">
          {FIREABLE_EVENTS.filter((e) => !registeredEventTypes.has(e)).map((e) => (
            <button
              key={e}
              onClick={() => fireHook(e)}
              disabled={firing === e}
              className="text-xs font-mono px-2 py-1 rounded border border-border text-text-muted hover:bg-bg-3 disabled:opacity-40"
            >
              {firing === e ? `${e}…` : e}
            </button>
          ))}
        </div>
        {lastResult && (
          <div className="mt-3 text-xs font-mono text-text-secondary break-all">
            {lastResult}
          </div>
        )}
      </div>
    </div>
  );
}
