/**
 * Tektos-Ultima v1 — Self-Repair Panel
 *
 * Dashboard for the self-repair engine:
 * - Engine status (running, uptime, repair counts)
 * - Health monitoring scores
 * - Repair history with status breakdown
 * - Effectiveness tracking
 * - Manual repair trigger
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface RepairRecord {
  record_id: string;
  threat_category: string;
  threat_severity: string;
  description: string;
  status: string;
  strategy_used?: string;
  verification_passed?: boolean;
  verification_details?: string;
  degradation_applied?: string;
  repair_actions: string[];
  time_to_diagnose_seconds?: number;
  time_to_repair_seconds?: number;
  time_to_verify_seconds?: number;
  total_time_seconds?: number;
  completed_at?: number;
  error?: string;
}

interface SelfRepairStatus {
  running: boolean;
  uptime_seconds: number;
  total_repairs: number;
  completed_repairs: number;
  failed_repairs: number;
  degraded_repairs: number;
  strategies_registered: number;
  workflows_registered: number;
  effectiveness?: Record<string, unknown>;
  latest_health?: Record<string, unknown>;
  health_trend?: string;
}

interface SelfRepairState {
  status: SelfRepairStatus | null;
  history: RepairRecord[];
  loading: boolean;
  error: string | null;
}

const statusColors: Record<string, string> = {
  COMPLETED: "text-green-400",
  FAILED: "text-red-400",
  DEGRADED: "text-amber-400",
  PENDING: "text-blue-400",
  DIAGNOSING: "text-blue-300",
  REPAIRING: "text-amber-300",
  VERIFYING: "text-purple-300",
};

const severityColors: Record<string, string> = {
  "0": "text-blue-400",
  "1": "text-amber-400",
  "2": "text-orange-400",
  "3": "text-red-400",
};

const severityLabels: Record<string, string> = {
  "0": "LOW",
  "1": "MEDIUM",
  "2": "HIGH",
  "3": "CRITICAL",
};

export function SelfRepairPanel() {
  const [state, setState] = useState<SelfRepairState>({
    status: null,
    history: [],
    loading: true,
    error: null,
  });
  const [activeTab, setActiveTab] = useState<"status" | "history" | "trigger">("status");
  const [triggerForm, setTriggerForm] = useState({
    threat_category: "resource_exhaustion",
    threat_severity: "1",
    ctx: "",
  });
  const [triggerResult, setTriggerResult] = useState<Record<string, unknown> | null>(null);
  const [triggerLoading, setTriggerLoading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, historyRes] = await Promise.all([
        fetch("/api/self_repair/status"),
        fetch("/api/self_repair/history?limit=50"),
      ]);

      if (!statusRes.ok || !historyRes.ok) {
        setState((prev) => ({
          ...prev,
          loading: false,
          error: "Failed to fetch self-repair data",
        }));
        return;
      }

      const status = await statusRes.json();
      const historyData = await historyRes.json();

      setState({
        status,
        history: historyData.history || [],
        loading: false,
        error: null,
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : "Unknown error",
      }));
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleTriggerRepair = async () => {
    setTriggerLoading(true);
    setTriggerResult(null);
    try {
      const ctx = triggerForm.ctx ? JSON.parse(triggerForm.ctx) : {};
      const res = await fetch("/api/self_repair/repair", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          threat_category: triggerForm.threat_category,
          threat_severity: parseInt(triggerForm.threat_severity),
          ctx,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const result = await res.json();
      setTriggerResult(result);
      fetchData();
    } catch (err) {
      setTriggerResult({ error: err instanceof Error ? err.message : "Unknown error" });
    } finally {
      setTriggerLoading(false);
    }
  };

  const formatUptime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h}h ${m}m ${s}s`;
  };

  const formatTime = (seconds?: number): string => {
    if (seconds === undefined) return "—";
    return `${seconds.toFixed(2)}s`;
  };

  if (state.loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Loading self-repair status...</div>
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-400 text-sm">{state.error}</div>
      </div>
    );
  }

  const s = state.status;
  if (!s) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Self-repair engine not initialized</div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${s.running ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
          <h2 className="text-sm font-semibold text-text-primary">Self-Repair Engine</h2>
          <span className="text-xs text-text-muted">{s.running ? "Running" : "Stopped"}</span>
        </div>
        <div className="flex items-center gap-1 bg-bg-3 rounded-lg p-0.5">
          {(["status", "history", "trigger"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                activeTab === tab
                  ? "bg-accent text-white shadow-sm"
                  : "text-text-muted hover:text-text-primary"
              }`}
            >
              {tab === "status" ? "Status" : tab === "history" ? "History" : "Trigger"}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeTab === "status" && (
          <>
            {/* Engine Overview */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-surface rounded-lg p-3 border border-border">
                <div className="text-xs text-text-muted mb-1">Uptime</div>
                <div className="text-lg font-mono text-text-primary">{formatUptime(s.uptime_seconds)}</div>
              </div>
              <div className="bg-surface rounded-lg p-3 border border-border">
                <div className="text-xs text-text-muted mb-1">Strategies</div>
                <div className="text-lg font-mono text-text-primary">{s.strategies_registered}</div>
              </div>
              <div className="bg-surface rounded-lg p-3 border border-border">
                <div className="text-xs text-text-muted mb-1">Workflows</div>
                <div className="text-lg font-mono text-text-primary">{s.workflows_registered}</div>
              </div>
              <div className="bg-surface rounded-lg p-3 border border-border">
                <div className="text-xs text-text-muted mb-1">Health Trend</div>
                <div className="text-lg font-mono text-text-primary">{s.health_trend || "—"}</div>
              </div>
            </div>

            {/* Repair Counts */}
            <div className="bg-surface rounded-lg p-3 border border-border">
              <h3 className="text-xs font-semibold text-text-muted mb-3">Repair Summary</h3>
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center">
                  <div className="text-2xl font-bold text-text-primary">{s.total_repairs}</div>
                  <div className="text-xs text-text-muted">Total</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-400">{s.completed_repairs}</div>
                  <div className="text-xs text-text-muted">Completed</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-red-400">{s.failed_repairs}</div>
                  <div className="text-xs text-text-muted">Failed</div>
                </div>
              </div>
              {s.degraded_repairs > 0 && (
                <div className="mt-3 pt-3 border-t border-border">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-muted">Degraded Repairs</span>
                    <span className="text-sm font-mono text-amber-400">{s.degraded_repairs}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Latest Health */}
            {s.latest_health && (
              <div className="bg-surface rounded-lg p-3 border border-border">
                <h3 className="text-xs font-semibold text-text-muted mb-3">Latest Health Check</h3>
                <div className="space-y-2">
                  {Object.entries(s.latest_health).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-xs text-text-muted capitalize">{key.replace(/_/g, " ")}</span>
                      <span className="text-xs font-mono text-text-primary">{String(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Effectiveness */}
            {s.effectiveness && (
              <div className="bg-surface rounded-lg p-3 border border-border">
                <h3 className="text-xs font-semibold text-text-muted mb-3">Effectiveness Tracking</h3>
                <div className="space-y-2">
                  {Object.entries(s.effectiveness).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-xs text-text-muted capitalize">{key.replace(/_/g, " ")}</span>
                      <span className="text-xs font-mono text-text-primary">{String(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === "history" && (
          <div className="space-y-3">
            {state.history.length === 0 ? (
              <div className="text-center py-8 text-text-muted text-sm">No repair history yet</div>
            ) : (
              state.history.map((record) => (
                <div key={record.record_id} className="bg-surface rounded-lg p-3 border border-border">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-text-muted">{record.record_id}</span>
                      <span className={`text-xs font-medium ${statusColors[record.status] || "text-text-muted"}`}>
                        {record.status}
                      </span>
                    </div>
                    <span className={`text-xs font-medium ${severityColors[record.threat_severity] || "text-text-muted"}`}>
                      {severityLabels[record.threat_severity] || record.threat_severity}
                    </span>
                  </div>

                  <div className="text-xs text-text-primary mb-2">{record.description}</div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-text-muted">Strategy:</span>{" "}
                      <span className="text-text-primary">{record.strategy_used || "—"}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Time:</span>{" "}
                      <span className="text-text-primary">{formatTime(record.total_time_seconds)}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Verify:</span>{" "}
                      <span className={record.verification_passed ? "text-green-400" : "text-red-400"}>
                        {record.verification_passed ? "Passed" : record.verification_details || "Failed"}
                      </span>
                    </div>
                    {record.degradation_applied && (
                      <div>
                        <span className="text-text-muted">Degradation:</span>{" "}
                        <span className="text-amber-400">{record.degradation_applied}</span>
                      </div>
                    )}
                  </div>

                  {record.repair_actions.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border">
                      <div className="text-xs text-text-muted mb-1">Actions:</div>
                      <ul className="text-xs text-text-primary space-y-0.5">
                        {record.repair_actions.map((action, i) => (
                          <li key={i} className="flex items-start gap-1">
                            <span className="text-text-muted mt-0.5">•</span>
                            <span>{action}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {record.error && (
                    <div className="mt-2 pt-2 border-t border-border">
                      <span className="text-xs text-red-400">Error: {record.error}</span>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === "trigger" && (
          <div className="space-y-4">
            <div className="bg-surface rounded-lg p-3 border border-border">
              <h3 className="text-xs font-semibold text-text-muted mb-3">Manual Repair Trigger</h3>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-text-muted mb-1">Threat Category</label>
                  <input
                    type="text"
                    value={triggerForm.threat_category}
                    onChange={(e) => setTriggerForm((f) => ({ ...f, threat_category: e.target.value }))}
                    className="w-full bg-bg-3 border border-border rounded-md px-3 py-2 text-xs text-text-primary focus:outline-none focus:border-accent"
                    placeholder="e.g., resource_exhaustion"
                  />
                </div>

                <div>
                  <label className="block text-xs text-text-muted mb-1">Severity (0-3)</label>
                  <select
                    value={triggerForm.threat_severity}
                    onChange={(e) => setTriggerForm((f) => ({ ...f, threat_severity: e.target.value }))}
                    className="w-full bg-bg-3 border border-border rounded-md px-3 py-2 text-xs text-text-primary focus:outline-none focus:border-accent"
                  >
                    <option value="0">0 - LOW</option>
                    <option value="1">1 - MEDIUM</option>
                    <option value="2">2 - HIGH</option>
                    <option value="3">3 - CRITICAL</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs text-text-muted mb-1">Context (JSON, optional)</label>
                  <textarea
                    value={triggerForm.ctx}
                    onChange={(e) => setTriggerForm((f) => ({ ...f, ctx: e.target.value }))}
                    className="w-full bg-bg-3 border border-border rounded-md px-3 py-2 text-xs text-text-primary focus:outline-none focus:border-accent font-mono"
                    rows={3}
                    placeholder='{"gpu_temp": 85, "vram_usage": 0.9}'
                  />
                </div>

                <button
                  onClick={handleTriggerRepair}
                  disabled={triggerLoading}
                  className="w-full bg-accent text-white text-xs font-medium py-2 rounded-md hover:bg-accent/90 transition-colors disabled:opacity-50"
                >
                  {triggerLoading ? "Triggering..." : "Trigger Repair"}
                </button>
              </div>
            </div>

            {triggerResult && (
              <div className="bg-surface rounded-lg p-3 border border-border">
                <h3 className="text-xs font-semibold text-text-muted mb-2">Result</h3>
                <pre className="text-xs text-text-primary font-mono whitespace-pre-wrap overflow-auto max-h-48">
                  {JSON.stringify(triggerResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
