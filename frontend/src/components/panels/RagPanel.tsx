/**
 * Tektos-Ultima v1 — RAG Panel
 *
 * Dashboard for the RAG engine:
 * - Indexing status
 * - Query statistics
 * - Embedder/retriever connectivity
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface RAGStats {
  indexed_count: number;
  query_count: number;
  top_k: number;
  similarity_threshold: number;
  has_embedder: boolean;
  has_retriever: boolean;
}

interface RAGStatus {
  status: string;
  stats: RAGStats;
  error?: string;
}

export function RagPanel() {
  const [status, setStatus] = useState<RAGStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/rag/status");
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
        <div className="text-text-muted text-sm">Loading RAG status...</div>
      </div>
    );
  }

  const stats = status?.stats;
  if (!stats) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">RAG engine not initialized</div>
      </div>
    );
  }

  const statusColor = status?.status === "initialized" ? "text-green-400" : "text-red-400";

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">🔍</span>
          <h2 className="text-sm font-semibold text-text-primary">RAG Engine</h2>
          <span className="text-xs text-text-muted">Retrieval-Augmented Generation</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${status?.status === "initialized" ? "bg-green-400" : "bg-red-400"}`} />
          <span className={`text-xs font-mono ${statusColor}`}>{status?.status}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Status Cards */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-surface rounded-lg p-3 border border-border">
            <div className="text-lg font-bold text-text-primary">{stats.indexed_count.toLocaleString()}</div>
            <div className="text-xs text-text-muted">Indexed Documents</div>
          </div>
          <div className="bg-surface rounded-lg p-3 border border-border">
            <div className="text-lg font-bold text-blue-400">{stats.query_count}</div>
            <div className="text-xs text-text-muted">Queries Executed</div>
          </div>
          <div className="bg-surface rounded-lg p-3 border border-border">
            <div className="text-lg font-bold text-purple-400">{stats.top_k}</div>
            <div className="text-xs text-text-muted">Top-K Results</div>
          </div>
          <div className="bg-surface rounded-lg p-3 border border-border">
            <div className="text-lg font-bold text-amber-400">{(stats.similarity_threshold * 100).toFixed(0)}%</div>
            <div className="text-xs text-text-muted">Similarity Threshold</div>
          </div>
        </div>

        {/* Connectivity */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">Connectivity</h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Embedder</span>
              <span className={`text-xs font-mono ${stats.has_embedder ? "text-green-400" : "text-red-400"}`}>
                {stats.has_embedder ? "connected" : "disconnected"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Retriever</span>
              <span className={`text-xs font-mono ${stats.has_retriever ? "text-green-400" : "text-red-400"}`}>
                {stats.has_retriever ? "connected" : "disconnected"}
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
