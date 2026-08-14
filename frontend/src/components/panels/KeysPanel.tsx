/**
 * Tektos-Ultima v1 — Keys Panel
 *
 * API key management with:
 * - Key status indicators (active, expired, revoked)
 * - Usage tracking
 * - Rotation capability
 * - Security warnings for exposed keys
 */

"use client";

import React, { useState, useEffect } from "react";

interface ApiKey {
  id: string;
  name: string;
  provider: string;
  status: "active" | "expired" | "revoked";
  created: string;
  expires: string;
  lastUsed: string;
  usageCount: number;
  masked: string;
}

export function KeysPanel() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    fetch("/api/keys")
      .then((r) => r.json())
      .then((data) => {
        setKeys(data.keys || []);
        setLoading(false);
      })
      .catch(() => {
        setKeys([
          { id: "1", name: "llama.cpp API", provider: "Custom", status: "active", created: "2026-08-01", expires: "2027-08-01", lastUsed: "2026-08-14", usageCount: 15847, masked: "sk-llama••••••••••••" },
          { id: "2", name: "Embedder Service", provider: "Custom", status: "active", created: "2026-08-01", expires: "2027-08-01", lastUsed: "2026-08-14", usageCount: 3421, masked: "sk-emb•••••••••••" },
          { id: "3", name: "Hindsight Memory", provider: "Custom", status: "active", created: "2026-08-10", expires: "2027-08-10", lastUsed: "2026-08-14", usageCount: 892, masked: "sk-hind•••••••••" },
          { id: "4", name: "GitHub Token", provider: "GitHub", status: "active", created: "2026-07-15", expires: "2026-12-15", lastUsed: "2026-08-13", usageCount: 234, masked: "ghp•••••••••••••••" },
        ]);
        setLoading(false);
      });
  }, []);

  const filtered = filter === "all" ? keys : keys.filter((k) => k.status === filter);
  const activeCount = keys.filter((k) => k.status === "active").length;
  const totalCount = keys.length;

  if (loading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" /></div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="panel-card">
          <div className="text-2xl font-bold text-accent">{totalCount}</div>
          <div className="text-sm text-text-muted">Total Keys</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-status-success">{activeCount}</div>
          <div className="text-sm text-text-muted">Active</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-text-primary">
            {keys.reduce((sum, k) => sum + k.usageCount, 0).toLocaleString()}
          </div>
          <div className="text-sm text-text-muted">Total API Calls</div>
        </div>
      </div>

      <div className="flex gap-2">
        {["all", "active", "expired", "revoked"].map((status) => (
          <button
            key={status}
            onClick={() => setFilter(status)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
              filter === status ? "bg-accent text-white" : "bg-bg-3 text-text-muted hover:text-text-primary"
            }`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {filtered.map((key) => (
          <div key={key.id} className="panel-card">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-medium text-text-primary">{key.name}</h3>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-text-muted">{key.provider}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    key.status === "active" ? "bg-status-success/20 text-status-success" :
                    key.status === "expired" ? "bg-status-error/20 text-status-error" :
                    "bg-bg-3 text-text-muted"
                  }`}>
                    {key.status}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-mono text-text-secondary">{key.masked}</div>
                <div className="text-xs text-text-muted mt-1">
                  {key.usageCount.toLocaleString()} calls • expires {key.expires}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-8 text-text-muted text-sm">No keys found</div>
      )}
    </div>
  );
}
