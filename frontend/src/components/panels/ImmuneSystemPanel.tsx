/**
 * Tektos-Ultima v1 — Immune System Panel
 *
 * Full immune system dashboard:
 * - Health score with component breakdown
 * - Active threats with severity, category, and recommended actions
 * - Threat memory (learned patterns)
 * - Response history (actions taken)
 * - Detector status
 *
 * Design: Health banner + threat cards + memory/response tabs.
 * Color-coded severity: LOW=blue, MEDIUM=amber, HIGH=orange, CRITICAL=red.
 */

import { useState, useEffect, useCallback } from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface HealthScore {
  overall: number;
  status: string;
  components: Record<string, number>;
  active_threats: number;
  resolved_threats: number;
  uptime_seconds: number;
  timestamp: number;
}

interface Threat {
  category: string;
  severity: string;
  description: string;
  timestamp: number;
  source: string;
  evidence: Record<string, unknown>;
  affected_components: string[];
  recommended_action: string;
  resolved: boolean;
  resolution: string;
}

interface MemorySummary {
  total_threats_seen: number;
  unique_threats: number;
  categories: Record<string, number>;
  last_updated: string;
}

interface ResponseRecord {
  threat: Threat;
  action: string;
  timestamp: number;
  success: boolean;
  details: string;
}

interface DetectorInfo {
  name: string;
  status: string;
  threats_detected: number;
}

interface ImmuneState {
  health: HealthScore;
  threats: Threat[];
  memory: MemorySummary;
  responses: ResponseRecord[];
  detectors: DetectorInfo[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const severityStyles: Record<string, { bg: string; text: string; border: string; icon: string }> = {
  LOW: { bg: "bg-blue-500/10", text: "text-blue-400", border: "border-blue-500/30", icon: "●" },
  MEDIUM: { bg: "bg-amber-500/10", text: "text-amber-400", border: "border-amber-500/30", icon: "⚠" },
  HIGH: { bg: "bg-orange-500/10", text: "text-orange-400", border: "border-orange-500/30", icon: "⛔" },
  CRITICAL: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/30", icon: "🚨" },
};

const healthStyles: Record<string, { bg: string; text: string; icon: string }> = {
  healthy: { bg: "bg-green-500/10 border-green-500/30", text: "text-green-400", icon: "✓" },
  warning: { bg: "bg-amber-500/10 border-amber-500/30", text: "text-amber-400", icon: "⚠" },
  critical: { bg: "bg-red-500/10 border-red-500/30", text: "text-red-400", icon: "🚨" },
};

const formatUptime = (seconds: number): string => {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
};

const formatTime = (ts: number): string => {
  return new Date(ts * 1000).toLocaleTimeString();
};

// ─── Component ────────────────────────────────────────────────────────────────

export function ImmuneSystemPanel() {
  const [state, setState] = useState<ImmuneState | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"threats" | "memory" | "responses">("threats");
  const [showResolved, setShowResolved] = useState(false);

  const fetchImmune = useCallback(async () => {
    try {
      const [healthRes, threatsRes, memoryRes, responsesRes, detectorsRes] = await Promise.all([
        fetch("/api/immune/health"),
        fetch("/api/immune/threats?resolved=false"),
        fetch("/api/immune/memory"),
        fetch("/api/immune/responses?limit=20"),
        fetch("/api/immune/detectors"),
      ]);

      const health = await healthRes.json();
      const threats = await threatsRes.json();
      const memory = await memoryRes.json();
      const responses = await responsesRes.json();
      const detectors = await detectorsRes.json();

      setState({
        health: health || {},
        threats: Array.isArray(threats) ? threats : [],
        memory: memory || {},
        responses: Array.isArray(responses) ? responses : [],
        detectors: Array.isArray(detectors) ? detectors : [],
      });
    } catch (err) {
      console.error("Failed to load immune system:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchImmune();
    const interval = setInterval(fetchImmune, 5000);
    return () => clearInterval(interval);
  }, [fetchImmune]);

  if (loading && !state) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading immune system...</div>
      </div>
    );
  }

  if (!state) return null;

  const { health, threats, memory, responses, detectors } = state;
  const hStyle = healthStyles[health.status] || healthStyles.healthy;
  const activeThreats = threats.filter((t) => !t.resolved);
  const resolvedThreats = threats.filter((t) => t.resolved);
  const displayThreats = showResolved ? threats : activeThreats;

  return (
    <div className="space-y-6">
      {/* ─── Health Banner ─────────────────────────────────────────────── */}
      <div className={`border rounded-lg p-5 ${hStyle.bg}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className={`text-3xl ${hStyle.text}`}>{hStyle.icon}</span>
            <div>
              <h2 className={`text-xl font-bold ${hStyle.text} capitalize`}>
                System Health: {health.status}
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Score: {health.overall.toFixed(2)} · Uptime: {formatUptime(health.uptime_seconds)} ·
                Last check: {formatTime(health.timestamp)}
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-3 text-sm">
              <span className="text-red-400 font-mono">{health.active_threats} active</span>
              <span className="text-slate-500">·</span>
              <span className="text-green-400 font-mono">{health.resolved_threats} resolved</span>
            </div>
          </div>
        </div>

        {/* Component health bars */}
        {Object.keys(health.components).length > 0 && (
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
            {Object.entries(health.components).map(([name, score]) => (
              <div key={name} className="bg-black/20 rounded-md p-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-slate-400 capitalize">{name.replace(/_/g, " ")}</span>
                  <span className={`text-xs font-mono ${score >= 0.7 ? "text-green-400" : score >= 0.5 ? "text-amber-400" : "text-red-400"}`}>
                    {(score * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-1.5">
                  <div
                    className={`h-1.5 rounded-full transition-all ${
                      score >= 0.7 ? "bg-green-400" : score >= 0.5 ? "bg-amber-400" : "bg-red-400"
                    }`}
                    style={{ width: `${score * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ─── Detector Status ───────────────────────────────────────────── */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Active Detectors</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {detectors.map((d) => (
            <div
              key={d.name}
              className="bg-black/30 border border-slate-700 rounded-md px-3 py-2 flex items-center gap-2"
            >
              <span className={`w-2 h-2 rounded-full ${d.status === "active" ? "bg-green-400" : "bg-slate-500"}`} />
              <div>
                <div className="text-xs font-medium text-slate-300 capitalize">{d.name.replace(/_/g, " ")}</div>
                <div className="text-xs text-slate-500">{d.threats_detected} threats</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ─── Threats / Memory / Responses Tabs ─────────────────────────── */}
      <div className="bg-black/40 border border-slate-700 rounded-lg overflow-hidden">
        {/* Tab bar */}
        <div className="flex border-b border-slate-700">
          {[
            { key: "threats" as const, label: `Threats (${activeThreats.length})`, badge: activeThreats.length > 0 ? "text-red-400" : "" },
            { key: "memory" as const, label: `Memory (${memory.total_threats_seen || 0})` },
            { key: "responses" as const, label: `Responses (${responses.length})` },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2.5 text-xs font-medium transition-all border-b-2 ${
                activeTab === tab.key
                  ? "border-accent text-accent bg-accent/5"
                  : "border-transparent text-slate-400 hover:text-slate-300"
              }`}
            >
              {tab.label}
              {tab.badge && <span className={`ml-1 ${tab.badge}`}>!</span>}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="p-4">
          {activeTab === "threats" && (
            <div className="space-y-3">
              {displayThreats.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  {showResolved ? "No resolved threats" : "✓ No active threats — system is healthy"}
                </div>
              ) : (
                <>
                  {displayThreats.map((threat, i) => {
                    const s = severityStyles[threat.severity] || severityStyles.LOW;
                    return (
                      <div
                        key={i}
                        className={`border rounded-lg p-4 ${s.bg} ${s.border} ${threat.resolved ? "opacity-60" : ""}`}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className={`text-lg ${s.text}`}>{s.icon}</span>
                            <span className={`text-sm font-bold ${s.text}`}>{threat.severity}</span>
                            <span className="text-xs text-slate-400 capitalize">
                              {threat.category.replace(/_/g, " ")}
                            </span>
                            {threat.resolved && (
                              <span className="text-xs text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded">
                                RESOLVED
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-slate-500">{formatTime(threat.timestamp)}</span>
                        </div>

                        <p className="text-sm text-slate-300 mb-2">{threat.description}</p>

                        {threat.affected_components.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {threat.affected_components.map((c) => (
                              <span key={c} className="text-xs bg-black/30 text-slate-400 px-2 py-0.5 rounded">
                                {c}
                              </span>
                            ))}
                          </div>
                        )}

                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-500">Source: {threat.source}</span>
                          <span className="text-amber-400/80">→ {threat.recommended_action}</span>
                        </div>
                      </div>
                    );
                  })}

                  {activeThreats.length > 0 && (
                    <button
                      onClick={() => setShowResolved(!showResolved)}
                      className="w-full text-center text-xs text-slate-500 hover:text-slate-300 py-2 transition-colors"
                    >
                      {showResolved ? "Hide resolved" : `Show ${resolvedThreats.length} resolved threats`}
                    </button>
                  )}
                </>
              )}
            </div>
          )}

          {activeTab === "memory" && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-2xl font-bold text-white">{memory.total_threats_seen || 0}</div>
                  <div className="text-xs text-slate-400">Total Seen</div>
                </div>
                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-2xl font-bold text-white">{memory.unique_threats || 0}</div>
                  <div className="text-xs text-slate-400">Unique Types</div>
                </div>
                <div className="bg-black/30 rounded-lg p-3">
                  <div className="text-2xl font-bold text-white">{Object.keys(memory.categories || {}).length}</div>
                  <div className="text-xs text-slate-400">Categories</div>
                </div>
              </div>

              {memory.categories && Object.keys(memory.categories).length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-slate-400 mb-2">Threat Categories</h4>
                  <div className="space-y-1.5">
                    {Object.entries(memory.categories)
                      .sort(([, a], [, b]) => b - a)
                      .map(([cat, count]) => (
                        <div key={cat} className="flex items-center gap-3">
                          <span className="text-xs text-slate-400 w-48 truncate capitalize">{cat.replace(/_/g, " ")}</span>
                          <div className="flex-1 bg-slate-700 rounded-full h-2">
                            <div
                              className="h-2 rounded-full bg-accent transition-all"
                              style={{ width: `${Math.min((count / (memory.total_threats_seen || 1)) * 100, 100)}%` }}
                            />
                          </div>
                          <span className="text-xs font-mono text-slate-400 w-8 text-right">{count}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === "responses" && (
            <div className="space-y-3">
              {responses.length === 0 ? (
                <div className="text-center py-8 text-slate-500">No responses recorded yet</div>
              ) : (
                responses.map((r, i) => (
                  <div key={i} className="bg-black/30 border border-slate-700 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className={`text-xs font-medium ${r.success ? "text-green-400" : "text-red-400"}`}>
                        {r.success ? "✓" : "✗"} {r.action}
                      </span>
                      <span className="text-xs text-slate-500">{formatTime(r.timestamp)}</span>
                    </div>
                    <p className="text-xs text-slate-400">{r.details}</p>
                    <div className="mt-1 text-xs text-slate-500">
                      Threat: <span className="text-slate-300">{r.threat.description}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
