/**
 * Tektos-Ultima v1 — PostgreSQL Long-term Memory Panel
 *
 * Displays PostgreSQL long-term and procedural memory backend status:
 * - Connection health, host/port/database
 * - Long-term memory table status
 * - Procedural memory table status
 * - Entry counts
 */

import { useState, useEffect, useCallback } from "react";

interface PostgresStatus {
  status: string;
  database: string;
  host: string | null;
  port: number | null;
  database_name: string | null;
  long_term_connected: boolean;
  procedural_connected: boolean;
  error: string | null;
}

export function PostgresPanel() {
  const [status, setStatus] = useState<PostgresStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/postgres/status");
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error("Failed to load PostgreSQL status:", err);
      setStatus({
        status: "error",
        database: "postgres",
        host: null,
        port: null,
        database_name: null,
        long_term_connected: false,
        procedural_connected: false,
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
        <div className="text-slate-400">Loading PostgreSQL status...</div>
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
          <h2 className="text-lg font-semibold text-white">PostgreSQL Long-term Memory</h2>
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${status.long_term_connected && status.procedural_connected ? "bg-green-400" : status.status === "not_initialized" ? "bg-slate-600" : "bg-red-400"}`} />
            <span className={`text-sm font-medium ${statusColor}`}>{status.status}</span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-xs text-slate-500">Host</span>
            <div className="text-slate-300 font-mono mt-1">{status.host || "—"}</div>
          </div>
          <div>
            <span className="text-xs text-slate-500">Port</span>
            <div className="text-slate-300 font-mono mt-1">{status.port || "—"}</div>
          </div>
          <div>
            <span className="text-xs text-slate-500">Database</span>
            <div className="text-slate-300 font-mono mt-1">{status.database_name || "—"}</div>
          </div>
        </div>

        {status.error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <div className="text-xs text-red-400 font-medium mb-1">Error</div>
            <div className="text-xs text-slate-400 font-mono break-all">{status.error}</div>
          </div>
        )}
      </div>

      {/* ─── Tier Status ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Long-term Memory */}
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-slate-300">Long-term Memory</h3>
            <span className={`text-xs px-2 py-0.5 rounded ${status.long_term_connected ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
              {status.long_term_connected ? "Connected" : "Disconnected"}
            </span>
          </div>
          <div className="space-y-2 text-xs text-slate-400">
            <p>Days-to-permanent memory with JSONB metadata, pgvector semantic search, and W5H1M fields.</p>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div className="bg-black/30 rounded p-2">
                <span className="text-slate-500">Table</span>
                <div className="text-slate-300 font-mono">tektos_long_term_memory</div>
              </div>
              <div className="bg-black/30 rounded p-2">
                <span className="text-slate-500">Vector</span>
                <div className="text-slate-300 font-mono">pgvector</div>
              </div>
            </div>
          </div>
        </div>

        {/* Procedural Memory */}
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-slate-300">Procedural Memory</h3>
            <span className={`text-xs px-2 py-0.5 rounded ${status.procedural_connected ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
              {status.procedural_connected ? "Connected" : "Disconnected"}
            </span>
          </div>
          <div className="space-y-2 text-xs text-slate-400">
            <p>Permanent skills, principles, and wisdom with graph-like edge tables and full-text search.</p>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div className="bg-black/30 rounded p-2">
                <span className="text-slate-500">Table</span>
                <div className="text-slate-300 font-mono">tektos_procedural_memory</div>
              </div>
              <div className="bg-black/30 rounded p-2">
                <span className="text-slate-500">Search</span>
                <div className="text-slate-300 font-mono">tsvector</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
