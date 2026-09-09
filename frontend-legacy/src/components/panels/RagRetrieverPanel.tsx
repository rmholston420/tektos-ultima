/**
 * Tektos-Ultima v1 — RAG Retriever Panel
 *
 * Dashboard for the RAG retriever:
 * - Database path and status
 * - Index statistics
 * - Retrieval performance
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface RAGRetrieverStatus {
  status: string;
  db_path: string;
  initialized: boolean;
  error?: string;
}

export function RagRetrieverPanel() {
  const [status, setStatus] = useState<RAGRetrieverStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/ragRetriever/status");
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
        <div className="text-text-muted text-sm">Loading RAG retriever status...</div>
      </div>
    );
  }

  const statusColor = status?.status === "initialized" ? "text-green-400" : "text-red-400";

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">📚</span>
          <h2 className="text-sm font-semibold text-text-primary">RAG Retriever</h2>
          <span className="text-xs text-text-muted">Vector Search Engine</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${status?.initialized ? "bg-green-400" : "bg-red-400"}`} />
          <span className={`text-xs font-mono ${statusColor}`}>{status?.status}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Status Card */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">Retriever Info</h3>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-text-muted">Status</span>
              <span className={`font-mono capitalize ${statusColor}`}>{status?.status}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Initialized</span>
              <span className={`font-mono ${status?.initialized ? "text-green-400" : "text-red-400"}`}>
                {status?.initialized ? "yes" : "no"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Database</span>
              <span className="text-text-primary font-mono text-right truncate ml-2" title={status?.db_path}>
                {status?.db_path || "—"}
              </span>
            </div>
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
