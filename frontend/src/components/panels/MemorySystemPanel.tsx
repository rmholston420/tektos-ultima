/**
 * Tektos-Ultima v1 — Memory System Panel
 *
 * Visualizes the memory persistence tiers reported by
 * /api/memory/stats (working / long_term / procedural counts + transfer log).
 *
 * The backend returns `{working_count, working_novel, long_term_count, ...}`
 * — a set of raw counts, not size/capacity gauges. We visualize those counts
 * directly with a "novel share" mini-gauge instead of a fake capacity bar,
 * so the panel stays honest when a tier reports 0 or is missing.
 */

"use client";

import React, { useState, useEffect } from "react";

interface MemoryStatsRaw {
  working_count?: number;
  working_novel?: number;
  long_term_count?: number;
  long_term_novel?: number;
  procedural_count?: number;
  procedural_novel?: number;
  transfers?: number;
  summary?: string;
  error?: string;
}

interface TierCardProps {
  name: string;
  storage: string;
  count: number;
  novel: number;
  color: string;
  description: string;
  icon: string;
}

function TierCard({ name, storage, count, novel, color, description, icon }: TierCardProps) {
  const novelPct = count > 0 ? (novel / count) * 100 : 0;
  return (
    <div className="panel p-4 flex items-start gap-4">
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
        style={{ backgroundColor: `${color}20`, color }}
      >
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <h4 className="text-sm font-medium text-text-primary">{name}</h4>
          <span className="text-xs font-mono text-text-muted">
            {count.toLocaleString()} entries
          </span>
        </div>
        <div className="flex items-center gap-2 mb-2">
          <div className="flex-1 h-2 bg-bg-3 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, novelPct)}%`, backgroundColor: color }}
            />
          </div>
          <span className="text-xs text-text-muted w-16 text-right">
            {novel.toLocaleString()} novel
          </span>
        </div>
        <p className="text-xs text-text-muted">{storage} · {description}</p>
      </div>
    </div>
  );
}

export function MemorySystemPanel() {
  const [stats, setStats] = useState<MemoryStatsRaw | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch("/api/memory/stats");
        const data = (await res.json()) as MemoryStatsRaw;
        setStats(data);
        setError(data?.error || null);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col gap-4 p-6 max-w-4xl mx-auto">
        <h2 className="text-2xl font-bold text-text-primary">Memory System</h2>
        <div className="text-center py-12 text-text-muted">Loading memory stats...</div>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="flex flex-col gap-4 p-6 max-w-4xl mx-auto">
        <h2 className="text-2xl font-bold text-text-primary">Memory System</h2>
        <div className="p-3 rounded-md bg-status-error/10 border border-status-error/20 text-xs text-status-error">
          {error}
        </div>
      </div>
    );
  }

  const s = stats || {};

  const tiers: TierCardProps[] = [
    {
      name: "Working Memory",
      storage: "SQLite",
      count: s.working_count ?? 0,
      novel: s.working_novel ?? 0,
      color: "#3b82f6",
      description: "Short-term working memory, volatile, fast access",
      icon: "🧠",
    },
    {
      name: "Long-term Memory",
      storage: "SQLite",
      count: s.long_term_count ?? 0,
      novel: s.long_term_novel ?? 0,
      color: "#10b981",
      description: "Persistent knowledge store, durable storage",
      icon: "📚",
    },
    {
      name: "Procedural Memory",
      storage: "SQLite",
      count: s.procedural_count ?? 0,
      novel: s.procedural_novel ?? 0,
      color: "#f59e0b",
      description: "Skills, patterns, reasoning procedures",
      icon: "🕸️",
    },
  ];

  return (
    <div className="flex flex-col gap-4 p-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-text-primary">Memory System</h2>

      {s.summary && (
        <div className="text-xs text-text-muted border border-border rounded-md p-3 bg-surface">
          {s.summary}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {tiers.map((tier, i) => (
          <TierCard key={i} {...tier} />
        ))}
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium text-text-primary">Transfers</div>
            <div className="text-xs text-text-muted">Cross-tier memory movements logged</div>
          </div>
          <div className="text-2xl font-mono text-accent">
            {(s.transfers ?? 0).toLocaleString()}
          </div>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-md bg-status-error/10 border border-status-error/20 text-xs text-status-error">
          {error}
        </div>
      )}
    </div>
  );
}
