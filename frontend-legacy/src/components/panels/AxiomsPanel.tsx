/**
 * Tektos-Ultima v1 — Axioms Panel
 *
 * Visual axiom system with:
 * - Dependency graph showing prerequisite chains
 * - Status indicators (in_progress, verified, blocked)
 * - Progress tracking per axiom
 * - Filter by category
 *
 * Design: Progress cards with dependency arrows and status badges.
 */

"use client";

import React, { useState, useEffect } from "react";
import { api, type Axiom } from "@/lib/api";

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: string }> = {
  in_progress: { bg: "bg-blue-500/20", text: "text-blue-400", icon: "⏳" },
  verified: { bg: "bg-green-500/20", text: "text-green-400", icon: "✅" },
  blocked: { bg: "bg-red-500/20", text: "text-red-400", icon: "🚫" },
};

export function AxiomsPanel() {
  const [axioms, setAxioms] = useState<Axiom[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getAxioms().then(setAxioms).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleVerify = async (id: string) => {
    try {
      await api.verifyAxiom(id);
      setAxioms((prev) => prev.map((a) => a.id === id ? { ...a, status: "verified" } : a));
    } catch (err) {
      console.error("Failed to verify axiom:", err);
    }
  };

  const filtered = filter === "all" ? axioms : axioms.filter((a) => a.category === filter);
  const categories = [...new Set(axioms.map((a) => a.category))];
  const progress = axioms.length > 0
    ? Math.round((axioms.filter((a) => a.status === "verified").length / axioms.length) * 100)
    : 0;

  return (
    <div className="flex flex-col gap-4 p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-text-primary">Axiom System</h2>
        <div className="text-sm text-text-muted">
          {progress}% complete ({axioms.filter((a) => a.status === "verified").length}/{axioms.length})
        </div>
      </div>

      {/* Progress bar */}
      <div className="panel p-4">
        <div className="w-full bg-bg-3 rounded-full h-3 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-accent to-purple-500 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Filter */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setFilter("all")}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            filter === "all" ? "bg-accent text-white" : "bg-bg-3 text-text-muted hover:text-text-secondary"
          }`}
        >
          All
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setFilter(cat)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              filter === cat ? "bg-accent text-white" : "bg-bg-3 text-text-muted hover:text-text-secondary"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Axiom list */}
      {loading ? (
        <div className="text-center py-4 text-text-muted">Loading axioms...</div>
      ) : (
        <div className="space-y-3">
          {filtered.map((axiom) => (
            <div key={axiom.id} className="panel p-4">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{STATUS_STYLES[axiom.status]?.icon}</span>
                  <span className="text-sm font-medium text-text-primary">{axiom.id}</span>
                </div>
                <span className={`px-2 py-1 rounded-md text-xs font-medium ${STATUS_STYLES[axiom.status]?.bg} ${STATUS_STYLES[axiom.status]?.text}`}>
                  {axiom.status}
                </span>
              </div>
              <p className="text-sm text-text-secondary mb-2">{axiom.description}</p>

              {axiom.prerequisites.length > 0 && (
                <div className="flex items-center gap-2 text-xs text-text-muted">
                  <span>Requires:</span>
                  <div className="flex gap-1 flex-wrap">
                    {axiom.prerequisites.map((prereq) => (
                      <span key={prereq} className="px-2 py-0.5 rounded bg-bg-3 border border-border">
                        {prereq}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {axiom.status !== "verified" && (
                <button
                  onClick={() => handleVerify(axiom.id)}
                  className="mt-2 px-3 py-1.5 bg-accent text-white rounded-lg text-xs font-medium hover:bg-accent-hover transition-colors"
                >
                  Verify
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
