/**
 * Tektos-Ultima v1 — Hindsight Cross-Session Memory Panel
 *
 * Displays Hindsight daemon status:
 * - Connection health, base URL, bank ID
 * - Retain / Recall / Reflect operations
 * - Recent experience records
 */

import { useState, useEffect, useCallback } from "react";

interface HindsightStatus {
  status: string;
  service: string;
  base_url: string | null;
  bank_id: string | null;
  healthy: boolean;
  error: string | null;
}

interface ExperienceRecord {
  id: string;
  content: string;
  tags: string[];
  timestamp: string;
}

export function HindsightPanel() {
  const [status, setStatus] = useState<HindsightStatus | null>(null);
  const [experiences, setExperiences] = useState<ExperienceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [retainText, setRetainText] = useState("");
  const [recallQuery, setRecallQuery] = useState("");
  const [reflectQuestion, setReflectQuestion] = useState("");
  const [retainResult, setRetainResult] = useState<string | null>(null);
  const [recallResult, setRecallResult] = useState<string | null>(null);
  const [reflectResult, setReflectResult] = useState<string | null>(null);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/hindsight/status");
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error("Failed to load Hindsight status:", err);
      setStatus({
        status: "error",
        service: "hindsight",
        base_url: null,
        bank_id: null,
        healthy: false,
        error: String(err),
      });
    }
  }, []);

  const fetchExperiences = useCallback(async () => {
    if (!status?.healthy) return;
    try {
      const res = await fetch("/api/hindsight/experiences?limit=10");
      const data = await res.json();
      setExperiences(Array.isArray(data) ? data : []);
    } catch {
      setExperiences([]);
    }
  }, [status]);

  useEffect(() => {
    fetchStatus();
    fetchExperiences();
    const interval = setInterval(() => {
      fetchStatus();
      fetchExperiences();
    }, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchExperiences]);

  const handleRetain = useCallback(async () => {
    if (!retainText.trim()) return;
    setLoadingAction("retain");
    try {
      const res = await fetch("/api/hindsight/retain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: retainText.trim() }),
      });
      const data = await res.json();
      setRetainResult(JSON.stringify(data, null, 2));
      setRetainText("");
    } catch (err) {
      setRetainResult(`Error: ${String(err)}`);
    } finally {
      setLoadingAction(null);
    }
  }, [retainText]);

  const handleRecall = useCallback(async () => {
    if (!recallQuery.trim()) return;
    setLoadingAction("recall");
    try {
      const res = await fetch("/api/hindsight/recall", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: recallQuery.trim() }),
      });
      const data = await res.json();
      setRecallResult(JSON.stringify(data, null, 2));
      setRecallQuery("");
    } catch (err) {
      setRecallResult(`Error: ${String(err)}`);
    } finally {
      setLoadingAction(null);
    }
  }, [recallQuery]);

  const handleReflect = useCallback(async () => {
    if (!reflectQuestion.trim()) return;
    setLoadingAction("reflect");
    try {
      const res = await fetch("/api/hindsight/reflect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: reflectQuestion.trim() }),
      });
      const data = await res.json();
      setReflectResult(JSON.stringify(data, null, 2));
      setReflectQuestion("");
    } catch (err) {
      setReflectResult(`Error: ${String(err)}`);
    } finally {
      setLoadingAction(null);
    }
  }, [reflectQuestion]);

  if (loading && !status) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading Hindsight status...</div>
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
          <h2 className="text-lg font-semibold text-white">Hindsight Cross-Session Memory</h2>
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${status.healthy ? "bg-green-400" : status.status === "not_initialized" ? "bg-slate-600" : "bg-red-400"}`} />
            <span className={`text-sm font-medium ${statusColor}`}>{status.status}</span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-xs text-slate-500">Base URL</span>
            <div className="text-slate-300 font-mono mt-1 truncate">{status.base_url || "—"}</div>
          </div>
          <div>
            <span className="text-xs text-slate-500">Bank ID</span>
            <div className="text-slate-300 font-mono mt-1">{status.bank_id || "—"}</div>
          </div>
        </div>

        {status.error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
            <div className="text-xs text-red-400 font-medium mb-1">Error</div>
            <div className="text-xs text-slate-400 font-mono break-all">{status.error}</div>
          </div>
        )}
      </div>

      {/* ─── Retain ──────────────────────────────────────────────────── */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Retain (Store Fact)</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={retainText}
            onChange={(e) => setRetainText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleRetain()}
            placeholder="Enter a fact to remember..."
            className="flex-1 bg-black/30 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-accent"
          />
          <button
            onClick={handleRetain}
            disabled={loadingAction === "retain" || !retainText.trim()}
            className="px-4 py-2 bg-accent/20 text-accent rounded-lg text-sm font-medium hover:bg-accent/30 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loadingAction === "retain" ? "Storing..." : "Store"}
          </button>
        </div>
        {retainResult && (
          <pre className="mt-3 p-3 bg-black/30 border border-slate-700 rounded-lg text-xs text-slate-400 font-mono max-h-40 overflow-auto whitespace-pre-wrap">
            {retainResult}
          </pre>
        )}
      </div>

      {/* ─── Recall ──────────────────────────────────────────────────── */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Recall (Search Memory)</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={recallQuery}
            onChange={(e) => setRecallQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleRecall()}
            placeholder="Search for memories..."
            className="flex-1 bg-black/30 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-accent"
          />
          <button
            onClick={handleRecall}
            disabled={loadingAction === "recall" || !recallQuery.trim()}
            className="px-4 py-2 bg-accent/20 text-accent rounded-lg text-sm font-medium hover:bg-accent/30 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loadingAction === "recall" ? "Searching..." : "Search"}
          </button>
        </div>
        {recallResult && (
          <pre className="mt-3 p-3 bg-black/30 border border-slate-700 rounded-lg text-xs text-slate-400 font-mono max-h-40 overflow-auto whitespace-pre-wrap">
            {recallResult}
          </pre>
        )}
      </div>

      {/* ─── Reflect ─────────────────────────────────────────────────── */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Reflect (Synthesize Reasoning)</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={reflectQuestion}
            onChange={(e) => setReflectQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleReflect()}
            placeholder="Ask a question about past experiences..."
            className="flex-1 bg-black/30 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-accent"
          />
          <button
            onClick={handleReflect}
            disabled={loadingAction === "reflect" || !reflectQuestion.trim()}
            className="px-4 py-2 bg-accent/20 text-accent rounded-lg text-sm font-medium hover:bg-accent/30 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loadingAction === "reflect" ? "Reflecting..." : "Reflect"}
          </button>
        </div>
        {reflectResult && (
          <pre className="mt-3 p-3 bg-black/30 border border-slate-700 rounded-lg text-xs text-slate-400 font-mono max-h-40 overflow-auto whitespace-pre-wrap">
            {reflectResult}
          </pre>
        )}
      </div>

      {/* ─── Recent Experiences ──────────────────────────────────────── */}
      <div className="bg-black/40 border border-slate-700 rounded-lg p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-3">Recent Experiences ({experiences.length})</h3>
        {experiences.length === 0 ? (
          <div className="text-center py-6 text-slate-500 text-sm">No experiences stored yet</div>
        ) : (
          <div className="space-y-2">
            {experiences.map((exp, i) => (
              <div key={i} className="border border-slate-700 rounded-lg p-3">
                <div className="text-xs text-slate-300 mb-1">{exp.content}</div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-600 font-mono">{exp.timestamp}</span>
                  {exp.tags.length > 0 && (
                    <div className="flex gap-1">
                      {exp.tags.slice(0, 3).map((tag, j) => (
                        <span key={j} className="text-[10px] bg-accent/10 text-accent px-1.5 py-0.5 rounded">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
