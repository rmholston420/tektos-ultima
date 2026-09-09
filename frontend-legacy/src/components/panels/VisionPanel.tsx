/**
 * Tektos-Ultima v1 — Vision Panel
 *
 * Dashboard for the vision analysis system:
 * - Vision client status
 * - Image analysis capabilities
 * - LLM vision endpoint connectivity
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface VisionStatus {
  ok: boolean;
  initialized: boolean;
  detail: string;
  error?: string;
}

export function VisionPanel() {
  const [status, setStatus] = useState<VisionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/vision/status");
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
        <div className="text-text-muted text-sm">Loading vision status...</div>
      </div>
    );
  }

  const statusColor = status?.ok ? "text-green-400" : "text-red-400";

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">👁️</span>
          <h2 className="text-sm font-semibold text-text-primary">Vision</h2>
          <span className="text-xs text-text-muted">Image Analysis</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${status?.ok ? "bg-green-400" : "bg-red-400"}`} />
          <span className={`text-xs font-mono ${statusColor}`}>{status?.ok ? "active" : "inactive"}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Status Card */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">Vision Client</h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">Initialized</span>
              <span className={`font-mono ${status?.initialized ? "text-green-400" : "text-red-400"}`}>
                {status?.initialized ? "yes" : "no"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Status</span>
              <span className={`font-mono ${statusColor}`}>
                {status?.ok ? "ready" : "not ready"}
              </span>
            </div>
            <div className="mt-2 p-2 bg-bg-3 rounded-md">
              <span className="text-text-muted">Detail: </span>
              <span className="text-text-primary">{status?.detail || "—"}</span>
            </div>
          </div>
        </div>

        {/* Setup Instructions */}
        {!status?.ok && (
          <div className="bg-amber-400/10 border border-amber-400/30 rounded-lg p-3">
            <h3 className="text-xs font-semibold text-amber-400 mb-2">Setup Required</h3>
            <p className="text-xs text-text-muted">
              Set the <code className="text-accent font-mono">TEKTOS_VISION_LLM_URL</code> environment variable to enable vision analysis.
            </p>
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
