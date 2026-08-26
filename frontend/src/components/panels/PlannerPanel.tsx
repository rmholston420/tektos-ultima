/**
 * Tektos-Ultima v1 — Planner Panel (S4)
 *
 * Dashboard for the Planner/Thinker:
 * - Architecture templates available
 * - Language games (domain classifiers)
 * - Run planning pipeline on a prompt
 * - View generated specs with phases and requirements
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface Template {
  name: string;
  description: string;
  pros: string[];
  cons: string[];
  use_cases: string[];
  recommended_for: string;
}

interface LanguageGame {
  name: string;
  description: string;
}

interface SpecPhase {
  id: string;
  description: string;
  deliverables: string[];
  acceptance_criteria: string[];
  estimated_effort: string;
}

interface BuildSpec {
  id: string;
  version: string;
  created_at: string;
  description: string;
  requirements: string[];
  constraints: string[];
  tech_stack: string[];
  test_strategy: string;
  architecture: { selected: string; reason: string; is_user_choice: boolean };
  phases: SpecPhase[];
  context_budget_warning: string | null;
  notes: string[];
}

interface PlannerOutput {
  spec: BuildSpec;
  language_game_detected: string;
  ambiguities_found: Array<{ term: string; possible_meanings: string[]; criticality: string }>;
  clarifying_questions_asked: Array<{ question: string; options: string[]; reason: string }>;
  templates_presented: string[];
  context_budget_used: number;
  context_budget_total: number;
}

interface PlannerState {
  templates: Template[];
  languageGames: LanguageGame[];
  output: PlannerOutput | null;
  loading: boolean;
  error: string | null;
}

export function PlannerPanel() {
  const [state, setState] = useState<PlannerState>({
    templates: [],
    languageGames: [],
    output: null,
    loading: true,
    error: null,
  });
  const [prompt, setPrompt] = useState("");
  const [running, setRunning] = useState(false);
  const [activeTab, setActiveTab] = useState<"templates" | "plan" | "output">("templates");

  const fetchData = useCallback(async () => {
    try {
      const [tplRes, lgRes] = await Promise.all([
        fetch("/api/planner/templates"),
        fetch("/api/planner/language-games"),
      ]);

      if (!tplRes.ok || !lgRes.ok) {
        setState((prev) => ({
          ...prev,
          loading: false,
          error: "Failed to fetch planner data",
        }));
        return;
      }

      const tplData = await tplRes.json();
      const lgData = await lgRes.json();

      setState((prev) => ({
        ...prev,
        templates: tplData.templates || [],
        languageGames: lgData.language_games || [],
        loading: false,
        error: null,
      }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : "Unknown error",
      }));
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handlePlan = async () => {
    if (!prompt.trim()) return;
    setRunning(true);
    setState((prev) => ({ ...prev, output: null, error: null }));
    try {
      const res = await fetch("/api/planner/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const output = await res.json();
      setState((prev) => ({ ...prev, output, activeTab: "output" }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        error: err instanceof Error ? err.message : "Planning failed",
      }));
    } finally {
      setRunning(false);
    }
  };

  if (state.loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Loading planner data...</div>
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-red-400 text-sm">{state.error}</div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">📋</span>
          <h2 className="text-sm font-semibold text-text-primary">Planner (S4)</h2>
          <span className="text-xs text-text-muted">NL → Spec Pipeline</span>
        </div>
        <div className="flex items-center gap-1 bg-bg-3 rounded-lg p-0.5">
          {(["templates", "plan", "output"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                activeTab === tab
                  ? "bg-accent text-white shadow-sm"
                  : "text-text-muted hover:text-text-primary"
              }`}
            >
              {tab === "templates" ? "Templates" : tab === "plan" ? "Plan" : "Output"}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeTab === "templates" && (
          <>
            {/* Language Games */}
            {state.languageGames.length > 0 && (
              <div className="bg-surface rounded-lg p-3 border border-border">
                <h3 className="text-xs font-semibold text-text-muted mb-3">Language Games (Domains)</h3>
                <div className="grid grid-cols-2 gap-2">
                  {state.languageGames.map((lg) => (
                    <div key={lg.name} className="bg-bg-3 rounded-md p-2">
                      <div className="text-xs font-medium text-text-primary capitalize">
                        {lg.description}
                      </div>
                      <div className="text-xs text-text-muted">{lg.name}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Templates */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold text-text-muted">Architecture Templates</h3>
              {state.templates.map((tpl) => (
                <div key={tpl.name} className="bg-surface rounded-lg p-3 border border-border">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-medium text-text-primary capitalize">{tpl.name.replace(/_/g, " ")}</h4>
                    <span className="text-xs text-text-muted">{tpl.recommended_for}</span>
                  </div>
                  <p className="text-xs text-text-primary mb-3">{tpl.description}</p>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-green-400 font-medium">Pros:</span>
                      <ul className="mt-1 space-y-0.5 text-text-muted">
                        {tpl.pros.slice(0, 3).map((p, i) => (
                          <li key={i}>• {p}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <span className="text-red-400 font-medium">Cons:</span>
                      <ul className="mt-1 space-y-0.5 text-text-muted">
                        {tpl.cons.slice(0, 3).map((c, i) => (
                          <li key={i}>• {c}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {activeTab === "plan" && (
          <div className="space-y-4">
            <div className="bg-surface rounded-lg p-3 border border-border">
              <h3 className="text-xs font-semibold text-text-muted mb-3">Run Planning Pipeline</h3>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                className="w-full bg-bg-3 border border-border rounded-md px-3 py-2 text-xs text-text-primary focus:outline-none focus:border-accent font-mono resize-none"
                rows={6}
                placeholder="Describe what you want to build. The Planner will translate your natural language into a structured build spec..."
              />
              <button
                onClick={handlePlan}
                disabled={running || !prompt.trim()}
                className="mt-3 w-full bg-accent text-white text-xs font-medium py-2 rounded-md hover:bg-accent/90 transition-colors disabled:opacity-50"
              >
                {running ? "Planning..." : "Run Planner"}
              </button>
            </div>

            {/* Quick prompts */}
            <div className="bg-surface rounded-lg p-3 border border-border">
              <h3 className="text-xs font-semibold text-text-muted mb-2">Quick Prompts</h3>
              <div className="flex flex-wrap gap-2">
                {[
                  "Build a REST API for task management with SQLite backend",
                  "Create a React dashboard with real-time WebSocket updates",
                  "Implement a plugin system with kernel + extensions architecture",
                ].map((qp) => (
                  <button
                    key={qp}
                    onClick={() => setPrompt(qp)}
                    className="px-2 py-1 text-xs bg-bg-3 border border-border rounded-md text-text-muted hover:text-text-primary transition-all"
                  >
                    {qp.slice(0, 40)}...
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "output" && (
          <>
            {state.output ? (
              <>
                {/* Spec Header */}
                <div className="bg-surface rounded-lg p-3 border border-border">
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <h3 className="text-sm font-semibold text-text-primary">{state.output.spec.description}</h3>
                      <div className="text-xs text-text-muted font-mono mt-1">
                        {state.output.spec.id} · v{state.output.spec.version}
                      </div>
                    </div>
                    <span className="text-xs text-text-muted capitalize">
                      {state.output.language_game_detected.replace(/_/g, " ")}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-3 text-xs">
                    <div>
                      <span className="text-text-muted">Architecture:</span>{" "}
                      <span className="text-text-primary capitalize">{state.output.spec.architecture.selected}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Phases:</span>{" "}
                      <span className="text-text-primary">{state.output.spec.phases.length}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Requirements:</span>{" "}
                      <span className="text-text-primary">{state.output.spec.requirements.length}</span>
                    </div>
                  </div>
                </div>

                {/* Ambiguities */}
                {state.output.ambiguities_found.length > 0 && (
                  <div className="bg-surface rounded-lg p-3 border border-border">
                    <h3 className="text-xs font-semibold text-text-muted mb-2">Ambiguities Found</h3>
                    <div className="space-y-2">
                      {state.output.ambiguities_found.map((amb, i) => (
                        <div key={i} className="text-xs">
                          <span className="text-amber-400 font-medium">{amb.term}</span>
                          <span className="text-text-muted"> — </span>
                          <span className="text-text-primary">{amb.possible_meanings.join(", ")}</span>
                          <span className={`ml-2 text-xs ${amb.criticality === "critical" ? "text-red-400" : "text-text-muted"}`}>
                            [{amb.criticality}]
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Requirements */}
                {state.output.spec.requirements.length > 0 && (
                  <div className="bg-surface rounded-lg p-3 border border-border">
                    <h3 className="text-xs font-semibold text-text-muted mb-2">Requirements</h3>
                    <ul className="text-xs text-text-primary space-y-0.5">
                      {state.output.spec.requirements.map((r, i) => (
                        <li key={i}>• {r}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Phases */}
                {state.output.spec.phases.length > 0 && (
                  <div className="bg-surface rounded-lg p-3 border border-border">
                    <h3 className="text-xs font-semibold text-text-muted mb-2">Build Phases</h3>
                    <div className="space-y-3">
                      {state.output.spec.phases.map((phase) => (
                        <div key={phase.id} className="bg-bg-3 rounded-md p-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-text-primary">{phase.description}</span>
                            <span className="text-xs text-text-muted capitalize">{phase.estimated_effort}</span>
                          </div>
                          <div className="text-xs text-text-muted mb-1">Deliverables:</div>
                          <ul className="text-xs text-text-primary space-y-0.5">
                            {phase.deliverables.map((d, j) => (
                              <li key={j}>• {d}</li>
                            ))}
                          </ul>
                          {phase.acceptance_criteria.length > 0 && (
                            <>
                              <div className="text-xs text-text-muted mt-2 mb-1">Acceptance Criteria:</div>
                              <ul className="text-xs text-text-primary space-y-0.5">
                                {phase.acceptance_criteria.map((c, j) => (
                                  <li key={j}>✓ {c}</li>
                                ))}
                              </ul>
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Context Budget */}
                <div className="bg-surface rounded-lg p-3 border border-border">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-muted">Context Budget</span>
                    <span className="text-text-primary font-mono">
                      {state.output.context_budget_used.toLocaleString()} / {state.output.context_budget_total.toLocaleString()}
                    </span>
                  </div>
                  <div className="w-full bg-slate-700 rounded-full h-1.5 mt-1">
                    <div
                      className="h-1.5 rounded-full bg-blue-400"
                      style={{ width: `${Math.min((state.output.context_budget_used / state.output.context_budget_total) * 100, 100)}%` }}
                    />
                  </div>
                </div>
              </>
            ) : (
              <div className="flex items-center justify-center h-64">
                <div className="text-center text-text-muted text-sm">
                  Run the planner to see output here
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
