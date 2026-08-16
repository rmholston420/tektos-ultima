/**
 * Tektos-Ultima v1 — Memory Panel
 *
 * Visualization of the 4-tier memory system with persistence state.
 */

import { useState, useEffect } from "react";

interface MemoryStats {
  working_count: number;
  working_novel: number;
  long_term_count: number;
  long_term_novel: number;
  procedural_count: number;
  procedural_novel: number;
  transfers: number;
}

interface MemoryEntry {
  id: string;
  content: string;
  tier: string;
  hemisphere: string;
  is_novel: boolean;
  novelty_score: number;
  timestamp: string;
  metadata: Record<string, any>;
}

export function MemoryPanel() {
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [activeTier, setActiveTier] = useState<string>("long_term");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, tierRes] = await Promise.all([
          fetch("/api/memory"),
          fetch(`/api/memory?tier=${activeTier}`),
        ]);
        const statsData = await statsRes.json();
        setStats(statsData as MemoryStats);
        const tierData = await tierRes.json();
        setEntries(Array.isArray(tierData) ? tierData : []);
      } catch (err) {
        console.error("Failed to load memory data:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [activeTier]);

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading memory system...</div>
      </div>
    );
  }

  const tiers = [
    { id: "working", label: "Working", icon: "🧠", color: "text-cyan-400", bg: "bg-cyan-400/10", border: "border-cyan-400/30" },
    { id: "long_term", label: "Long-Term", icon: "📚", color: "text-violet-400", bg: "bg-violet-400/10", border: "border-violet-400/30" },
    { id: "procedural", label: "Procedural", icon: "⚙️", color: "text-emerald-400", bg: "bg-emerald-400/10", border: "border-emerald-400/30" },
  ];

  const getCount = (id: string) => {
    if (!stats) return 0;
    return stats[`${id}_count` as keyof MemoryStats] as number;
  };
  const getNovel = (id: string) => {
    if (!stats) return 0;
    return stats[`${id}_novel` as keyof MemoryStats] as number;
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {tiers.map((t) => {
          const count = getCount(t.id);
          const novel = getNovel(t.id);
          return (
            <div key={t.id} className={`${t.bg} border ${t.border} rounded-lg p-4`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{t.icon}</span>
                  <div>
                    <h3 className={`text-sm font-medium ${t.color}`}>{t.label}</h3>
                    <p className="text-xs text-slate-400">
                      {t.id === "working" ? "Active cognition (7±2)" : t.id === "long_term" ? "Declarative knowledge" : "Skills & wisdom"}
                    </p>
                  </div>
                </div>
                <span className="text-3xl font-bold text-white">{count}</span>
              </div>
              {novel > 0 && <p className="text-xs text-amber-400 mt-2">⚡ {novel} novel{novel > 1 ? " entries" : ""}</p>}
            </div>
          );
        })}
      </div>

      <div className="flex gap-2">
        {tiers.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTier(t.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTier === t.id ? `${t.bg} ${t.color} border ${t.border}` : "bg-black/30 text-slate-400 border border-slate-700 hover:text-slate-300"
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        {entries.length === 0 ? (
          <div className="text-center py-8 text-slate-400">No {activeTier} memory entries</div>
        ) : (
          <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
            {entries.map((entry) => (
              <div key={entry.id} className="bg-black/30 border border-slate-700/50 rounded-lg p-3">
                <p className="text-sm text-slate-200">{entry.content}</p>
                <div className="flex items-center gap-3 mt-2">
                  <span className="text-xs text-slate-500">
                    {entry.hemisphere === "left" ? "◈ Operative" : "◉ Speculative"}
                  </span>
                  {entry.is_novel && (
                    <span className="text-xs text-amber-400">⚡ Novel ({entry.novelty_score.toFixed(2)})</span>
                  )}
                  <span className="text-xs text-slate-500 ml-auto">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">System Stats</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-slate-500">Memory Transfers:</span>
            <span className="text-white ml-2">{stats?.transfers || 0}</span>
          </div>
          <div>
            <span className="text-slate-500">Total Novelty:</span>
            <span className="text-amber-400 ml-2">
              {stats ? (stats.working_novel + stats.long_term_novel + stats.procedural_novel) : 0}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
