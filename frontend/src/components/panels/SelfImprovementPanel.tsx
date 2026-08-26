/**
 * Tektos-Ultima v1 — Self-Improvement Panel
 *
 * Dashboard for the cybernetic feedback loop (System 4):
 * - Learning metrics: tasks, improvements, velocity
 * - Model performance rankings
 * - Experience records with lessons learned
 * - Human-readable report
 */

"use client";

import React, { useState, useEffect, useCallback } from "react";

interface ModelRanking {
  model: string;
  task_type: string;
  tasks: number;
  successes: number;
  avg_quality: number;
}

interface LearningMetrics {
  total_tasks: number;
  total_improvements: number;
  learning_velocity: number;
  model_rankings: ModelRanking[];
  best_model_for_coding: string | null;
}

interface ExperienceRecord {
  session_id: string;
  task: string;
  model_used: string;
  success: boolean;
  tests_passed: number;
  tests_total: number;
  wall_time_seconds: number;
  evaluation_score: number;
  lessons: string[];
  what_worked: string[];
  what_failed: string[];
  created_skills: string[];
  created_at: string;
}

interface SelfImprovementState {
  metrics: LearningMetrics | null;
  experiences: ExperienceRecord[];
  report: string | null;
  loading: boolean;
  error: string | null;
}

export function SelfImprovementPanel() {
  const [state, setState] = useState<SelfImprovementState>({
    metrics: null,
    experiences: [],
    report: null,
    loading: true,
    error: null,
  });
  const [activeTab, setActiveTab] = useState<"metrics" | "experiences" | "report">("metrics");

  const fetchData = useCallback(async () => {
    try {
      const [metricsRes, expRes, reportRes] = await Promise.all([
        fetch("/api/self_improvement/metrics"),
        fetch("/api/self_improvement/experiences?top_k=20"),
        fetch("/api/self_improvement/report"),
      ]);

      if (!metricsRes.ok || !expRes.ok) {
        setState((prev) => ({
          ...prev,
          loading: false,
          error: "Failed to fetch self-improvement data",
        }));
        return;
      }

      const metrics = await metricsRes.json();
      const expData = await expRes.json();
      const reportData = await reportRes.json();

      setState({
        metrics,
        experiences: expData.experiences || [],
        report: reportData.report ?? null,
        loading: false,
        error: null,
      });
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
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (state.loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Loading self-improvement data...</div>
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

  const m = state.metrics;
  if (!m) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-text-muted text-sm">Self-improvement not initialized</div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <span className="text-xl">🧠</span>
          <h2 className="text-sm font-semibold text-text-primary">Self-Improvement</h2>
          <span className="text-xs text-text-muted">System 4 — Cybernetic Loop</span>
        </div>
        <div className="flex items-center gap-1 bg-bg-3 rounded-lg p-0.5">
          {(["metrics", "experiences", "report"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                activeTab === tab
                  ? "bg-accent text-white shadow-sm"
                  : "text-text-muted hover:text-text-primary"
              }`}
            >
              {tab === "metrics" ? "Metrics" : tab === "experiences" ? "Experiences" : "Report"}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeTab === "metrics" && (
          <>
            {/* Overview Stats */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-surface rounded-lg p-3 border border-border text-center">
                <div className="text-2xl font-bold text-text-primary">{m.total_tasks}</div>
                <div className="text-xs text-text-muted">Total Tasks</div>
              </div>
              <div className="bg-surface rounded-lg p-3 border border-border text-center">
                <div className="text-2xl font-bold text-green-400">{m.total_improvements}</div>
                <div className="text-xs text-text-muted">Improvements</div>
              </div>
              <div className="bg-surface rounded-lg p-3 border border-border text-center">
                <div className="text-2xl font-bold text-blue-400">{m.learning_velocity.toFixed(3)}</div>
                <div className="text-xs text-text-muted">Velocity</div>
              </div>
            </div>

            {/* Best Model */}
            {m.best_model_for_coding && (
              <div className="bg-surface rounded-lg p-3 border border-border">
                <h3 className="text-xs font-semibold text-text-muted mb-2">Best Model for Coding</h3>
                <div className="text-sm font-mono text-text-primary truncate">
                  {m.best_model_for_coding}
                </div>
              </div>
            )}

            {/* Model Rankings */}
            {m.model_rankings.length > 0 && (
              <div className="bg-surface rounded-lg p-3 border border-border">
                <h3 className="text-xs font-semibold text-text-muted mb-3">Model Performance Rankings</h3>
                <div className="space-y-2">
                  {m.model_rankings.slice(0, 10).map((r, i) => (
                    <div key={i} className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-text-muted w-4">{i + 1}.</span>
                        <span className="text-xs font-mono text-text-primary truncate max-w-[14rem]">{r.model}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs">
                        <span className="text-text-muted">{r.task_type}</span>
                        <span className="text-text-muted">{r.tasks} tasks</span>
                        <span className="text-green-400 font-mono">{r.avg_quality.toFixed(3)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {activeTab === "experiences" && (
          <div className="space-y-3">
            {state.experiences.length === 0 ? (
              <div className="text-center py-8 text-text-muted text-sm">No experience records yet</div>
            ) : (
              state.experiences.map((exp, i) => (
                <div key={i} className="bg-surface rounded-lg p-3 border border-border">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-medium ${exp.success ? "text-green-400" : "text-red-400"}`}>
                        {exp.success ? "✓" : "✗"}
                      </span>
                      <span className="text-xs font-mono text-text-muted">{exp.session_id.slice(0, 8)}</span>
                      <span className="text-xs text-text-muted">{new Date(exp.created_at).toLocaleDateString()}</span>
                    </div>
                    <span className="text-xs font-mono text-slate-300">
                      Score: {exp.evaluation_score.toFixed(2)}
                    </span>
                  </div>

                  <div className="text-xs text-text-primary mb-2 truncate">{exp.task}</div>

                  <div className="grid grid-cols-3 gap-2 text-xs mb-2">
                    <div>
                      <span className="text-text-muted">Tests:</span>{" "}
                      <span className="text-text-primary">{exp.tests_passed}/{exp.tests_total}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Time:</span>{" "}
                      <span className="text-text-primary">{exp.wall_time_seconds.toFixed(0)}s</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Model:</span>{" "}
                      <span className="text-text-primary truncate">{exp.model_used.split("/").pop()}</span>
                    </div>
                  </div>

                  {exp.lessons.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border">
                      <div className="text-xs text-text-muted mb-1">Lessons:</div>
                      <ul className="text-xs text-text-primary space-y-0.5">
                        {exp.lessons.slice(0, 3).map((lesson, j) => (
                          <li key={j} className="flex items-start gap-1">
                            <span className="text-text-muted mt-0.5">•</span>
                            <span>{lesson}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {exp.created_skills.length > 0 && (
                    <div className="mt-1 text-xs text-blue-400">
                      +{exp.created_skills.length} skill(s) created
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === "report" && (
          <div className="bg-surface rounded-lg p-3 border border-border">
            {state.report ? (
              <pre className="text-xs text-text-primary font-mono whitespace-pre-wrap overflow-auto max-h-[60vh]">
                {state.report}
              </pre>
            ) : (
              <div className="text-center py-8 text-text-muted text-sm">No report available</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
