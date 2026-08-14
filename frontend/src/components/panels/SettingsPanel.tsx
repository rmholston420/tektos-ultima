/**
 * Tektos-Ultima v1 — Settings & Preferences Panel
 *
 * Workflow-based settings UI organized by category:
 * - Model preferences (default model, context window, max tokens)
 * - Appearance (theme, font size, density)
 * - System (auto-save interval, backup settings)
 * - Plugins (enable/disable per plugin)
 *
 * Design: Collapsible accordion sections with smooth animations.
 * Hidden complexity revealed through progressive disclosure.
 */

"use client";

import React, { useState } from "react";
import { api, type PluginInfo } from "@/lib/api";

const SECTION_ICONS = {
  models: "🧠",
  appearance: "🎨",
  system: "⚙️",
  plugins: "🔌",
  keys: "🔑",
} as const;

interface SettingsPanelProps {
  initialConfig?: Record<string, any>;
}

export function SettingsPanel({ initialConfig }: SettingsPanelProps) {
  const [config, setConfig] = useState<Record<string, any>>(initialConfig || {});
  const [plugins, setPlugins] = useState<PluginInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string>("models");

  const toggleSection = (section: string) => {
    setExpanded(expanded === section ? "" : section);
  };

  const handleSave = async (section: string, key: string, value: any) => {
    try {
      await api.updateConfig(`${section}.${key}`, value);
      setConfig((prev) => ({ ...prev, [section]: { ...prev[section], [key]: value } }));
    } catch (err) {
      console.error("Failed to save config:", err);
    }
  };

  const handleTogglePlugin = async (name: string, enabled: boolean) => {
    try {
      await api.togglePlugin(name, !enabled);
      setPlugins((prev) => prev.map((p) => p.name === name ? { ...p, enabled: !p.enabled } : p));
    } catch (err) {
      console.error("Failed to toggle plugin:", err);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold text-text-primary">Settings & Preferences</h2>

      {Object.entries(SECTION_ICONS).map(([section, icon]) => (
        <div key={section} className="panel overflow-hidden">
          <button
            onClick={() => toggleSection(section)}
            className="w-full flex items-center justify-between py-3"
          >
            <div className="flex items-center gap-3">
              <span className="text-xl">{icon}</span>
              <span className="text-sm font-medium text-text-primary capitalize">{section}</span>
            </div>
            <svg
              className={`w-5 h-5 text-text-muted transition-transform duration-200 ${expanded === section ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {expanded === section && (
            <div className="pt-2 pb-4 space-y-4">
              {section === "models" && (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">Default Model</label>
                      <select
                        className="w-full bg-bg-3 border border-border rounded-lg px-3 py-2 text-sm"
                        defaultValue={config.models?.default_model}
                        onChange={(e) => handleSave("models", "default_model", e.target.value)}
                      >
                        <option value="qwen3.6-35b-a3b">Qwen3.6-35B-A3B</option>
                        <option value="qwen3-coder-30b">Qwen3-Coder-30B</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-text-muted mb-1 block">Context Window</label>
                      <input
                        type="number"
                        className="w-full bg-bg-3 border border-border rounded-lg px-3 py-2 text-sm"
                        defaultValue={config.models?.context_window}
                        onChange={(e) => handleSave("models", "context_window", parseInt(e.target.value))}
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">Max Tokens</label>
                    <input
                      type="range"
                      min="1000"
                      max="32000"
                      step="1000"
                      className="w-full"
                      defaultValue={config.models?.max_tokens}
                      onChange={(e) => handleSave("models", "max_tokens", parseInt(e.target.value))}
                    />
                    <div className="flex justify-between text-xs text-text-muted mt-1">
                      <span>1K</span>
                      <span className="text-text-primary">{config.models?.max_tokens || 8000}</span>
                      <span>32K</span>
                    </div>
                  </div>
                </>
              )}

              {section === "appearance" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">Font Size</label>
                    <select
                      className="w-full bg-bg-3 border border-border rounded-lg px-3 py-2 text-sm"
                      defaultValue={config.appearance?.font_size}
                      onChange={(e) => handleSave("appearance", "font_size", e.target.value)}
                    >
                      <option value="small">Small (12px)</option>
                      <option value="medium">Medium (14px)</option>
                      <option value="large">Large (16px)</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">UI Density</label>
                    <select
                      className="w-full bg-bg-3 border border-border rounded-lg px-3 py-2 text-sm"
                      defaultValue={config.appearance?.density}
                      onChange={(e) => handleSave("appearance", "density", e.target.value)}
                    >
                      <option value="comfortable">Comfortable</option>
                      <option value="compact">Compact</option>
                      <option value="dense">Dense</option>
                    </select>
                  </div>
                </div>
              )}

              {section === "system" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-text-muted mb-1 block">Auto-Save Interval (minutes)</label>
                    <input
                      type="number"
                      className="w-full bg-bg-3 border border-border rounded-lg px-3 py-2 text-sm"
                      defaultValue={config.system?.auto_save_interval}
                      onChange={(e) => handleSave("system", "auto_save_interval", parseInt(e.target.value))}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      className="rounded"
                      defaultChecked={config.system?.enable_backups}
                      onChange={(e) => handleSave("system", "enable_backups", e.target.checked)}
                    />
                    <span className="text-sm text-text-secondary">Enable automatic backups</span>
                  </div>
                </div>
              )}

              {section === "plugins" && (
                <div className="space-y-2">
                  {plugins.map((plugin) => (
                    <div key={plugin.name} className="flex items-center justify-between py-2 px-3 rounded-lg bg-bg-3">
                      <div>
                        <div className="text-sm text-text-primary">{plugin.name}</div>
                        <div className="text-xs text-text-muted">{plugin.description}</div>
                      </div>
                      <button
                        onClick={() => handleTogglePlugin(plugin.name, plugin.enabled)}
                        className={`w-10 h-6 rounded-full transition-all relative ${plugin.enabled ? "bg-accent" : "bg-bg-5"}`}
                      >
                        <div
                          className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-all ${
                            plugin.enabled ? "right-0.5" : "left-0.5"
                          }`}
                        />
                      </button>
                    </div>
                  ))}
                  {plugins.length === 0 && (
                    <div className="text-center py-4 text-text-muted text-sm">Loading plugins...</div>
                  )}
                </div>
              )}

              {section === "keys" && (
                <div className="space-y-3">
                  <p className="text-sm text-text-secondary">API keys are stored securely and encrypted at rest.</p>
                  <div className="grid grid-cols-1 gap-3">
                    {["searxng", "tavily", "farfalle", "gmail"].map((key) => (
                      <div key={key} className="flex items-center justify-between py-2 px-3 rounded-lg bg-bg-3">
                        <span className="text-sm text-text-primary capitalize">{key} API Key</span>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono text-text-muted">
                            ••••••••••••{key.length}
                          </span>
                          <button className="text-xs text-accent hover:text-accent-hover">Change</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
