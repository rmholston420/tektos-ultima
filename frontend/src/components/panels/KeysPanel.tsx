/**
 * Tektos-Ultima v1 — Keys Panel
 *
 * Displays configured credential environment variables from /api/keys.
 * The backend returns a static list of sensitive vars with a masked value
 * and a `configured` flag; it does not track usage counts or expiry, so we
 * present only what the backend actually knows.
 */

"use client";

import React, { useEffect, useState } from "react";

interface ApiKey {
  name: string;
  key: string;
  value: string;
  configured: boolean;
}

interface KeysResponse {
  keys?: ApiKey[];
  error?: string;
}

type FilterKind = "all" | "configured" | "missing";

export function KeysPanel() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterKind>("all");

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch("/api/keys");
        const data = (await res.json()) as KeysResponse;
        if (data.error) {
          setError(data.error);
          setKeys([]);
        } else {
          setKeys(Array.isArray(data.keys) ? data.keys : []);
          setError(null);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const filtered = keys.filter((k) =>
    filter === "all" ? true : filter === "configured" ? k.configured : !k.configured,
  );
  const configuredCount = keys.filter((k) => k.configured).length;
  const missingCount = keys.length - configuredCount;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="panel-card">
          <div className="text-2xl font-bold text-accent">{keys.length}</div>
          <div className="text-sm text-text-muted">Total Credentials</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-status-success">{configuredCount}</div>
          <div className="text-sm text-text-muted">Configured</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-text-muted">{missingCount}</div>
          <div className="text-sm text-text-muted">Not Configured</div>
        </div>
      </div>

      {error && (
        <div className="rounded border border-status-error/40 bg-status-error/10 p-3 text-xs text-status-error">
          {error}
        </div>
      )}

      <div className="flex gap-2">
        {([
          { id: "all", label: "All" },
          { id: "configured", label: "Configured" },
          { id: "missing", label: "Missing" },
        ] as { id: FilterKind; label: string }[]).map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setFilter(id)}
            className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
              filter === id ? "bg-accent text-white" : "bg-bg-3 text-text-muted hover:text-text-primary"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {filtered.map((key) => (
          <div key={key.key} className="panel-card">
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <h3 className="font-medium text-text-primary">{key.name}</h3>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs font-mono text-text-muted">{key.key}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      key.configured
                        ? "bg-status-success/20 text-status-success"
                        : "bg-bg-3 text-text-muted"
                    }`}
                  >
                    {key.configured ? "configured" : "not configured"}
                  </span>
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-sm font-mono text-text-secondary">{key.value}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-8 text-text-muted text-sm">No credentials in this view.</div>
      )}
    </div>
  );
}
