/**
 * Tektos-Ultima v1 — Skills Panel
 *
 * Interactive skill management with search, categorization, and activation.
 * Shows skill status, dependencies, and usage statistics.
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
  dependencies: string[];
  usageCount: number;
  lastUsed: string;
}

export function SkillsPanel() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterCategory, setFilterCategory] = useState("all");

  useEffect(() => {
    fetch("/api/skills")
      .then((r) => r.json())
      .then((data) => {
        setSkills(data.skills || []);
        setLoading(false);
      })
      .catch(() => {
        setSkills([]);
        setLoading(false);
      });
  }, []);

  const categories = useMemo(() => {
    const cats = new Set(skills.map((s) => s.category));
    return ["all", ...Array.from(cats)];
  }, [skills]);

  const filteredSkills = useMemo(() => {
    return skills.filter((s) => {
      if (filterCategory !== "all" && s.category !== filterCategory) return false;
      if (search && !s.name.toLowerCase().includes(search.toLowerCase()) && !s.description.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [skills, search, filterCategory]);

  const totalUsage = useMemo(() => skills.reduce((sum, s) => sum + s.usageCount, 0), [skills]);
  const enabledCount = useMemo(() => skills.filter((s) => s.enabled).length, [skills]);

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
                <span className="text-xs bg-bg-3 px-2 py-0.5 rounded-full text-text-muted">{skill.category}</span>
                <span className="text-xs text-text-muted">v{skill.version}</span>
              </div>
              <p className="text-sm text-text-secondary mt-1 ml-5">{skill.description}</p>
              {skill.dependencies.length > 0 && (
                <div className="flex gap-2 mt-1 ml-5">
                  {skill.dependencies.map((dep) => (
                    <span key={dep} className="text-xs bg-bg-3 px-2 py-0.5 rounded-full text-text-muted">{dep}</span>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center gap-4 text-right">
              <div>
                <div className="text-sm font-medium text-text-primary">{skill.usageCount}</div>
                <div className="text-xs text-text-muted">uses</div>
              </div>
              <button
                onClick={() => {
                  setSkills(skills.map((s) => s.id === skill.id ? { ...s, enabled: !s.enabled } : s));
                }}
                className={`relative w-12 h-6 rounded-full transition-all ${skill.enabled ? "bg-accent" : "bg-bg-3 border border-border"}`}
              >
                <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-all ${skill.enabled ? "left-6" : "left-0.5"}`} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {filteredSkills.length === 0 && (
        <div className="text-center py-8 text-text-muted text-sm">No skills found</div>
      )}
    </div>
  );
}
