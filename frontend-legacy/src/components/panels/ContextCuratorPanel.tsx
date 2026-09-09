/**
 * Tektos-Ultima v1 — Context Curator Panel
 *
 * Dashboard for the context curator:
 * - Token budget tracking
 * - Compaction status and history
 * - Snapshot management
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface ContextCuratorStats {
  max_tokens: number;
  current_tokens: number;
  budget_remaining: number;
  compaction_threshold: number;
  should_compact: boolean;
  total_compactions: number;
  snapshots_tracked: number;
}

interface ContextCuratorStatus {
  status: string;
  stats: ContextCuratorStats;
  error?: string;
}

export function ContextCuratorPanel() {
  const [status, setStatus] = useState<ContextCuratorStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/contextCurator/status");
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
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Loading context curator status...</div>
      </div>
    );
  }

  const stats = status?.stats;
  if (!stats) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Context curator not initialized</div>
      </div>
    );
  }

  const budgetPercent = (stats.current_tokens / stats.max_tokens) * 100;
  const budgetColor = budgetPercent > 90 ? "text-red-400" : budgetPercent > 75 ? "text-amber-400" : "text-green-400";
  const budgetBarColor = budgetPercent > 90 ? "bg-red-400" : budgetPercent > 75 ? "bg-amber-400" : "bg-green-400";
  const compactColor = stats.should_compact ? "text-red-400" : "text-green-400";

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">📑</span>
          <h2 className="text-sm font-semibold text-text-primary">Context Curator</h2>
          <span className="text-xs text-text-muted">Token Budget Manager</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${status?.status === "initialized" ? "bg-green-400" : "bg-red-400"}`} />
          <span className={`text-xs font-mono ${compactColor}`}>
            {stats.should_compact ? "COMPACT" : "OK"}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Budget Card */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">Token Budget</h3>
          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-muted">Usage</span>
                <span className={`text-sm font-mono ${budgetColor}`}>
                  {stats.current_tokens.toLocaleString()} / {stats.max_tokens.toLocaleString()}
                </span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2.5">
                <div
                  className={`h-2.5 rounded-full transition-all ${budgetBarColor}`}
                  style={{ width: `${Math.min(budgetPercent, 100)}%` }}
                />
              </div>
              <div className="flex justify-between mt-1 text-xs text-text-muted">
                <span>{budgetPercent.toFixed(1)}% used</span>
                <span>{stats.budget_remaining.toLocaleString()} remaining</span>
              </div>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-surface rounded-lg p-3 border border-border">
            <div className="text-lg font-bold text-text-primary">{stats.total_compactions}</div>
            <div className="text-xs text-text-muted">Total Compactions</div>
          </div>
          <div className="bg-surface rounded-lg p-3 border border-border">
            <div className="text-lg font-bold text-text-primary">{stats.snapshots_tracked}</div>
            <div className="text-xs text-text-muted">Snapshots Tracked</div>
          </div>
          <div className="bg-surface rounded-lg p-3 border border-border">
            <div className="text-lg font-bold text-blue-400">{(stats.compaction_threshold * 100).toFixed(0)}%</div>
            <div className="text-xs text-text-muted">Compaction Threshold</div>
          </div>
          <div className="bg-surface rounded-lg p-3 border border-border">
            <div className={`text-lg font-bold ${compactColor}`}>
              {stats.should_compact ? "YES" : "NO"}
            </div>
            <div className="text-xs text-text-muted">Should Compact</div>
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
