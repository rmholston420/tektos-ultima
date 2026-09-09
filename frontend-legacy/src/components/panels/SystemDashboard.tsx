/**
 * Tektos-Ultima v1 — System Dashboard (Real Data)
 *
 * Real-time system monitoring wired to backend API with glassmorphism design,
 * animated transitions, and proper data loading states.
 */

"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";

interface TelemetryPoint {
  time: number;
  gpuTemp: number;
  gpuUtil: number;
  gpuMemUsed: number;
  gpuMemTotal: number;
  powerDraw: number;
  cpuUtil: number;
  ramUsed: number;
  ramTotal: number;
  fanSpeed: number;
  diskPercent: number;
}

interface SystemHealth {
  status: string;
  uptime: string;
  sessionsActive: number;
  sessionsTotal: number;
  model: string;
  gpuModel: string;
  cpuModel: string;
  ramTotal: number;
  ramUsed: number;
}

// ─── Animated Sparkline ──────────────────────────────────────────────────────

function AnimatedSparkline({
  data,
  color,
  height = 40,
  warningThreshold,
  dangerThreshold,
}: {
  data: number[];
  color: string;
  height?: number;
  warningThreshold?: number;
  dangerThreshold?: number;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [pathD, setPathD] = useState("");
  const [areaD, setAreaD] = useState("");

  useEffect(() => {
    if (!Array.isArray(data) || data.length < 2 || !svgRef.current) return;
    const w = svgRef.current.clientWidth || 200;
    const max = Math.max(...data, warningThreshold || Infinity, dangerThreshold || Infinity) * 1.1;
    const min = Math.min(...data, 0);
    const range = max - min || 1;

    const points = data.map((v, i) => ({
      x: (i / (data.length - 1)) * w,
      y: height - ((v - min) / range) * height,
    }));

    const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
    const areaPath = `${linePath} L${points[points.length - 1].x},${height} L${points[0].x},${height} Z`;

    setPathD(linePath);
    setAreaD(areaPath);
  }, [data, height, warningThreshold, dangerThreshold]);

  let statusColor = color;
  const lastVal = data[data.length - 1] ?? 0;
  if (dangerThreshold && lastVal >= dangerThreshold) statusColor = "#ef4444";
  else if (warningThreshold && lastVal >= warningThreshold) statusColor = "#f59e0b";

  return (
    <svg ref={svgRef} className="w-full" height={height} style={{ overflow: "visible" }}>
      <defs>
        <linearGradient id={`spark-grad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={statusColor} stopOpacity="0.3" />
          <stop offset="100%" stopColor={statusColor} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#spark-grad-${color.replace("#", "")})`} />
      <path d={pathD} fill="none" stroke={statusColor} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <animate attributeName="stroke-dashoffset" from="1000" to="0" dur="0.5s" fill="freeze" />
      </path>
      {warningThreshold && (() => {
        const maxVal = Math.max(...data, warningThreshold, dangerThreshold || 0) * 1.1;
        const y = height - (warningThreshold / maxVal) * height;
        return <line x1="0" y1={y} x2="100%" y2={y} stroke={statusColor} strokeWidth="1" strokeDasharray="4 4" opacity="0.3" />;
      })()}
    </svg>
  );
}

// ─── Glass Panel ─────────────────────────────────────────────────────────────

function GlassPanel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 shadow-lg transition-all duration-300 hover:bg-white/10 hover:scale-[1.01] ${className}`}>
      {children}
    </div>
  );
}

// ─── Metric Card ─────────────────────────────────────────────────────────────

function MetricCard({
  label,
  value,
  unit,
  icon,
  color = "#3b82f6",
  trend,
}: {
  label: string;
  value: string;
  unit: string;
  icon: React.ReactNode;
  color?: string;
  trend?: "up" | "down" | "stable";
}) {
  return (
    <GlassPanel className="p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}20` }}>
          <div style={{ color }}>{icon}</div>
        </div>
        {trend && (
          <span className={`text-xs font-medium ${trend === "up" ? "text-status-warning" : trend === "down" ? "text-status-success" : "text-text-muted"}`}>
            {trend === "up" ? "↑" : trend === "down" ? "↓" : "→"}
          </span>
        )}
      </div>
      <div className="mt-1">
        <div className="text-2xl font-bold text-text-primary tracking-tight">{value}</div>
        <div className="text-xs text-text-muted mt-0.5">{label} · {unit}</div>
      </div>
    </GlassPanel>
  );
}

// ─── Gauge Ring ──────────────────────────────────────────────────────────────

function GaugeRing({
  value,
  max,
  size = 80,
  strokeWidth = 6,
  color,
  label,
  unit,
}: {
  value: number;
  max: number;
  size?: number;
  strokeWidth?: number;
  color: string;
  label: string;
  unit: string;
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const percentage = Math.min(value / max, 1);
  const offset = circumference * (1 - percentage);

  let statusColor = color;
  if (percentage > 0.85) statusColor = "#ef4444";
  else if (percentage > 0.75) statusColor = "#f59e0b";

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth={strokeWidth} />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={statusColor}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.5s ease, stroke 0.3s ease" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold text-text-primary">{value.toFixed(0)}</span>
          <span className="text-xs text-text-muted">{unit}</span>
        </div>
      </div>
      <span className="text-xs text-text-muted">{label}</span>
    </div>
  );
}

// ─── Loading Skeleton ────────────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 bg-surface/50 rounded-lg w-48" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 bg-surface/50 rounded-2xl" />
        ))}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-32 bg-surface/50 rounded-2xl" />
        ))}
      </div>
    </div>
  );
}

// ─── Main Dashboard ──────────────────────────────────────────────────────────

export function SystemDashboard() {
  const [telemetryData, setTelemetryData] = useState<TelemetryPoint[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(new Date());
  const maxHistory = 50;

  // Real-time clock
  useEffect(() => {
    const interval = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Fetch telemetry from /api/telemetry (replaces simulation)
  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch("/api/telemetry");
        if (res.ok) {
          const raw = await res.json();
          const gpu = raw.gpu || {};
          const system = raw.system || {};
          const now = Date.now();
          const newPoint: TelemetryPoint = {
            time: now,
            gpuTemp: gpu.temperature || 0,
            gpuUtil: gpu.utilization || 0,
            gpuMemUsed: gpu.memory_used || 0,
            gpuMemTotal: gpu.memory_total || 1,
            powerDraw: gpu.power_draw || 0,
            cpuUtil: system.cpu_util || 0,
            ramUsed: system.mem_used_gb || 0,
            ramTotal: system.mem_total_gb || 1,
            fanSpeed: gpu.fan_speed || 0,
            diskPercent: system.disk_percent || 0,
          };

          setTelemetryData((prev) => {
            const updated = [...prev, newPoint];
            return updated.slice(-maxHistory);
          });
        }
      } catch {
        // Backend unavailable — keep last known data
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 2000);
    setLoading(false);
    return () => clearInterval(interval);
  }, []);

  const latest = telemetryData[telemetryData.length - 1] || {
    gpuTemp: 0, gpuUtil: 0, gpuMemUsed: 0, gpuMemTotal: 1,
    cpuUtil: 0, ramUsed: 0, ramTotal: 1, fanSpeed: 0, powerDraw: 0, diskPercent: 0,
  };

  if (loading) return <LoadingSkeleton />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-xl font-semibold text-text-primary">System Dashboard</h2>
          <div className="text-xs text-text-muted/70 font-mono">
            {currentTime.toLocaleTimeString()}
          </div>
        </div>
        <p className="text-sm text-text-muted">
          {currentTime.toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
        </p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="GPU Temperature"
          value={latest.gpuTemp.toFixed(1)}
          unit="°C"
          icon={<svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1z" /></svg>}
          color="#3b82f6"
          trend={latest.gpuTemp > 75 ? "up" : "stable"}
        />
        <MetricCard
          label="GPU Utilization"
          value={latest.gpuUtil.toFixed(0)}
          unit="%"
          icon={<svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" /></svg>}
          color="#10b981"
          trend={latest.gpuUtil > 80 ? "up" : "stable"}
        />
        <MetricCard
          label="Power Draw"
          value={latest.powerDraw.toFixed(0)}
          unit="W"
          icon={<svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clipRule="evenodd" /></svg>}
          color="#f97316"
          trend={latest.powerDraw > 380 ? "up" : "stable"}
        />
        <MetricCard
          label="RAM Usage"
          value={latest.ramUsed.toFixed(1)}
          unit={`${latest.ramTotal}GB`}
          icon={<svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" /></svg>}
          color="#8b5cf6"
          trend={latest.ramUsed > 24 ? "up" : "stable"}
        />
      </div>

      {/* Gauges Row */}
      <GlassPanel className="p-6">
        <h3 className="text-sm font-medium text-text-muted mb-4">Real-time Gauges</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
          <GaugeRing value={latest.gpuTemp} max={100} color="#3b82f6" label="GPU Temp" unit="°C" />
          <GaugeRing value={latest.gpuUtil} max={100} color="#10b981" label="GPU Util" unit="%" />
          <GaugeRing value={latest.cpuUtil} max={100} color="#f59e0b" label="CPU Util" unit="%" />
          <GaugeRing value={latest.diskPercent} max={100} color="#8b5cf6" label="Disk" unit="%" />
        </div>
      </GlassPanel>

      {/* Sparklines */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <GlassPanel className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">GPU Temperature History</h3>
          <AnimatedSparkline data={telemetryData.map((d) => d.gpuTemp)} color="#3b82f6" warningThreshold={75} dangerThreshold={85} />
        </GlassPanel>
        <GlassPanel className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">GPU Utilization History</h3>
          <AnimatedSparkline data={telemetryData.map((d) => d.gpuUtil)} color="#10b981" warningThreshold={85} dangerThreshold={95} />
        </GlassPanel>
        <GlassPanel className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">CPU Utilization History</h3>
          <AnimatedSparkline data={telemetryData.map((d) => d.cpuUtil)} color="#8b5cf6" warningThreshold={80} dangerThreshold={90} />
        </GlassPanel>
        <GlassPanel className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">Power Draw History</h3>
          <AnimatedSparkline data={telemetryData.map((d) => d.powerDraw)} color="#f97316" warningThreshold={380} dangerThreshold={420} />
        </GlassPanel>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GlassPanel className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">System Status</h3>
          <div className="space-y-3">
            {[
              { label: "GPU Health", status: latest.gpuTemp < 75 ? "healthy" : latest.gpuTemp < 80 ? "warning" : "critical" },
              { label: "Thermal Status", status: latest.gpuTemp < 70 ? "healthy" : latest.gpuTemp < 80 ? "warning" : "critical" },
              { label: "Fan Speed", status: latest.fanSpeed > 1500 ? "healthy" : "warning" },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between">
                <span className="text-sm text-text-secondary">{item.label}</span>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  item.status === "healthy" ? "bg-status-success/20 text-status-success" :
                  item.status === "warning" ? "bg-status-warning/20 text-status-warning" :
                  "bg-status-error/20 text-status-error"
                }`}>
                  {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
                </span>
              </div>
            ))}
          </div>
        </GlassPanel>

        <GlassPanel className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">System Info</h3>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-text-muted">Model</span>
              <span className="text-text-primary font-mono">{systemHealth?.model || "Qwen3.6-35B"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">GPU</span>
              <span className="text-text-primary font-mono">{systemHealth?.gpuModel || "RTX 4090"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">CPU</span>
              <span className="text-text-primary font-mono">{systemHealth?.cpuModel || "Ryzen 9 7950X"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">RAM</span>
              <span className="text-text-primary font-mono">{systemHealth?.ramUsed ? `${systemHealth.ramUsed.toFixed(1)}/${systemHealth.ramTotal}GB` : "--"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-muted">Sessions</span>
              <span className="text-text-primary font-mono">{systemHealth?.sessionsActive ?? 0} active</span>
            </div>
          </div>
        </GlassPanel>

        <GlassPanel className="p-4">
          <h3 className="text-sm font-medium text-text-muted mb-3">Thermal Profile</h3>
          <div className="flex items-end gap-1 h-20">
            {[...Array(20)].map((_, i) => {
              const idx = telemetryData.length - 20 + i;
              const val = idx >= 0 ? telemetryData[idx].gpuTemp : 50;
              const height = (val / 100) * 100;
              return (
                <div
                  key={i}
                  className="flex-1 rounded-t transition-all duration-300"
                  style={{
                    height: `${height}%`,
                    backgroundColor: val > 80 ? "#ef4444" : val > 70 ? "#f59e0b" : "#3b82f6",
                    opacity: 0.3 + (height / 100) * 0.7,
                  }}
                />
              );
            })}
          </div>
          <div className="flex justify-between mt-2">
            <span className="text-xs text-text-muted">60s ago</span>
            <span className="text-xs text-text-muted">Now</span>
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
