/**
 * Tektos-Ultima v1 — Logs Panel
 *
 * Real-time log viewer with:
 * - Color-coded severity levels (DEBUG=gray, INFO=blue, WARNING=amber, ERROR=red)
 * - Level filtering
 * - Auto-scroll
 * - Search within logs
 * - Log grouping by logger
 *
 * Design: Terminal-style interface with glass panels and monospace font.
 */

"use client";

import React, { useState, useEffect, useRef } from "react";
import { api, type LogEntry } from "@/lib/api";

const LEVEL_STYLES: Record<string, { bg: string; text: string; icon: string }> = {
  DEBUG: { bg: "bg-gray-500/10", text: "text-gray-400", icon: "•" },
  INFO: { bg: "bg-blue-500/10", text: "text-blue-400", icon: "●" },
  WARNING: { bg: "bg-amber-500/10", text: "text-amber-400", icon: "⚠" },
  ERROR: { bg: "bg-red-500/10", text: "text-red-400", icon: "✗" },
};

export function LogsPanel() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filterLevel, setFilterLevel] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const entries = await api.getLogs(filterLevel !== "all" ? filterLevel : undefined, 200);
        setLogs(entries);
      } catch (err) {
        console.error("Failed to fetch logs:", err);
      }
    };

    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, [filterLevel]);

  useEffect(() => {
    if (autoScroll) {
      logEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const filtered = logs.filter((log) => {
    if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  return (
    <div className="flex flex-col gap-4 p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-text-primary">System Logs</h2>
        <label className="flex items-center gap-2 text-xs text-text-secondary">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded"
          />
          Auto-scroll
        </label>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1">
          <input
            type="text"
            placeholder="Search logs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-bg-3 border border-border rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <div className="flex gap-2">
          {["all", "DEBUG", "INFO", "WARNING", "ERROR"].map((level) => (
            <button
              key={level}
              onClick={() => setFilterLevel(level)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                filterLevel === level ? "bg-accent text-white" : "bg-bg-3 text-text-muted hover:text-text-secondary"
              }`}
            >
              {level}
            </button>
          ))}
        </div>
      </div>

      {/* Log viewer */}
      <div className="panel overflow-hidden" style={{ minHeight: "400px" }}>
        <div className="bg-black/30 border-b border-border px-4 py-2 flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500/60" />
          <div className="w-3 h-3 rounded-full bg-amber-500/60" />
          <div className="w-3 h-3 rounded-full bg-green-500/60" />
          <span className="ml-2 text-xs text-text-muted font-mono">tektos-logs</span>
        </div>
        <div className="p-4 font-mono text-xs space-y-1 overflow-y-auto" style={{ maxHeight: "600px" }}>
          {filtered.map((log, i) => (
            <div key={i} className={`flex gap-3 py-1 px-2 rounded ${LEVEL_STYLES[log.level]?.bg || "bg-transparent"}`}>
              <span className="text-text-muted flex-shrink-0">{new Date(log.timestamp).toLocaleTimeString()}</span>
              <span className={`font-medium flex-shrink-0 w-20 ${LEVEL_STYLES[log.level]?.text || "text-text-muted"}`}>
                {log.level}
              </span>
              <span className="text-text-muted flex-shrink-0 w-40 truncate">{log.logger}</span>
              <span className="text-text-secondary truncate">{log.message}</span>
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}
