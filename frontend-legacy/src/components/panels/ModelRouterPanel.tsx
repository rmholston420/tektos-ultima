/**
 * Tektos-Ultima v1 — Model Router Panel
 *
 * Multi-model routing dashboard showing:
 * - Available models with tier badges
 * - Current routing decision with reasoning
 * - Cost tracking per model
 * - Fallback chain visualization
 *
 * Design: Cards with tier color-coding, animated decision flow.
 */

"use client";

import React, { useState, useEffect } from "react";
import { api, type ModelProfile, type RoutingDecision } from "@/lib/api";

const TIER_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  fast: { bg: "bg-green-500/20", text: "text-green-400", label: "Fast" },
  balanced: { bg: "bg-blue-500/20", text: "text-blue-400", label: "Balanced" },
  power: { bg: "bg-purple-500/20", text: "text-purple-400", label: "Power" },
  expert: { bg: "bg-amber-500/20", text: "text-amber-400", label: "Expert" },
};

export function ModelRouterPanel() {
  const [models, setModels] = useState<ModelProfile[]>([]);
  const [decision, setDecision] = useState<RoutingDecision | null>(null);
  const [taskInput, setTaskInput] = useState("");
  const [complexity, setComplexity] = useState(5);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getModels().then(setModels).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleDecide = async () => {
    if (!taskInput) return;
    try {
      const d = await api.getRoutingDecision(taskInput, complexity);
      setDecision(d);
    } catch (err) {
      console.error("Routing decision failed:", err);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-6 max-w-6xl mx-auto">
      <h2 className="text-2xl font-bold text-text-primary">Model Router</h2>

      {/* Decision Interface */}
      <div className="panel">
        <h3 className="text-sm font-medium text-text-muted mb-3">Routing Decision</h3>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Describe the task..."
              value={taskInput}
              onChange={(e) => setTaskInput(e.target.value)}
              className="w-full bg-bg-3 border border-border rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted">Complexity:</span>
            <input
              type="range"
              min="1"
              max="10"
              value={complexity}
              onChange={(e) => setComplexity(parseInt(e.target.value))}
              className="w-24"
            />
            <span className="text-sm text-text-primary w-6">{complexity}</span>
          </div>
          <button
            onClick={handleDecide}
            className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            Decide
          </button>
        </div>

        {decision && (
          <div className="mt-4 p-4 rounded-lg bg-surface-active border border-border">
            <div className="flex items-center gap-3 mb-2">
              <div className={`px-2 py-1 rounded-md text-xs font-medium ${TIER_STYLES[decision.tier]?.bg || ""}`}>
                {TIER_STYLES[decision.tier]?.label || decision.tier}
              </div>
              <span className="text-sm font-medium text-text-primary">{decision.selected_model}</span>
              <span className="text-xs text-text-muted">Confidence: {Math.round(decision.confidence * 100)}%</span>
            </div>
            <p className="text-sm text-text-secondary">{decision.reason}</p>
            {decision.fallback_model && (
              <p className="text-xs text-text-muted mt-2">
                Fallback: <span className="text-text-secondary">{decision.fallback_model}</span>
              </p>
            )}
          </div>
        )}
      </div>

      {/* Available Models */}
      <div className="panel">
        <h3 className="text-sm font-medium text-text-muted mb-3">Available Models</h3>
        {loading ? (
          <div className="text-center py-4 text-text-muted">Loading models...</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {models.map((model) => (
              <div key={model.name} className="p-3 rounded-lg bg-bg-3 border border-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-text-primary">{model.model_name}</span>
                  <span className={`px-2 py-0.5 rounded-md text-xs font-medium ${TIER_STYLES[model.tier]?.bg || "bg-gray-500/20"}`}>
                    {TIER_STYLES[model.tier]?.label || model.tier}
                  </span>
                </div>
                <div className="text-xs text-text-muted">
                  <div>API: {model.api_base}</div>
                  <div>Context: {model.context_window.toLocaleString()} tokens</div>
                  {model.is_default && <span className="text-accent ml-2">★ Default</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
