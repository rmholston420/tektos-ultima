/**
 * Tektos-Ultima v1 — Tool Router Panel
 *
 * Dashboard for the tool router:
 * - Tool capability mapping
 * - Performance statistics per tool
 * - Error classification and recovery
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface ToolPerformance {
  total_calls: number;
  success_rate: string;
  average_duration: string;
  last_error: string;
}

interface ToolRouterStats {
  [toolName: string]: ToolPerformance;
}

interface ToolRouterStatus {
  status: string;
  stats: ToolRouterStats;
  error?: string;
}

export function ToolRouterPanel() {
  const [status, setStatus] = useState<ToolRouterStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/toolRouter/status");
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
        <div className="text-text-muted text-sm">Loading tool router status...</div>
      </div>
    );
  }

  const stats = status?.stats;
  if (!stats) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Tool router not initialized</div>
      </div>
    );
  }

  const toolNames = Object.keys(stats);
  const statusColor = status?.status === "initialized" ? "text-green-400" : "text-red-400";

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">🔀</span>
          <h2 className="text-sm font-semibold text-text-primary">Tool Router</h2>
          <span className="text-xs text-text-muted">Tool Selection & Routing</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${status?.status === "initialized" ? "bg-green-400" : "bg-red-400"}`} />
          <span className={`text-xs font-mono ${statusColor}`}>{status?.status}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Tool Stats */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">Tool Performance ({toolNames.length} tools)</h3>
          <div className="space-y-2">
            {toolNames.map((toolName) => {
              const perf = stats[toolName];
              const successRate = parseFloat(perf.success_rate) || 0;
              const rateColor = successRate >= 90 ? "text-green-400" : successRate >= 50 ? "text-amber-400" : "text-red-400";
              return (
                <div key={toolName} className="bg-bg-3 rounded-md p-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono text-accent">{toolName}</span>
                    <span className={`text-xs font-mono ${rateColor}`}>{perf.success_rate}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-text-muted">
                    <span>Calls: {perf.total_calls}</span>
                    <span>Duration: {perf.average_duration}</span>
                  </div>
                  {perf.last_error && perf.last_error !== "None" && (
                    <div className="text-xs text-red-400 mt-1 truncate" title={perf.last_error}>
                      Error: {perf.last_error}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

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
