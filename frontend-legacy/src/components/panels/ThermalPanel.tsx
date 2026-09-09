/**
 * Tektos-Ultima v1 — Thermal Regulation Panel
 *
 * Dashboard for the thermal regulation system:
 * - GPU/CPU temperature, power, clock monitoring
 * - PID regulation status and action history
 * - Health score with threshold alerts
 * - Manual reset to optimal settings
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface GpuInfo {
  temperature: number;
  power_limit: number;
  clock_mhz: number;
  action: string;
  reason: string;
}

interface CpuInfo {
  temperature: number;
  status: string;
  action: string;
}

interface ThermalSnapshot {
  timestamp: string;
  gpu: GpuInfo;
  cpu: CpuInfo;
  regulation_count: number;
  history: Array<{
    timestamp: string;
    gpu_temp: number;
    cpu_temp: number;
    power: number;
    clock: number;
    action: string;
  }>;
}

interface ThermalState {
  snapshot: ThermalSnapshot | null;
  healthScore: number | null;
  loading: boolean;
  error: string | null;
}

const tempColor = (t: number): string => {
  if (t >= 85) return "text-red-400";
  if (t >= 75) return "text-orange-400";
  if (t >= 70) return "text-amber-400";
  return "text-green-400";
};

const tempBarColor = (t: number): string => {
  if (t >= 85) return "bg-red-400";
  if (t >= 75) return "bg-orange-400";
  if (t >= 70) return "bg-amber-400";
  return "bg-green-400";
};

const actionColors: Record<string, string> = {
  throttle: "text-red-400",
  relax: "text-blue-400",
  stable: "text-green-400",
  none: "text-slate-400",
};

export function ThermalPanel() {
  const [state, setState] = useState<ThermalState>({
    snapshot: null,
    healthScore: null,
    loading: true,
    error: null,
  });
  const [resetting, setResetting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [snapRes, healthRes] = await Promise.all([
        fetch("/api/thermal/status"),
        fetch("/api/thermal/health"),
      ]);

      if (!snapRes.ok || !healthRes.ok) {
        setState((prev) => ({
          ...prev,
          loading: false,
          error: "Failed to fetch thermal data",
        }));
        return;
      }

      const snapshot = await snapRes.json();
      const health = await healthRes.json();

      setState({
        snapshot,
        healthScore: health.health_score ?? null,
        loading: false,
        error: null,
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : "Unknown error",
      }));
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleReset = async () => {
    setResetting(true);
    try {
      const res = await fetch("/api/thermal/reset", { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      fetchData();
    } catch (err) {
      setState((prev) => ({
        ...prev,
        error: err instanceof Error ? err.message : "Reset failed",
      }));
    } finally {
      setResetting(false);
    }
  };

  if (state.loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Loading thermal status...</div>
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-400 text-sm">{state.error}</div>
      </div>
    );
  }

  const snap = state.snapshot;
  if (!snap) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Thermal monitor not initialized</div>
      </div>
    );
  }

  const gpu = snap.gpu;
  const cpu = snap.cpu;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">🌡️</span>
          <h2 className="text-sm font-semibold text-text-primary">Thermal Regulation</h2>
          <span className="text-xs text-text-muted">Target: 72°C</span>
        </div>
        <div className="flex items-center gap-3">
          {state.healthScore !== null && (
            <div className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${
                state.healthScore >= 0.9 ? "bg-green-400" :
                state.healthScore >= 0.7 ? "bg-amber-400" :
                "bg-red-400"
              }`} />
              <span className="text-xs font-mono text-text-primary">
                Health: {(state.healthScore * 100).toFixed(0)}%
              </span>
            </div>
          )}
          <button
            onClick={handleReset}
            disabled={resetting}
            className="px-2.5 py-1 text-xs font-medium rounded-md bg-surface-hover text-text-muted hover:text-text-primary transition-all disabled:opacity-50"
          >
            {resetting ? "Resetting..." : "Reset Optimal"}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* GPU Metrics */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">GPU — RTX 5090</h3>
          <div className="grid grid-cols-2 gap-4">
            {/* Temperature */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-muted">Temperature</span>
                <span className={`text-sm font-mono ${tempColor(gpu.temperature)}`}>
                  {gpu.temperature.toFixed(1)}°C
                </span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${tempBarColor(gpu.temperature)}`}
                  style={{ width: `${Math.min(gpu.temperature / 100 * 100, 100)}%` }}
                />
              </div>
            </div>

            {/* Power */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-muted">Power</span>
                <span className="text-sm font-mono text-slate-200">{gpu.power_limit}W</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div className="h-2 rounded-full bg-blue-400 transition-all" style={{ width: `${Math.min(gpu.power_limit / 600 * 100, 100)}%` }} />
              </div>
            </div>

            {/* Clock */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-muted">Clock</span>
                <span className="text-sm font-mono text-slate-200">{gpu.clock_mhz} MHz</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div className="h-2 rounded-full bg-purple-400 transition-all" style={{ width: `${Math.min(gpu.clock_mhz / 2500 * 100, 100)}%` }} />
              </div>
            </div>

            {/* Action */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-muted">Action</span>
                <span className={`text-sm font-mono capitalize ${actionColors[gpu.action] || "text-text-muted"}`}>
                  {gpu.action}
                </span>
              </div>
              <div className="text-xs text-text-muted truncate" title={gpu.reason}>
                {gpu.reason}
              </div>
            </div>
          </div>
        </div>

        {/* CPU Metrics */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">CPU</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-muted">Temperature</span>
                <span className={`text-sm font-mono ${tempColor(cpu.temperature)}`}>
                  {cpu.temperature > 0 ? `${cpu.temperature.toFixed(1)}°C` : "—"}
                </span>
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-text-muted">Status</span>
                <span className="text-sm font-mono text-slate-200 capitalize">{cpu.status}</span>
              </div>
            </div>
          </div>
          {cpu.action && (
            <div className="mt-2 text-xs text-text-muted">{cpu.action}</div>
          )}
        </div>

        {/* Regulation Stats */}
        <div className="bg-surface rounded-lg p-3 border border-border">
          <h3 className="text-xs font-semibold text-text-muted mb-3">Regulation</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-bg-3 rounded-md p-2 text-center">
              <div className="text-lg font-bold text-text-primary">{snap.regulation_count}</div>
              <div className="text-xs text-text-muted">Cycles</div>
            </div>
            <div className="bg-bg-3 rounded-md p-2 text-center">
              <div className="text-lg font-bold text-text-primary">
                {new Date(snap.timestamp).toLocaleTimeString()}
              </div>
              <div className="text-xs text-text-muted">Last Update</div>
            </div>
          </div>
        </div>

        {/* History */}
        {snap.history.length > 0 && (
          <div className="bg-surface rounded-lg p-3 border border-border">
            <h3 className="text-xs font-semibold text-text-muted mb-3">Recent History</h3>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {[...snap.history].reverse().slice(0, 10).map((entry, i) => (
                <div key={i} className="flex items-center justify-between text-xs py-1 border-b border-border/50 last:border-0">
                  <span className="text-text-muted font-mono">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                  <span className={`font-mono ${tempColor(entry.gpu_temp)}`}>{entry.gpu_temp.toFixed(1)}°C</span>
                  <span className="text-text-muted">{entry.cpu_temp.toFixed(1)}°C</span>
                  <span className="font-mono text-slate-300">{entry.power}W</span>
                  <span className={`font-mono capitalize ${actionColors[entry.action] || "text-text-muted"}`}>{entry.action}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
