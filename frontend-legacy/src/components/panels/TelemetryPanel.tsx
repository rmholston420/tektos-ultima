/**
 * Tektos-Ultima v1 — Telemetry Panel (Real Data)
 *
 * Real-time GPU/CPU temperature, utilization, power draw, fan speed,
 * RAM, and disk metrics wired to live /api/telemetry endpoint.
 * Color-coded status with amber/red thresholds for thermal warnings.
 *
 * Exemplar pattern: Real-time metrics with trend history from live hardware.
 */

"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { api, type TelemetryData } from "@/lib/api";

// ─── Types ───────────────────────────────────────────────────────────────────

interface MetricGaugeProps {
  label: string;
  value: number;
  max: number;
  unit: string;
  warningThreshold: number;
  dangerThreshold: number;
  size?: "sm" | "md";
  color?: string;
}

interface SparklineProps {
  data: number[];
  width: number;
  height: number;
  color: string;
  warningThreshold?: number;
}

// ─── Sparkline Component ─────────────────────────────────────────────────────

function Sparkline({ data, width, height, color, warningThreshold }: SparklineProps) {
  const points = useMemo(() => {
    if (data.length < 2) return "";
    const max = Math.max(...data, warningThreshold || Infinity);
    const min = Math.min(...data);
    const range = max - min || 1;
    return data
      .map((v, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((v - min) / range) * height;
        return `${x},${y}`;
      })
      .join(" ");
  }, [data, width, height, warningThreshold]);

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {warningThreshold && (
        <line
          x1={0}
          y1={height - (warningThreshold / Math.max(...data)) * height}
          x2={width}
          y2={height - (warningThreshold / Math.max(...data)) * height}
          stroke={color}
          strokeWidth="1"
          strokeDasharray="4 4"
          opacity="0.5"
        />
      )}
    </svg>
  );
}

// ─── Metric Gauge Component ──────────────────────────────────────────────────

function MetricGauge({
  label,
  value,
  max,
  unit,
  warningThreshold,
  dangerThreshold,
  size = "sm",
  color,
}: MetricGaugeProps) {
  const percentage = (value / max) * 100;
  const isWarning = value >= warningThreshold;
  const isDanger = value >= dangerThreshold;

  let statusColor = color;
  if (isDanger) statusColor = "#ef4444";
  else if (isWarning) statusColor = "#f59e0b";

  const gaugeWidth = size === "md" ? 64 : 48;
  const gaugeHeight = size === "md" ? 16 : 12;
  const radius = size === "md" ? 6 : 4;

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-muted">{label}</span>
        <span className={`text-xs font-mono ${isDanger ? "text-status-error" : isWarning ? "text-status-warning" : "text-text-secondary"}`}>
          {value.toFixed(1)}{unit}
        </span>
      </div>
      <div className="relative">
        <svg width={gaugeWidth} height={gaugeHeight} className="overflow-visible">
          <rect
            x="0"
            y="0"
            width={gaugeWidth}
            height={gaugeHeight}
            rx={radius}
            fill="var(--color-bg-4)"
          />
          <rect
            x="0"
            y="0"
            width={(percentage / 100) * gaugeWidth}
            height={gaugeHeight}
            rx={radius}
            fill={statusColor}
            style={{ transition: "width 0.3s ease" }}
          />
        </svg>
      </div>
    </div>
  );
}

// ─── Telemetry Panel ─────────────────────────────────────────────────────────

export function TelemetryPanel() {
  const [data, setData] = useState<TelemetryData | null>(null);
  const [history, setHistory] = useState<TelemetryData[]>([]);
  const [error, setError] = useState<string | null>(null);
  const maxHistory = 30;

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch("/api/telemetry");
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        const raw: TelemetryData = await res.json();
        setData(raw);
        setHistory((prev) => [...prev.slice(-maxHistory + 1), raw]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch telemetry");
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, []);

  const sparklineWidth = 120;
  const sparklineHeight = 32;

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${error ? "bg-status-error animate-pulse" : "bg-status-success"}`} />
          <h3 className="text-sm font-semibold text-text-primary">System Telemetry</h3>
        </div>
        {data && (
          <span className="text-xs text-text-muted font-mono">
            {new Date(data.timestamp * 1000).toLocaleTimeString()}
          </span>
        )}
      </div>

      {error ? (
        <div className="p-3 rounded-md bg-status-error/10 border border-status-error/20">
          <p className="text-xs text-status-error">{error}</p>
        </div>
      ) : data ? (
        <>
          {/* GPU Section */}
          <div className="space-y-2">
            <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider">GPU</h4>
            <div className="grid grid-cols-2 gap-3">
              <MetricGauge
                label="Temperature"
                value={data.gpu.temperature}
                max={100}
                unit="°C"
                warningThreshold={75}
                dangerThreshold={85}
                color="#3b82f6"
              />
              <MetricGauge
                label="Utilization"
                value={data.gpu.utilization}
                max={100}
                unit="%"
                warningThreshold={85}
                dangerThreshold={95}
                color="#10b981"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <MetricGauge
                label="VRAM Used"
                value={data.gpu.memory_used}
                max={data.gpu.memory_total}
                unit=" MB"
                warningThreshold={data.gpu.memory_total * 0.85}
                dangerThreshold={data.gpu.memory_total * 0.95}
                color="#06b6d4"
              />
              <MetricGauge
                label="Power Draw"
                value={data.gpu.power_draw}
                max={data.gpu.power_limit}
                unit=" W"
                warningThreshold={data.gpu.power_limit * 0.9}
                dangerThreshold={data.gpu.power_limit}
                color="#f97316"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <MetricGauge
                label="Clocks (GPU)"
                value={data.gpu.clocks_graphics}
                max={3000}
                unit=" MHz"
                warningThreshold={0}
                dangerThreshold={0}
                color="#8b5cf6"
              />
              <MetricGauge
                label="Clocks (Mem)"
                value={data.gpu.clocks_memory}
                max={20000}
                unit=" MHz"
                warningThreshold={0}
                dangerThreshold={0}
                color="#14b8a6"
              />
            </div>
            <Sparkline
              data={history.map((h) => h.gpu.temperature)}
              width={sparklineWidth}
              height={sparklineHeight}
              color="#3b82f6"
              warningThreshold={75}
            />
          </div>

          {/* CPU Section */}
          <div className="space-y-2">
            <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider">CPU</h4>
            <div className="grid grid-cols-2 gap-3">
              <MetricGauge
                label="Utilization"
                value={data.system.cpu_util}
                max={100}
                unit="%"
                warningThreshold={80}
                dangerThreshold={90}
                color="#8b5cf6"
              />
              <MetricGauge
                label="RAM Used"
                value={data.system.mem_used_gb}
                max={data.system.mem_total_gb}
                unit={` / ${data.system.mem_total_gb} GB`}
                warningThreshold={data.system.mem_total_gb * 0.8}
                dangerThreshold={data.system.mem_total_gb * 0.9}
                color="#06b6d4"
              />
            </div>
            <MetricGauge
              label="RAM Utilization"
              value={data.system.mem_percent}
              max={100}
              unit="%"
              warningThreshold={80}
              dangerThreshold={90}
              color="#06b6d4"
            />
            <Sparkline
              data={history.map((h) => h.system.cpu_util)}
              width={sparklineWidth}
              height={sparklineHeight}
              color="#8b5cf6"
            />
          </div>

          {/* Storage */}
          <div className="space-y-2">
            <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider">Storage</h4>
            <MetricGauge
              label="Disk Used"
              value={data.system.disk_used_gb}
              max={data.system.disk_total_gb}
              unit={` / ${data.system.disk_total_gb.toFixed(0)} GB`}
              warningThreshold={data.system.disk_total_gb * 0.8}
              dangerThreshold={data.system.disk_total_gb * 0.9}
              color="#ec4899"
            />
            <MetricGauge
              label="Disk Utilization"
              value={data.system.disk_percent}
              max={100}
              unit="%"
              warningThreshold={80}
              dangerThreshold={90}
              color="#ec4899"
            />
          </div>

          {/* Fan Speed */}
          <div className="space-y-2">
            <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider">Cooling</h4>
            <MetricGauge
              label="Fan Speed"
              value={data.gpu.fan_speed}
              max={100}
              unit="%"
              warningThreshold={80}
              dangerThreshold={95}
              color="#14b8a6"
            />
          </div>
        </>
      ) : (
        <div className="flex items-center justify-center h-32">
          <div className="animate-pulse text-text-muted text-sm">Loading telemetry...</div>
        </div>
      )}
    </div>
  );
}
