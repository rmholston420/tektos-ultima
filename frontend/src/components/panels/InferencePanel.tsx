/**
 * Tektos-Ultima v1 — Inference Panel
 *
 * Dashboard for the LLM inference engine:
 * - Model info, health, connection status
 * - Real-time metrics (tokens, latency, cache)
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface InferenceStatus {
  status: string;
  model: string;
  base_url: string;
  health: string;
  error?: string;
}

interface InferenceMetrics {
  tokens_per_second?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  cache_hit_rate?: number;
  avg_prompt_latency?: number;
  avg_generation_latency?: number;
  [key: string]: any;
}

export function InferencePanel() {
  const [status, setStatus] = useState<InferenceStatus | null>(null);
  const [metrics, setMetrics] = useState<InferenceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, metricsRes] = await Promise.all([
        fetch("/api/inference/status"),
        fetch("/api/inference/metrics"),
      ]);
      if (!statusRes.ok) throw new Error(`HTTP ${statusRes.status}`);
      const statusData = await statusRes.json();
      setStatus(statusData);
      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setMetrics(metricsData);
      }
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
        <div className="text-text-muted text-sm">Loading inference status...</div>
      </div>
    );
  }

  const healthColor = status?.health === "ok" ? "text-green-400" : status?.health === "degraded" ? "text-amber-400" : "text-red-400";
  const statusColor = status?.status === "active" ? "text-green-400" : status?.status === "initialized" ? "text-blue-400" : "text-red-400";

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">🧠</span>
          <h2 className="text-sm font-semibold text-text-primary">Inference Engine</h2>
          <span className="text-xs text-text-muted">LLM Runtime</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${status?.health === "ok" ? "bg-green-400" : "bg-red-400"}`} />
          <span className={`text-xs font-mono ${healthColor}`}>{status?.health}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Model Info */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">Model</h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">Model</span>
              <span className="text-text-primary font-mono">{status?.model || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Base URL</span>
              <span className="text-text-primary font-mono">{status?.base_url || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Status</span>
              <span className={`font-mono capitalize ${statusColor}`}>{status?.status}</span>
            </div>
          </div>
        </div>

        {/* Metrics */}
        {metrics && (
          <div className="bg-surface rounded-lg p-3 border border-border">
            <h3 className="text-xs font-semibold text-text-muted mb-3">Metrics</h3>
            <div className="grid grid-cols-2 gap-3">
              {metrics.total_tokens !== undefined && (
                <div className="bg-bg-3 rounded-md p-2 text-center">
                  <div className="text-lg font-bold text-text-primary">{metrics.total_tokens.toLocaleString()}</div>
                  <div className="text-xs text-text-muted">Total Tokens</div>
                </div>
              )}
              {metrics.tokens_per_second !== undefined && (
                <div className="bg-bg-3 rounded-md p-2 text-center">
                  <div className="text-lg font-bold text-blue-400">{metrics.tokens_per_second.toFixed(1)}</div>
                  <div className="text-xs text-text-muted">Tokens/sec</div>
                </div>
              )}
              {metrics.cache_hit_rate !== undefined && (
                <div className="bg-bg-3 rounded-md p-2 text-center">
                  <div className="text-lg font-bold text-purple-400">{(metrics.cache_hit_rate * 100).toFixed(1)}%</div>
                  <div className="text-xs text-text-muted">Cache Hit Rate</div>
                </div>
              )}
              {metrics.avg_prompt_latency !== undefined && (
                <div className="bg-bg-3 rounded-md p-2 text-center">
                  <div className="text-lg font-bold text-amber-400">{metrics.avg_prompt_latency.toFixed(1)}ms</div>
                  <div className="text-xs text-text-muted">Avg Prompt Latency</div>
                </div>
              )}
              {metrics.avg_generation_latency !== undefined && (
                <div className="bg-bg-3 rounded-md p-2 text-center">
                  <div className="text-lg font-bold text-emerald-400">{metrics.avg_generation_latency.toFixed(1)}ms</div>
                  <div className="text-xs text-text-muted">Avg Generation Latency</div>
                </div>
              )}
              {metrics.prompt_tokens !== undefined && (
                <div className="bg-bg-3 rounded-md p-2 text-center">
                  <div className="text-lg font-bold text-text-primary">{metrics.prompt_tokens.toLocaleString()}</div>
                  <div className="text-xs text-text-muted">Prompt Tokens</div>
                </div>
              )}
              {metrics.completion_tokens !== undefined && (
                <div className="bg-bg-3 rounded-md p-2 text-center">
                  <div className="text-lg font-bold text-text-primary">{metrics.completion_tokens.toLocaleString()}</div>
                  <div className="text-xs text-text-muted">Completion Tokens</div>
                </div>
              )}
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
