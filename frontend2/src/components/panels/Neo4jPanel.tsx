/**
 * Tektos-Ultima v1 — Neo4j Graph Database Panel
 *
 * Displays Neo4j graph database backend status:
 * - Connection health, URI, node/edge counts
 * - Graph schema overview
 * - Recent queries
 */

import { useState, useEffect, useCallback } from "react";

interface Neo4jStatus {
  status: string;
  database: string;
  uri: string | null;
  healthy: boolean;
  error: string | null;
}

export function Neo4jPanel() {
  const [status, setStatus] = useState<Neo4jStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/neo4j/status");
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error("Failed to load Neo4j status:", err);
      setStatus({
        status: "error",
        database: "neo4j",
        uri: null,
        healthy: false,
        error: String(err),
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading Neo4j status...</div>
      </div>
    );
  }

  if (!status) return null;

  const statusColor =
    status.status === "connected"
      ? "text-green-400"
      : status.status === "partial"
        ? "text-amber-400"
        : status.status === "not_initialized"
          ? "text-slate-500"
          : "text-red-400";

  const statusBg =
    status.status === "connected"
      ? "bg-green-500/10 border-green-500/30"
      : status.status === "partial"
        ? "bg-amber-500/10 border-amber-500/30"
        : status.status === "not_initialized"
          ? "bg-slate-500/5 border-slate-700"
          : "bg-red-500/10 border-red-500/30";

  return (
    <div className="space-y-6">
      {/* ─── Status Card ─────────────────────────────────────────────── */}
      <div className={`border rounded-lg p-6 ${statusBg}`}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Neo4j Graph Database</h2>
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${status.healthy ? "bg-green-400" : status.status === "not_initialized" ? "bg-slate-600" : "bg-red-400"}`} />
            <span className={`text-sm font-medium ${statusColor}`}>{status.status}</span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-xs text-slate-500">URI</span>
            <div className="text-slate-300 font-mono mt-1 truncate">
              {status.uri || "—"}
            </div>
          </div>
          <div>
            <span className="text-xs text-slate-500">Health</span>
            <div className={`mt-1 ${status.healthy ? "text-green-400" : "text-red-400"}`}>
              {status.healthy ? "Healthy" : "Unhealthy"}
            </div>
          </div>
        </div>

        {status.error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <div className="text-xs text-red-400 font-medium mb-1">Error</div>
            <div className="text-xs text-slate-400 font-mono break-all">{status.error}</div>
          </div>
        )}
      </div>

      {/* ─── Info ────────────────────────────────────────────────────── */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">About Neo4j</h3>
        <div className="space-y-2 text-xs text-slate-400">
          <p>
            Neo4j provides graph-based memory storage for Tektos, enabling
            relationship-aware retrieval across sessions. It stores agents,
            tasks, skills, and their interconnections as a knowledge graph.
          </p>
          <div className="grid grid-cols-2 gap-2 mt-3">
            <div className="bg-black/30 rounded p-2">
              <span className="text-slate-500">Nodes</span>
              <div className="text-slate-300 font-mono">—</div>
            </div>
            <div className="bg-black/30 rounded p-2">
              <span className="text-slate-500">Relationships</span>
              <div className="text-slate-300 font-mono">—</div>
            </div>
            <div className="bg-black/30 rounded p-2">
              <span className="text-slate-500">Labels</span>
              <div className="text-slate-300 font-mono">—</div>
            </div>
            <div className="bg-black/30 rounded p-2">
              <span className="text-slate-500">Indexes</span>
              <div className="text-slate-300 font-mono">—</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
