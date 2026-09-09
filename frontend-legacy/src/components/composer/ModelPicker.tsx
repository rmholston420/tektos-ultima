/**
 * Tektos-Ultima v1 — Model Picker
 *
 * Dropdown for selecting the active LLM during a session.
 * Shows model name, role (Coder/Planner/General/Fast/Vision),
 * and a brief description of each model's specialty.
 */

"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";

// ---------------------------------------------------------------------------
// Model definitions
// ---------------------------------------------------------------------------

export interface ModelInfo {
  id: string;
  name: string;
  role: "Coder" | "Planner" | "General" | "Fast" | "Vision" | "Embedding";
  description: string;
  params: string;
  caps: string[];
  recommended?: boolean;
}

export const MODEL_OPTIONS: ModelInfo[] = [
  // Coder — optimized for code generation and tool use
  {
    id: "qwen3-coder:30b",
    name: "qwen3-coder:30b",
    role: "Coder",
    description: "30.5B params. RL-trained on SWE-bench. Fast code generation, file editing, tool use. Best for implementation tasks.",
    params: "30.5B",
    caps: ["tools", "completion"],
  },
  {
    id: "qwen3.6:35b-a3b-mtp-coder",
    name: "qwen3.6:35b-a3b",
    role: "Coder",
    description: "35.5B params. Multi-token prediction optimized for agentic coding. Strongest coding model available.",
    params: "35.5B",
    caps: ["tools", "completion", "thinking", "vision"],
    recommended: true,
  },
  // Planner — strong reasoning and chain-of-thought
  {
    id: "deepseek-r1:32b",
    name: "deepseek-r1:32b",
    role: "Planner",
    description: "32.8B params. Deep reasoning model. Best for decomposition, planning, architecture, and chain-of-thought tasks.",
    params: "32.8B",
    caps: ["completion", "thinking"],
  },
  {
    id: "glm-4.7-flash:q4_K_M",
    name: "glm-4.7-flash",
    role: "Planner",
    description: "29.9B params. Strong reasoning with tool use. Good balance of speed and depth for planning tasks.",
    params: "29.9B",
    caps: ["tools", "completion", "thinking"],
  },
  // General — balanced capabilities
  {
    id: "qwen3.6:35b-a3b-mtp-q4_K_M",
    name: "qwen3.6:35b-a3b (Q4)",
    role: "General",
    description: "35.5B params. Balanced generalist with multi-token prediction. Good for diverse tasks.",
    params: "35.5B",
    caps: ["tools", "completion", "thinking", "vision"],
  },
  {
    id: "qwen3.6:35b",
    name: "qwen3.6:35b",
    role: "General",
    description: "36.0B params. Full Qwen 3.6. Vision-capable, tool-use, thinking. Versatile all-rounder.",
    params: "36.0B",
    caps: ["tools", "completion", "thinking", "vision"],
  },
  // Vision — models with vision capabilities
  {
    id: "qwen3.6:27b-coder",
    name: "qwen3.6:27b-coder",
    role: "Vision",
    description: "27.8B params. Code-specialized with vision. Read diagrams, screenshots, and code together.",
    params: "27.8B",
    caps: ["tools", "completion", "thinking", "vision"],
  },
  // Fast — lightweight models for quick responses
  {
    id: "qwen3.5:9b-q8_0",
    name: "qwen3.5:9b",
    role: "Fast",
    description: "9.7B params. Fast and responsive. Good for quick tasks, brainstorming, and iterative refinement.",
    params: "9.7B",
    caps: ["tools", "completion", "thinking", "vision"],
  },
  {
    id: "lfm2.5:8b",
    name: "lfm2.5:8b",
    role: "Fast",
    description: "8.5B params. High context (256K). Fast responses with deep context retention.",
    params: "8.5B",
    caps: ["tools", "completion", "thinking"],
  },
  {
    id: "qwen3.5:2b-q8_0",
    name: "qwen3.5:2b",
    role: "Fast",
    description: "2.3B params. Lightning fast. Best for simple Q&A and quick tasks.",
    params: "2.3B",
    caps: ["tools", "completion", "thinking", "vision"],
  },
];

// Role color mapping
const ROLE_COLORS: Record<string, string> = {
  Coder: "text-accent",
  Planner: "text-status-warning",
  General: "text-text-primary",
  Fast: "text-text-muted",
  Vision: "text-accent",
  Embedding: "text-text-muted",
};

const ROLE_ICONS: Record<string, string> = {
  Coder: "⟨/⟩",
  Planner: "◈",
  General: "◉",
  Fast: "⚡",
  Vision: "◐",
  Embedding: "◆",
};

// ---------------------------------------------------------------------------
// ModelPicker component
// ---------------------------------------------------------------------------

interface ModelPickerProps {
  currentModel: string;
  onModelChange: (modelId: string) => void;
  disabled?: boolean;
}

export function ModelPicker({ currentModel, onModelChange, disabled = false }: ModelPickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Find current model info
  const current = MODEL_OPTIONS.find((m) => m.id === currentModel) || MODEL_OPTIONS[0];

  // Filter models
  const filtered = MODEL_OPTIONS.filter(
    (m) =>
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      m.description.toLowerCase().includes(search.toLowerCase()) ||
      m.role.toLowerCase().includes(search.toLowerCase())
  );

  // Group by role
  const grouped = filtered.reduce((acc, m) => {
    if (!acc[m.role]) acc[m.role] = [];
    acc[m.role].push(m);
    return acc;
  }, {} as Record<string, ModelInfo[]>);

  // Close on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
        setSearch("");
      }
    };
    if (isOpen) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isOpen]);

  const handleSelect = useCallback(
    (modelId: string) => {
      onModelChange(modelId);
      setIsOpen(false);
      setSearch("");
    },
    [onModelChange]
  );

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
      <button
        ref={buttonRef}
        onClick={() => {
          if (!disabled) setIsOpen(!isOpen);
        }}
        disabled={disabled}
        className={`
          flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium
          transition-all border
          ${
            isOpen
              ? "bg-surface-active border-border shadow-sm"
              : "bg-surface border-border/50 hover:border-border"
          }
          ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
        `}
        title="Select model"
      >
        <span className={`${ROLE_COLORS[current.role]} text-sm`}>
          {ROLE_ICONS[current.role]}
        </span>
        <span className="text-text-primary">{current.name}</span>
        <span className={`text-[10px] ${ROLE_COLORS[current.role]} font-medium`}>
          {current.role}
        </span>
        <svg
          className={`w-3 h-3 text-text-muted/50 transition-transform ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute bottom-full left-0 mb-2 w-80 bg-bg-3 border border-border rounded-xl shadow-xl overflow-hidden z-50">
          {/* Search */}
          <div className="p-2 border-b border-border">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search models..."
              className="w-full px-2 py-1.5 text-xs bg-bg-4 border border-border rounded-lg text-text-primary placeholder-text-muted/50 focus:outline-none focus:border-accent/50"
            />
          </div>

          {/* Model list */}
          <div className="max-h-80 overflow-y-auto">
            {Object.entries(grouped).map(([role, models]) => (
              <div key={role}>
                <div className={`px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider ${ROLE_COLORS[role]} bg-bg-4/50`}>
                  {ROLE_ICONS[role]} {role}
                </div>
                {models.map((model) => (
                  <button
                    key={model.id}
                    onClick={() => handleSelect(model.id)}
                    className={`
                      w-full px-3 py-2 text-left hover:bg-surface-hover transition-colors
                      ${model.id === currentModel ? "bg-accent/5 border-r-2 border-accent" : ""}
                    `}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-xs font-medium text-text-primary">
                        {model.name}
                      </span>
                      <div className="flex items-center gap-1">
                        {model.recommended && (
                          <span className="text-[9px] px-1 py-0.5 rounded bg-accent/20 text-accent font-medium">
                            REC
                          </span>
                        )}
                        <span className={`text-[10px] ${ROLE_COLORS[model.role]}`}>
                          {model.params}
                        </span>
                      </div>
                    </div>
                    <p className="text-[10px] text-text-muted/60 leading-relaxed line-clamp-2">
                      {model.description}
                    </p>
                    <div className="flex items-center gap-1 mt-1">
                      {model.caps.slice(0, 3).map((cap) => (
                        <span
                          key={cap}
                          className="text-[9px] px-1 py-0.5 rounded bg-bg-4 text-text-muted/50"
                        >
                          {cap}
                        </span>
                      ))}
                      {model.caps.length > 3 && (
                        <span className="text-[9px] text-text-muted/40">
                          +{model.caps.length - 3}
                        </span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="px-3 py-2 border-t border-border bg-bg-4/50 text-[10px] text-text-muted/40 text-center">
            {filtered.length} models available
          </div>
        </div>
      )}
    </div>
  );
}
