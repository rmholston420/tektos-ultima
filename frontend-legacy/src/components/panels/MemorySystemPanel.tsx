/**
 * Tektos-Ultima v1 — Memory System Panel
 *
 * Visualizes the 4-tier memory architecture:
 * - Sensory (Redis) — short-term working memory
 * - Long-term (PostgreSQL) — persistent knowledge
 * - Procedural (Neo4j) — knowledge graphs
 * - Backup (SQLite) — redundancy
 *
 * Design: Tiered visualization with capacity gauges and flow arrows.
 * Shows memory size, capacity, and utilization percentages.
 */

"use client";

import React, { useState, useEffect } from "react";
import { api, type MemorySystemStats } from "@/lib/api";

interface TierCardProps {
  name: string;
  storage: string;
  used: number;
  capacity: number;
  utilization: number;
  color: string;
  description: string;
  tier: number;
}

function TierCard({ name, storage, used, capacity, utilization, color, description, tier }: TierCardProps) {
  return (
    <div className="panel p-4 flex items-start gap-4">
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
        style={{ backgroundColor: `${color}20`, color }}
      >
        {tier === 1 ? "🧠" : tier === 2 ? "📚" : tier === 3 ? "🕸️" : "💾"}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <h4 className="text-sm font-medium text-text-primary">{name}</h4>
          <span className="text-xs font-mono text-text-muted">{used.toFixed(1)} / {capacity} {capacity > 100 ? 'GB' : 'MB'}</span>
        </div>
        <div className="flex items-center gap-2 mb-2">
          <div className="flex-1 h-2 bg-bg-3 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${utilization}%`, backgroundColor: color }}
            />
          </div>
          <span className="text-xs text-text-muted w-12 text-right">{utilization.toFixed(0)}%</span>
        </div>
        <p className="text-xs text-text-muted">{storage} · {description}</p>
      </div>
    </div>
  );
}

export function MemorySystemPanel() {
  const [stats, setStats] = useState<MemorySystemStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getMemoryStats().then(setStats).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading || !stats) {
    return (
      <div className="flex flex-col gap-4 p-6 max-w-4xl mx-auto">
        <h2 className="text-2xl font-bold text-text-primary">Memory System</h2>
        <div className="text-center py-12 text-text-muted">Loading memory stats...</div>
      </div>
    );
  }

  const tiers: TierCardProps[] = [
    {
      name: "Sensory Memory",
      storage: "Redis",
      used: stats.sensory.size,
      capacity: stats.sensory.capacity,
      utilization: stats.sensory.capacity > 0 ? (stats.sensory.size / stats.sensory.capacity) * 100 : 0,
      color: "#3b82f6",
      description: "Short-term working memory, volatile, fast access",
      tier: 1,
    },
    {
      name: "Long-term Memory",
      storage: "PostgreSQL",
      used: stats.longterm.size,
      capacity: stats.longterm.capacity,
      utilization: stats.longterm.capacity > 0 ? (stats.longterm.size / stats.longterm.capacity) * 100 : 0,
      color: "#10b981",
      description: "Persistent knowledge store, durable storage",
      tier: 2,
    },
    {
      name: "Procedural Memory",
      storage: "Neo4j",
      used: stats.procedural.size,
      capacity: stats.procedural.capacity,
      utilization: stats.procedural.capacity > 0 ? (stats.procedural.size / stats.procedural.capacity) * 100 : 0,
      color: "#f59e0b",
      description: "Knowledge graphs, relationships, reasoning patterns",
      tier: 3,
    },
    {
      name: "Backup Store",
      storage: "SQLite",
      used: stats.working.size,
      capacity: stats.working.capacity,
      utilization: stats.working.capacity > 0 ? (stats.working.size / stats.working.capacity) * 100 : 0,
      color: "#8b5cf6",
      description: "Redundant backup, disaster recovery",
      tier: 4,
    },
  ];

  return (
    <div className="flex flex-col gap-4 p-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-text-primary">Memory System</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {tiers.map((tier, i) => (
          <TierCard key={i} {...tier} />
        ))}
      </div>
    </div>
  );
}
