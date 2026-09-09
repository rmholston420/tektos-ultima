/**
 * Tektos-Ultima v1 — Metabolism Panel
 *
 * Full resource monitoring: GPU (VRAM, power, thermal), system (CPU, memory, disk),
 * context budget, and health assessment with threshold alerts.
 */

import { useState, useEffect, useCallback } from "react";

interface GpuInfo {
  temperature: number;
  utilization: number;
  vram_total_mb: number;
  vram_used_mb: number;
  vram_pct: number;
  power_draw_w: number;
  power_limit_w: number;
  power_pct: number;
  fan_speed: number;
  clock_graphics: number;
  clock_memory: number;
}

interface SystemInfo {
  cpu_percent: number;
  memory_total_mb: number;
  memory_used_mb: number;
  memory_pct: number;
  disk_total_gb: number;
  disk_used_gb: number;
  disk_pct: number;
  disk_free_gb: number;
}

interface ContextBudget {
  current_tokens: number;
  max_tokens: number;
  pct: number;
  remaining_tokens: number;
  alert_level: string;
  recommended_action: string;
}

interface MetabolismState {
  overall_health: string;
  timestamp: string;
  gpu?: GpuInfo;
  system?: SystemInfo;
  context_budget?: ContextBudget;
  inference_latency_ms: number;
  tokens_per_second: number;
  active_sessions: number;
  total_tool_calls: number;
}

const alertColors: Record<string, string> = {
  normal: "text-green-400",
  warning: "text-amber-400",
  critical: "text-orange-400",
  emergency: "text-red-400",
};

const alertBg: Record<string, string> = {
  normal: "bg-green-400/20 border-green-400/30",
  warning: "bg-amber-400/20 border-amber-400/30",
  critical: "bg-orange-400/20 border-orange-400/30",
  emergency: "bg-red-400/20 border-red-400/30",
};

const barColor = (pct: number) => {
  if (pct >= 90) return "bg-red-400";
  if (pct >= 80) return "bg-amber-400";
  return "bg-green-400";
};

export function MetabolismPanel() {
  const [state, setState] = useState<MetabolismState | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMetabolism = useCallback(async () => {
    try {
      const res = await fetch("/api/metabolism");
      const data = await res.json();
      setState(data);
    } catch (err) {
      console.error("Failed to load metabolism:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetabolism();
    const interval = setInterval(fetchMetabolism, 5000);
    return () => clearInterval(interval);
  }, [fetchMetabolism]);

  if (loading && !state) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading metabolism...</div>
      </div>
    );
  }

  if (!state) return null;

  const health = state.overall_health;
  const gpu = state.gpu;
  const sys = state.system;
  const ctx = state.context_budget;

  const formatTokens = (n: number) => {
    if (n >= 1024) return `${(n / 1024).toFixed(1)}k`;
    return n.toString();
  };

  return (
    <div className="space-y-6">
      {/* Health Banner */}
      <div className={`border rounded-lg p-4 ${alertBg[health] || alertBg.normal}`}>
        <div className="flex items-center gap-3">
          <span className={`text-2xl ${alertColors[health]}`}>
            {health === "normal" ? "✓" : health === "warning" ? "⚠" : health === "critical" ? "⛔" : "🚨"}
          </span>
          <div>
            <h2 className={`text-lg font-semibold ${alertColors[health]} capitalize`}>
              {health}
            </h2>
            <p className="text-xs text-slate-400">
              Updated {new Date(state.timestamp).toLocaleTimeString()}
            </p>
          </div>
        </div>
      </div>

      {/* GPU Metrics */}
      {gpu && (
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <h3 className="text-sm font-medium text-slate-300 mb-4">GPU — RTX 5090</h3>
          <div className="grid grid-cols-2 gap-4">
            {/* Temperature */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-400">Temperature</span>
                <span className={`text-sm font-mono ${gpu.temperature >= 82 ? "text-red-400" : gpu.temperature >= 70 ? "text-amber-400" : "text-slate-200"}`}>
                  {gpu.temperature}°C
                </span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${gpu.temperature >= 90 ? "bg-red-400" : gpu.temperature >= 82 ? "bg-amber-400" : "bg-green-400"}`}
                  style={{ width: `${Math.min(gpu.temperature / 100 * 100, 100)}%` }}
                />
              </div>
            </div>

            {/* VRAM */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-400">VRAM</span>
                <span className="text-sm font-mono text-slate-200">
                  {formatTokens(gpu.vram_used_mb)} / {formatTokens(gpu.vram_total_mb)} MB ({gpu.vram_pct.toFixed(0)}%)
                </span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div className={`h-2 rounded-full transition-all ${barColor(gpu.vram_pct)}`} style={{ width: `${gpu.vram_pct}%` }} />
              </div>
            </div>

            {/* Power */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-400">Power</span>
                <span className="text-sm font-mono text-slate-200">
                  {gpu.power_draw_w.toFixed(0)}W / {gpu.power_limit_w}W ({gpu.power_pct.toFixed(0)}%)
                </span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div className="h-2 rounded-full bg-blue-400 transition-all" style={{ width: `${gpu.power_pct}%` }} />
              </div>
            </div>

            {/* Utilization */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-400">Utilization</span>
                <span className="text-sm font-mono text-slate-200">{gpu.utilization}%</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div className="h-2 rounded-full bg-purple-400 transition-all" style={{ width: `${gpu.utilization}%` }} />
              </div>
            </div>
          </div>

          {/* Thermal Notes */}
          {gpu.temperature >= 82 && (
            <div className="mt-3 p-2 bg-red-400/10 border border-red-400/30 rounded text-xs text-red-400">
              ⚠ Thermal cooling trigger active ({gpu.temperature}°C ≥ 82°C) — fan boost engaged
            </div>
          )}
          {gpu.temperature >= 85 && (
            <div className="mt-2 p-2 bg-red-500/20 border border-red-500/50 rounded text-xs text-red-400">
              🚨 Emergency cutoff zone — reduce workload
            </div>
          )}
        </div>
      )}

      {/* System Metrics */}
      {sys && (
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <h3 className="text-sm font-medium text-slate-300 mb-4">System</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-400">CPU</span>
                <span className="text-sm font-mono text-slate-200">{sys.cpu_percent}%</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div className={`h-2 rounded-full ${barColor(sys.cpu_percent)}`} style={{ width: `${sys.cpu_percent}%` }} />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-400">Memory</span>
                <span className="text-sm font-mono text-slate-200">{sys.memory_pct.toFixed(0)}%</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div className={`h-2 rounded-full ${barColor(sys.memory_pct)}`} style={{ width: `${sys.memory_pct}%` }} />
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-slate-400">Disk</span>
                <span className="text-sm font-mono text-slate-200">{sys.disk_pct.toFixed(0)}%</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div className={`h-2 rounded-full ${barColor(sys.disk_pct)}`} style={{ width: `${sys.disk_pct}%` }} />
              </div>
            </div>
          </div>
          <div className="mt-3 text-xs text-slate-500">
            RAM: {formatTokens(sys.memory_used_mb)} / {formatTokens(sys.memory_total_mb)} MB
            {sys.disk_free_gb > 0 && ` · Disk: ${sys.disk_free_gb.toFixed(1)} GB free`}
          </div>
        </div>
      )}

      {/* Context Budget */}
      {ctx && (
        <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
          <h3 className="text-sm font-medium text-slate-300 mb-4">Context Budget</h3>
          <div className="flex items-center justify-between mb-2">
            <span className={`text-xs ${alertColors[ctx.alert_level]}`}>
              {ctx.alert_level.toUpperCase()}
            </span>
            <span className="text-sm font-mono text-slate-200">
              {formatTokens(ctx.current_tokens)} / {formatTokens(ctx.max_tokens)} tokens
            </span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-3 mb-2">
            <div className={`h-3 rounded-full transition-all ${barColor(ctx.pct)}`} style={{ width: `${Math.min(ctx.pct, 100)}%` }} />
          </div>
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>{formatTokens(ctx.remaining_tokens)} remaining</span>
            <span>Action: {ctx.recommended_action.replace(/_/g, " ")}</span>
          </div>
        </div>
      )}

      {/* Activity Stats */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Activity</h3>
        <div className="grid grid-cols-4 gap-4 text-center">
          <div>
            <div className="text-lg font-bold text-white">{state.active_sessions}</div>
            <div className="text-xs text-slate-400">Sessions</div>
          </div>
          <div>
            <div className="text-lg font-bold text-white">{state.total_tool_calls}</div>
            <div className="text-xs text-slate-400">Tool Calls</div>
          </div>
          <div>
            <div className="text-lg font-bold text-white">{state.inference_latency_ms.toFixed(0)}ms</div>
            <div className="text-xs text-slate-400">Latency</div>
          </div>
          <div>
            <div className="text-lg font-bold text-white">{state.tokens_per_second.toFixed(0)}</div>
            <div className="text-xs text-slate-400">Tokens/sec</div>
          </div>
        </div>
      </div>
    </div>
  );
}
