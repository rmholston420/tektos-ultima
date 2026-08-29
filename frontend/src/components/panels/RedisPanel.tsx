/**
 * Tektos-Ultima v1 — Redis Working Memory Panel
 *
 * Displays Redis working and sensory memory backend status:
 * - Connection health, host/port
 * - Sensory memory stream status
 * - Working memory sorted set status
 * - Ping connectivity
 */

import { useState, useEffect, useCallback } from "react";

interface RedisStatus {
  status: string;
  database: string;
  host: string | null;
  port: number | null;
  sensory_connected: boolean;
  working_connected: boolean;
  ping_ok: boolean;
  error: string | null;
}

export function RedisPanel() {
  const [status, setStatus] = useState<RedisStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/redis/status");
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error("Failed to load Redis status:", err);
      setStatus({
        status: "error",
        database: "redis",
        host: null,
        port: null,
        sensory_connected: false,
        working_connected: false,
        ping_ok: false,
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
        <div className="text-slate-400">Loading Redis status...</div>
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
          <h2 className="text-lg font-semibold text-white">Redis Working Memory</h2>
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${status.ping_ok ? "bg-green-400" : status.status === "not_initialized" ? "bg-slate-600" : "bg-red-400"}`} />
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
            <span className="text-xs text-slate-500">Ping</span>
            <div className={`mt-1 ${status.ping_ok ? "text-green-400" : "text-red-400"}`}>
              {status.ping_ok ? "OK" : "Failed"}
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

      {/* ─── Tier Status ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Sensory Memory */}
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-slate-300">Sensory Memory</h3>
            <span className={`text-xs px-2 py-0.5 rounded ${status.sensory_connected ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
              {status.sensory_connected ? "Connected" : "Disconnected"}
            </span>
          </div>
          <div className="space-y-2 text-xs text-slate-400">
            <p>100ms–4s event buffer via Redis Streams with TTL-based auto-decay and attention scores.</p>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div className="bg-black/30 rounded p-2">
                <span className="text-slate-500">Structure</span>
                <div className="text-slate-300 font-mono">Stream</div>
              </div>
              <div className="bg-black/30 rounded p-2">
                <span className="text-slate-500">TTL</span>
                <div className="text-slate-300 font-mono">4s</div>
              </div>
            </div>
          </div>
        </div>

        {/* Working Memory */}
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-slate-300">Working Memory</h3>
            <span className={`text-xs px-2 py-0.5 rounded ${status.working_connected ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
              {status.working_connected ? "Connected" : "Disconnected"}
            </span>
          </div>
          <div className="space-y-2 text-xs text-slate-400">
            <p>Seconds–minutes, 7±2 items via Sorted Sets with priority-based eviction (Miller's Law).</p>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div className="bg-black/30 rounded p-2">
                <span className="text-slate-500">Structure</span>
                <div className="text-slate-300 font-mono">Sorted Set</div>
              </div>
              <div className="bg-black/30 rounded p-2">
                <span className="text-slate-500">Capacity</span>
                <div className="text-slate-300 font-mono">7 items</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
