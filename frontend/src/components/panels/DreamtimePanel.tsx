/**
 * Tektos-Ultima — Dreamtime Panel
 *
 * Surfaces the dreamtime/contemplation engine:
 *   - Summary card (state, totals)
 *   - Recent dreams with insights and novelty
 *   - Manual "Run contemplation" and "Generate skills from insights" actions
 */

"use client";

import { useCallback, useEffect, useState } from "react";

interface DreamSummary {
  state?: string;
  total_dreams?: number;
  total_insights?: number;
  last_run?: string;
  novel_dreams?: number;
  error?: string;
  [k: string]: unknown;
}

interface Dream {
  id: string;
  source_count: number;
  insight_count: number;
  is_novel: boolean;
  novelty_score: number;
  insights: string[];
  timestamp: string;
}

export function DreamtimePanel() {
  const [summary, setSummary] = useState<DreamSummary | null>(null);
  const [dreams, setDreams] = useState<Dream[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [focusArea, setFocusArea] = useState("");
  const [maxMemories, setMaxMemories] = useState(50);

  const load = useCallback(async () => {
    try {
      const [sRes, hRes] = await Promise.all([
        fetch("/api/dreamtime/summary"),
        fetch("/api/dreamtime/history?limit=10"),
      ]);
      const sBody = await sRes.json();
      const hBody = await hRes.json();
      setSummary(sBody);
      setDreams(Array.isArray(hBody.dreams) ? hBody.dreams : []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const runContemplation = async () => {
    setBusy(true);
    setStatus("running contemplation…");
    try {
      const res = await fetch("/api/dreamtime/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_memories: maxMemories,
          focus_area: focusArea || null,
        }),
      });
      const body = await res.json();
      if (body.error) {
        setStatus(`✗ ${body.error}`);
      } else {
        setStatus(`✓ dream ${body.id.slice(0, 8)} — ${body.insight_count} insights, novelty ${(body.novelty_score * 100).toFixed(0)}%`);
      }
    } catch (err) {
      setStatus(`✗ ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
      void load();
    }
  };

  const triggerSkills = async () => {
    setBusy(true);
    setStatus("generating skills from insights…");
    try {
      const res = await fetch("/api/dreamtime/trigger-skill-generation", { method: "POST" });
      const body = await res.json();
      if (body.error) {
        setStatus(`✗ ${body.error}`);
      } else {
        setStatus(`✓ ${body.message ?? "done"} (skills created: ${body.skills_created ?? 0})`);
      }
    } catch (err) {
      setStatus(`✗ ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="panel-card">
          <div className="text-2xl font-bold text-accent">{summary?.total_dreams ?? 0}</div>
          <div className="text-sm text-text-muted">Dreams</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-status-success">{summary?.total_insights ?? 0}</div>
          <div className="text-sm text-text-muted">Insights</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-text-primary">{summary?.novel_dreams ?? 0}</div>
          <div className="text-sm text-text-muted">Novel</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-text-primary">
            {(summary?.state as string) ?? "idle"}
          </div>
          <div className="text-sm text-text-muted">State</div>
        </div>
      </div>

      {summary?.error && (
        <div className="panel-card bg-status-error/10 border-status-error text-status-error text-sm p-3">
          {summary.error}
        </div>
      )}

      {/* Controls */}
      <div className="panel-card space-y-2">
        <div className="text-sm font-medium text-text-primary">Run contemplation</div>
        <div className="flex flex-wrap gap-2 items-center text-xs">
          <label className="text-text-muted">Focus:</label>
          <input
            type="text"
            value={focusArea}
            onChange={(e) => setFocusArea(e.target.value)}
            placeholder="(optional keyword)"
            className="bg-bg-3 border border-border rounded px-2 py-1 text-xs w-56"
          />
          <label className="text-text-muted ml-2">Max memories:</label>
          <input
            type="number"
            value={maxMemories}
            min={5}
            max={500}
            onChange={(e) => setMaxMemories(parseInt(e.target.value) || 50)}
            className="bg-bg-3 border border-border rounded px-2 py-1 text-xs w-20"
          />
          <button
            onClick={runContemplation}
            disabled={busy}
            className="ml-auto rounded bg-accent px-3 py-1 text-black text-xs font-medium disabled:opacity-40"
          >
            Run
          </button>
          <button
            onClick={triggerSkills}
            disabled={busy}
            className="rounded border border-border px-3 py-1 text-text-primary text-xs hover:bg-bg-3 disabled:opacity-40"
          >
            Skills from insights
          </button>
        </div>
        {status && <div className="text-xs text-text-muted">{status}</div>}
      </div>

      {/* History */}
      <div className="space-y-2">
        <div className="text-sm font-medium text-text-primary">Recent dreams</div>
        {dreams.length === 0 ? (
          <div className="text-xs text-text-muted">No dreams yet.</div>
        ) : (
          dreams.map((d) => (
            <div key={d.id} className="panel-card space-y-1">
              <div className="flex items-center gap-2 text-xs text-text-muted">
                <span className="font-mono text-text-primary">{d.id.slice(0, 8)}</span>
                <span>{new Date(d.timestamp).toLocaleString()}</span>
                <span>· {d.source_count} sources</span>
                <span>· {d.insight_count} insights</span>
                <span
                  className={`ml-auto rounded-full px-2 py-0.5 text-xs ${
                    d.is_novel ? "bg-status-success/20 text-status-success" : "bg-bg-3 text-text-muted"
                  }`}
                >
                  novelty {(d.novelty_score * 100).toFixed(0)}%
                </span>
              </div>
              {d.insights.length > 0 && (
                <ul className="ml-5 list-disc text-xs text-text-secondary space-y-0.5">
                  {d.insights.slice(0, 5).map((i, idx) => (
                    <li key={idx}>{i}</li>
                  ))}
                  {d.insights.length > 5 && (
                    <li className="text-text-muted">…+{d.insights.length - 5} more</li>
                  )}
                </ul>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
