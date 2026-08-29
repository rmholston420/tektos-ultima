/**
 * Tektos-Ultima v1 — Repo Map Panel
 *
 * Dashboard for the repository map generator:
 * - Project structure overview
 * - File and directory counts
 * - Dependency graph stats
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface RepoMapStats {
  project_root: string;
  total_entries: number;
  files: number;
  directories: number;
}

interface RepoMapStatus {
  status: string;
  stats: RepoMapStats;
  error?: string;
}

export function RepoMapPanel() {
  const [status, setStatus] = useState<RepoMapStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/repoMap/status");
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
        <div className="text-text-muted text-sm">Loading repo map status...</div>
      </div>
    );
  }

  const stats = status?.stats;
  if (!stats) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Repo map not initialized</div>
      </div>
    );
  }

  const statusColor = status?.status === "initialized" ? "text-green-400" : "text-red-400";
  const fileRatio = stats.total_entries > 0 ? ((stats.files / stats.total_entries) * 100).toFixed(0) : "0";

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">🗺️</span>
          <h2 className="text-sm font-semibold text-text-primary">Repo Map</h2>
          <span className="text-xs text-text-muted">Repository Structure</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${status?.status === "initialized" ? "bg-green-400" : "bg-red-400"}`} />
          <span className={`text-xs font-mono ${statusColor}`}>{status?.status}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-surface rounded-lg p-3 border border-border text-center">
            <div className="text-2xl font-bold text-text-primary">{stats.total_entries.toLocaleString()}</div>
            <div className="text-xs text-text-muted">Total Entries</div>
          </div>
          <div className="bg-surface rounded-lg p-3 border border-border text-center">
            <div className="text-2xl font-bold text-blue-400">{stats.files.toLocaleString()}</div>
            <div className="text-xs text-text-muted">Files</div>
          </div>
          <div className="bg-surface rounded-lg p-3 border border-border text-center">
            <div className="text-2xl font-bold text-purple-400">{stats.directories.toLocaleString()}</div>
            <div className="text-xs text-text-muted">Directories</div>
          </div>
        </div>

        {/* File Ratio */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">Structure</h3>
          <div className="space-y-2">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-muted">Files</span>
                <span className="text-xs font-mono text-blue-400">{fileRatio}%</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div className="h-2 rounded-full bg-blue-400 transition-all" style={{ width: `${fileRatio}%` }} />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-muted">Directories</span>
                <span className="text-xs font-mono text-purple-400">{(100 - parseInt(fileRatio)).toFixed(0)}%</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div className="h-2 rounded-full bg-purple-400 transition-all" style={{ width: `${100 - parseInt(fileRatio)}%` }} />
              </div>
            </div>
          </div>
        </div>

        {/* Project Root */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-2">Project Root</h3>
          <div className="text-xs text-text-primary font-mono bg-bg-3 rounded-md p-2 truncate" title={stats.project_root}>
            {stats.project_root}
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
