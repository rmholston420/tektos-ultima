/**
 * Tektos-Ultima v1 — Hooks Panel
 *
 * Event hook management with:
 * - Hook definitions and triggers
 * - Execution history
 * - Success/failure rates
 * - Enable/disable toggles
 */

"use client";

import React, { useState, useEffect } from "react";

interface Hook {
  id: string;
  name: string;
  trigger: string;
  action: string;
  enabled: boolean;
  executions: number;
  successRate: number;
  lastExecution: string;
}

export function HooksPanel() {
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/hooks")
      .then((r) => r.json())
      .then((data) => {
        setHooks(data.hooks || []);
        setLoading(false);
      })
      .catch(() => {
        setHooks([]);
        setLoading(false);
      });
  }, []);

  const enabledCount = hooks.filter((h) => h.enabled).length;
  const totalExec = hooks.reduce((sum, h) => sum + h.executions, 0);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" /></div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="panel-card">
          <div className="text-2xl font-bold text-accent">{hooks.length}</div>
          <div className="text-sm text-text-muted">Total Hooks</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-status-success">{enabledCount}</div>
          <div className="text-sm text-text-muted">Active</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-text-primary">{totalExec.toLocaleString()}</div>
          <div className="text-sm text-text-muted">Total Executions</div>
        </div>
      </div>

      <div className="space-y-3">
        {hooks.map((hook) => (
          <div key={hook.id} className="panel-card">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <span className={`w-2.5 h-2.5 rounded-full ${hook.enabled ? "bg-status-success" : "bg-text-muted"}`} />
                  <h3 className="font-medium text-text-primary">{hook.name}</h3>
                  <span className="text-xs bg-bg-3 px-2 py-0.5 rounded-full text-text-muted">{hook.trigger}</span>
                  <span className="text-xs font-mono text-text-secondary">{hook.action}</span>
                </div>
                <div className="flex items-center gap-4 mt-2 ml-5">
                  <span className="text-xs text-text-muted">{hook.executions.toLocaleString()} executions</span>
                  <span className="text-xs text-text-muted">Last: {hook.lastExecution}</span>
                  <span className="text-xs text-accent">Success: {hook.successRate}%</span>
                </div>
              </div>
              <button
                onClick={() => setHooks(hooks.map((h) => h.id === hook.id ? { ...h, enabled: !h.enabled } : h))}
                className={`relative w-12 h-6 rounded-full transition-all ${hook.enabled ? "bg-accent" : "bg-bg-3 border border-border"}`}
              >
                <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-all ${hook.enabled ? "left-6" : "left-0.5"}`} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
