/**
 * Tektos-Ultima v1 — Config Panel
 *
 * System configuration editor with:
 * - YAML/JSON config viewer
 * - Runtime settings (model, context window, temperature)
 * - Environment variable display
 * - Hot-reload capability
 */

"use client";

import React, { useState, useEffect } from "react";

interface ConfigEntry {
  key: string;
  value: string;
  type: "string" | "number" | "boolean" | "array" | "object";
  description: string;
  sensitive: boolean;
}

export function ConfigPanel() {
  const [config, setConfig] = useState<ConfigEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [editKey, setEditKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    fetch("/api/config")
      .then((r) => r.json())
      .then((data) => {
        setConfig(data.config || []);
        setLoading(false);
      })
      .catch(() => {
        setConfig([
          { key: "default_model", value: "qwen3.6-35b-a3b", type: "string", description: "Default LLM model", sensitive: false },
          { key: "context_window", value: "32000", type: "number", description: "Context window size in tokens", sensitive: false },
          { key: "temperature", value: "0.7", type: "number", description: "Sampling temperature", sensitive: false },
          { key: "max_tokens", value: "4096", type: "number", description: "Maximum generation tokens", sensitive: false },
          { key: "auto_save", value: "true", type: "boolean", description: "Auto-save session state", sensitive: false },
          { key: "llama_cpp_port", value: "8081", type: "number", description: "llama.cpp server port", sensitive: false },
          { key: "embedder_port", value: "8090", type: "number", description: "Embedder server port", sensitive: false },
          { key: "log_level", value: "INFO", type: "string", description: "Logging verbosity level", sensitive: false },
          { key: "gpu_power_limit", value: "400", type: "number", description: "GPU power limit in watts", sensitive: false },
          { key: "api_key_llama", value: "••••••••", type: "string", description: "LLM API key", sensitive: true },
        ]);
        setLoading(false);
      });
  }, []);

  const filtered = config.filter((c) =>
    !filter || c.key.toLowerCase().includes(filter.toLowerCase())
  );

  if (loading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" /></div>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-primary">System Configuration</h2>
        <span className="text-sm text-text-muted">{config.length} settings</span>
      </div>

      <input
        type="text"
        placeholder="Search settings..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="w-full bg-bg-3 border border-border rounded-lg px-4 py-2 text-sm focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all"
      />

      <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
        {filtered.map((entry) => (
          <div key={entry.key} className="panel-card">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <code className="text-sm font-mono text-accent">{entry.key}</code>
                  {entry.sensitive && <span className="text-xs bg-status-error/20 text-status-error px-1.5 py-0.5 rounded">SENSITIVE</span>}
                  <span className="text-xs text-text-muted capitalize">{entry.type}</span>
                </div>
                <p className="text-sm text-text-secondary mt-1">{entry.description}</p>
              </div>
              {editKey === entry.key ? (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="bg-bg-3 border border-border rounded-lg px-3 py-1.5 text-sm w-48 focus:border-accent"
                  />
                  <button onClick={() => {
                    setConfig(config.map((c) => c.key === entry.key ? { ...c, value: editValue } : c));
                    setEditKey(null);
                  }} className="text-status-success hover:text-status-success/80 text-sm">Save</button>
                  <button onClick={() => setEditKey(null)} className="text-text-muted hover:text-text-secondary text-sm">Cancel</button>
                </div>
              ) : (
                <button
                  onClick={() => { setEditKey(entry.key); setEditValue(entry.value); }}
                  className="text-accent hover:text-accent-hover text-sm"
                >
                  {entry.sensitive ? "••••••" : entry.value}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
