/**
 * Tektos-Ultima v1 — Skills Panel
 *
 * Interactive skill management with search, categorization, and activation.
 * Connects to /api/skills REST endpoints.
 */

"use client";

import React, { useState, useEffect, useMemo } from "react";

interface Skill {
  id: string;
  name: string;
  category: string;
  enabled: boolean;
  version: string;
  description: string;
  trigger_conditions: string[];
  steps: Record<string, any>[];
  usage_count: number;
  last_used: string;
  success_rate: number;
  source: string;
  created_at: string;
  updated_at: string;
}

interface SkillStats {
  total_skills: number;
  active_skills: number;
  top_skills: Array<{
    name: string;
    category: string;
    usage_count: number;
    success_rate: number;
  }>;
  categories: string[];
}

export function SkillsPanel() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [stats, setStats] = useState<SkillStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterCategory, setFilterCategory] = useState("all");
  const [error, setError] = useState<string | null>(null);

  const fetchSkills = async () => {
    try {
      setError(null);
      const [skillsRes, statsRes] = await Promise.all([
        fetch("/api/skills"),
        fetch("/api/skills/stats"),
      ]);
      const skillsData = await skillsRes.json();
      const statsData = await statsRes.json();
      setSkills(Array.isArray(skillsData.skills) ? skillsData.skills : []);
      setStats(statsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load skills");
      setSkills([]);
      setStats(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSkills();
  }, []);

  const categories = useMemo(() => {
    const cats = new Set(skills.map((s) => s.category).filter(Boolean));
    return ["all", ...Array.from(cats)];
  }, [skills]);

  const filteredSkills = useMemo(() => {
    return skills.filter((s) => {
      if (filterCategory !== "all" && s.category !== filterCategory) return false;
      if (search && !s.name.toLowerCase().includes(search.toLowerCase()) && !s.description.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [skills, search, filterCategory]);

  const totalUsage = useMemo(() => skills.reduce((sum, s) => sum + s.usage_count, 0), [skills]);
  const enabledCount = useMemo(() => skills.filter((s) => s.enabled).length, [skills]);

  const toggleSkill = async (skillId: string) => {
    try {
      await fetch(`/api/skills/${skillId}/toggle`, { method: "POST" });
      fetchSkills();
    } catch (err) {
      console.error("Failed to toggle skill:", err);
    }
  };

  const deleteSkill = async (skillId: string, name: string) => {
    if (!confirm(`Delete skill "${name}"?`)) return;
    try {
      await fetch(`/api/skills/${skillId}`, { method: "DELETE" });
      fetchSkills();
    } catch (err) {
      console.error("Failed to delete skill:", err);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" /></div>;

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="panel-card">
          <div className="text-2xl font-bold text-accent">{skills.length}</div>
          <div className="text-sm text-text-muted">Total Skills</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-status-success">{enabledCount}</div>
          <div className="text-sm text-text-muted">Enabled</div>
        </div>
        <div className="panel-card">
          <div className="text-2xl font-bold text-text-primary">{totalUsage}</div>
          <div className="text-sm text-text-muted">Total Usages</div>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="panel-card bg-status-error/10 border-status-error text-status-error text-sm p-3">
          {error}
        </div>
      )}

      {/* Search and filter */}
      <div className="flex gap-3">
        <input
          type="text"
          placeholder="Search skills..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 bg-bg-3 border border-border rounded-lg px-4 py-2 text-sm focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all"
        />
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="bg-bg-3 border border-border rounded-lg px-4 py-2 text-sm focus:border-accent focus:ring-1 focus:ring-accent/20 transition-all"
        >
          {categories.map((cat) => (
            <option key={cat} value={cat}>{cat === "all" ? "All Categories" : cat}</option>
          ))}
        </select>
      </div>

      {/* Skills list */}
      <div className="space-y-3">
        {filteredSkills.map((skill) => (
          <div key={skill.id} className="panel-card flex items-center justify-between hover:scale-[1.01] transition-all">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <span className={`w-2.5 h-2.5 rounded-full ${skill.enabled ? "bg-status-success" : "bg-text-muted"}`} />
                <h3 className="font-medium text-text-primary">{skill.name}</h3>
                <span className="text-xs bg-bg-3 px-2 py-0.5 rounded-full text-text-muted">{skill.category || "general"}</span>
                <span className="text-xs text-text-muted">v{skill.version}</span>
                <span className="text-xs bg-bg-3 px-2 py-0.5 rounded-full text-text-muted">{skill.source}</span>
              </div>
              <p className="text-sm text-text-secondary mt-1 ml-5">{skill.description}</p>
              {skill.trigger_conditions.length > 0 && (
                <div className="flex gap-2 mt-1 ml-5 flex-wrap">
                  {skill.trigger_conditions.map((tc, i) => (
                    <span key={i} className="text-xs bg-accent/10 px-2 py-0.5 rounded-full text-accent">{tc}</span>
                  ))}
                </div>
              )}
              <div className="flex gap-4 mt-1 ml-5 text-xs text-text-muted">
                <span>{skill.usage_count} uses</span>
                <span>{skill.success_rate > 0 ? `${(skill.success_rate * 100).toFixed(0)}% success` : "N/A"}</span>
                {skill.last_used && <span>last: {new Date(skill.last_used).toLocaleDateString()}</span>}
              </div>
            </div>
            <div className="flex items-center gap-3 text-right">
              <button
                onClick={() => toggleSkill(skill.id)}
                className={`relative w-12 h-6 rounded-full transition-all ${skill.enabled ? "bg-accent" : "bg-bg-3 border border-border"}`}
                title={skill.enabled ? "Disable" : "Enable"}
              >
                <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-all ${skill.enabled ? "left-6" : "left-0.5"}`} />
              </button>
              <button
                onClick={() => deleteSkill(skill.id, skill.name)}
                className="text-text-muted hover:text-status-error transition-colors"
                title="Delete"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>
        ))}
      </div>

      {filteredSkills.length === 0 && (
        <div className="text-center py-8 text-text-muted text-sm">
          {skills.length === 0
            ? "No skills yet. Skills are created automatically from self-improvement reflection."
            : "No skills match your search."}
        </div>
      )}
    </div>
  );
}
