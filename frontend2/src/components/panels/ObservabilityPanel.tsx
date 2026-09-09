/**
 * Tektos-Ultima v1 — Observability Panel
 *
 * Dashboard for the observability system:
 * - Telemetry status
 * - Health checks
 * - Alert monitoring
 * - Auto-recovery status
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface ObservabilityStatus {
  status: string;
  telemetry: boolean;
  auto_recovery: boolean;
  health_checks?: Record<string, boolean>;
  alerts?: Array<{ type: string; name: string; timestamp: number }>;
  metrics?: Record<string, any>;
  error?: string;
}

export function ObservabilityPanel() {
  const [status, setStatus] = useState<ObservabilityStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/observability/status");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Loading observability status...</div>
      </div>
    );
  }

  const statusColor = status?.status === "active" ? "text-green-400" : "text-red-400";

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">📊</span>
          <h2 className="text-sm font-semibold text-text-primary">Observability</h2>
          <span className="text-xs text-text-muted">Telemetry & Health</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${status?.status === "active" ? "bg-green-400" : "bg-red-400"}`} />
          <span className={`text-xs font-mono ${statusColor}`}>{status?.status}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Status Cards */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-surface rounded-lg p-3 border border-border text-center">
            <div className={`text-lg font-bold ${status?.telemetry ? "text-green-400" : "text-red-400"}`}>
              {status?.telemetry ? "ON" : "OFF"}
            </div>
            <div className="text-xs text-text-muted">Telemetry</div>
          </div>
          <div className="bg-surface rounded-lg p-3 border border-border text-center">
            <div className={`text-lg font-bold ${status?.auto_recovery ? "text-green-400" : "text-red-400"}`}>
              {status?.auto_recovery ? "ON" : "OFF"}
            </div>
            <div className="text-xs text-text-muted">Auto-Recovery</div>
          </div>
          <div className="bg-surface rounded-lg p-3 border border-border text-center">
            <div className="text-lg font-bold text-text-primary">
              {status?.alerts?.length || 0}
            </div>
            <div className="text-xs text-text-muted">Alerts</div>
          </div>
        </div>

        {/* Health Checks */}
        {status?.health_checks && Object.keys(status.health_checks).length > 0 && (
          <div className="bg-surface rounded-lg p-3 border border-border">
            <h3 className="text-xs font-semibold text-text-muted mb-3">Health Checks</h3>
            <div className="space-y-1.5">
              {Object.entries(status.health_checks).map(([name, healthy]) => (
                <div key={name} className="flex items-center justify-between text-xs">
                  <span className="text-text-primary capitalize">{name.replace(/_/g, " ")}</span>
                  <span className={`font-mono ${healthy ? "text-green-400" : "text-red-400"}`}>
                    {healthy ? "healthy" : "unhealthy"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Alerts */}
        {status?.alerts && status.alerts.length > 0 && (
          <div className="bg-surface rounded-lg p-3 border border-border">
            <h3 className="text-xs font-semibold text-text-muted mb-3">Recent Alerts</h3>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {status.alerts.slice(-10).reverse().map((alert, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1 border-b border-border/50 last:border-0">
                  <span className="text-text-muted capitalize">{alert.type.replace(/_/g, " ")}</span>
                  <span className="text-text-primary">{alert.name}</span>
                  <span className="text-text-muted font-mono">
                    {new Date(alert.timestamp * 1000).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-400/10 border border-red-400/30 rounded-lg p-3">
            <span className="text-xs text-red-400">{error}</span>
          </div>
        )}
      </div>
    </div>
  );
}
