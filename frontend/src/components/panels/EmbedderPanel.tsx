/**
 * Tektos-Ultima v1 — Embedder Panel
 *
 * Dashboard for the embedding model:
 * - Model info, base URL, connection status
 * - Embedding generation and similarity search
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface EmbedderStatus {
  status: string;
  model: string;
  base_url: string;
  error?: string;
}

export function EmbedderPanel() {
  const [status, setStatus] = useState<EmbedderStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [embedText, setEmbedText] = useState("");
  const [embedResult, setEmbedResult] = useState<string | null>(null);
  const [embedding, setEmbedding] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/embedder/status");
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

  const handleEmbed = async () => {
    if (!embedText.trim()) return;
    setEmbedding(true);
    setEmbedResult(null);
    try {
      const res = await fetch("/api/embedder/embed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: embedText }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEmbedResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setEmbedResult(`Error: ${err instanceof Error ? err.message : "Unknown"}`);
    } finally {
      setEmbedding(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Loading embedder status...</div>
      </div>
    );
  }

  const statusColor = status?.status === "initialized" ? "text-green-400" : status?.status === "active" ? "text-blue-400" : "text-red-400";

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">🔤</span>
          <h2 className="text-sm font-semibold text-text-primary">Embedder</h2>
          <span className="text-xs text-text-muted">Vector Embeddings</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className={`w-2 h-2 rounded-full ${status?.status === "initialized" || status?.status === "active" ? "bg-green-400" : "bg-red-400"}`} />
          <span className={`text-xs font-mono ${statusColor}`}>{status?.status}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Status Card */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">Model Info</h3>
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

        {/* Error */}
        {error && (
          <div className="bg-red-400/10 border border-red-400/30 rounded-lg p-3">
            <span className="text-xs text-red-400">{error}</span>
          </div>
        )}

        {/* Embed Text Input */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">Generate Embedding</h3>
          <textarea
            value={embedText}
            onChange={(e) => setEmbedText(e.target.value)}
            className="w-full bg-bg-3 border border-border rounded-md px-3 py-2 text-xs text-text-primary focus:outline-none focus:border-accent font-mono resize-none"
            rows={3}
            placeholder="Enter text to embed..."
          />
          <button
            onClick={handleEmbed}
            disabled={embedding || !embedText.trim()}
            className="mt-2 w-full bg-accent text-white text-xs font-medium py-2 rounded-md hover:bg-accent/90 transition-colors disabled:opacity-50"
          >
            {embedding ? "Embedding..." : "Embed"}
          </button>
          {embedResult && (
            <pre className="mt-2 text-xs text-text-muted whitespace-pre-wrap font-mono bg-bg-3 rounded-md p-2 max-h-32 overflow-y-auto">
              {embedResult}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
