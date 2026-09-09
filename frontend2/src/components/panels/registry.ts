"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";

const asDyn = (loader: () => Promise<{ default: unknown } | Record<string, unknown>>): ComponentType => {
  return dynamic(async () => {
    const mod = await loader();
    // Prefer named export matching the panel filename convention, then default.
    const cand = (Object.values(mod)[0] as ComponentType | undefined) ?? (mod as { default: ComponentType }).default;
    return { default: cand as ComponentType };
  }, { ssr: false });
};

export interface PanelMeta {
  id: string;
  label: string;
  section: string;
  Component: ComponentType;
}

/**
 * Registry of dashboard panels ported from the legacy tree. Each panel
 * is dynamic-imported so the panel bundle only loads when the panel
 * activates. Sections group panels for navigation.
 */
export const PANELS: PanelMeta[] = [
  // Overview
  { id: "overview",         label: "Overview",           section: "Overview",   Component: asDyn(() => import("./SystemDashboard").then((m) => ({ default: m.SystemDashboard }))) },

  // System
  { id: "nervous",          label: "Nervous System",     section: "System",     Component: asDyn(() => import("./NervousSystemPanel").then((m) => ({ default: m.NervousSystemPanel }))) },
  { id: "metabolism",       label: "Metabolism",         section: "System",     Component: asDyn(() => import("./MetabolismPanel").then((m) => ({ default: m.MetabolismPanel }))) },
  { id: "schema",           label: "Schema Evolution",   section: "System",     Component: asDyn(() => import("./SchemaEvolutionPanel").then((m) => ({ default: m.SchemaEvolutionPanel }))) },
  { id: "immune",           label: "Immune",             section: "System",     Component: asDyn(() => import("./ImmuneSystemPanel").then((m) => ({ default: m.ImmuneSystemPanel }))) },
  { id: "self_repair",      label: "Self-Repair",        section: "System",     Component: asDyn(() => import("./SelfRepairPanel").then((m) => ({ default: m.SelfRepairPanel }))) },
  { id: "thermal",          label: "Thermal",            section: "System",     Component: asDyn(() => import("./ThermalPanel").then((m) => ({ default: m.ThermalPanel }))) },
  { id: "self_improvement", label: "Self-Improvement",   section: "System",     Component: asDyn(() => import("./SelfImprovementPanel").then((m) => ({ default: m.SelfImprovementPanel }))) },

  // Observability
  { id: "telemetry",        label: "Telemetry",          section: "Observability", Component: asDyn(() => import("./TelemetryPanel").then((m) => ({ default: m.TelemetryPanel }))) },
  { id: "observability",    label: "Observability",      section: "Observability", Component: asDyn(() => import("./ObservabilityPanel").then((m) => ({ default: m.ObservabilityPanel }))) },
  { id: "logs",             label: "Logs",               section: "Observability", Component: asDyn(() => import("./LogsPanel").then((m) => ({ default: m.LogsPanel }))) },
  { id: "graph",            label: "System Graph",       section: "Observability", Component: asDyn(() => import("../graphs/BiologicalGraph").then((m) => ({ default: m.BiologicalGraph }))) },

  // Models & Inference
  { id: "router",           label: "Model Router",       section: "Models",     Component: asDyn(() => import("./ModelRouterPanel").then((m) => ({ default: m.ModelRouterPanel }))) },
  { id: "inference",        label: "Inference",          section: "Models",     Component: asDyn(() => import("./InferencePanel").then((m) => ({ default: m.InferencePanel }))) },
  { id: "embedder",         label: "Embedder",           section: "Models",     Component: asDyn(() => import("./EmbedderPanel").then((m) => ({ default: m.EmbedderPanel }))) },
  { id: "vision",           label: "Vision",             section: "Models",     Component: asDyn(() => import("./VisionPanel").then((m) => ({ default: m.VisionPanel }))) },
  { id: "evaluation",       label: "Evaluation",         section: "Models",     Component: asDyn(() => import("./EvaluationPanel").then((m) => ({ default: m.EvaluationPanel }))) },

  // Context & Memory
  { id: "context",          label: "Context",            section: "Context & Memory", Component: asDyn(() => import("./ContextPanel").then((m) => ({ default: m.ContextPanel }))) },
  { id: "context_curator",  label: "Context Curator",    section: "Context & Memory", Component: asDyn(() => import("./ContextCuratorPanel").then((m) => ({ default: m.ContextCuratorPanel }))) },
  { id: "memory",           label: "Memory",             section: "Context & Memory", Component: asDyn(() => import("./MemoryPanel").then((m) => ({ default: m.MemoryPanel }))) },
  { id: "memory_system",    label: "Memory System",      section: "Context & Memory", Component: asDyn(() => import("./MemorySystemPanel").then((m) => ({ default: m.MemorySystemPanel }))) },
  { id: "hindsight",        label: "Hindsight",          section: "Context & Memory", Component: asDyn(() => import("./HindsightPanel").then((m) => ({ default: m.HindsightPanel }))) },

  // Retrieval
  { id: "rag",              label: "RAG",                section: "Retrieval",  Component: asDyn(() => import("./RagPanel").then((m) => ({ default: m.RagPanel }))) },
  { id: "rag_retriever",    label: "RAG Retriever",      section: "Retrieval",  Component: asDyn(() => import("./RagRetrieverPanel").then((m) => ({ default: m.RagRetrieverPanel }))) },
  { id: "repo_map",         label: "Repo Map",           section: "Retrieval",  Component: asDyn(() => import("./RepoMapPanel").then((m) => ({ default: m.RepoMapPanel }))) },

  // Agents & Tools
  { id: "planner",          label: "Planner",            section: "Agents & Tools", Component: asDyn(() => import("./PlannerPanel").then((m) => ({ default: m.PlannerPanel }))) },
  { id: "multi_agent",      label: "Multi-Agent",        section: "Agents & Tools", Component: asDyn(() => import("./MultiAgentOrchestratorPanel").then((m) => ({ default: m.MultiAgentOrchestratorPanel }))) },
  { id: "tools",            label: "Tools",              section: "Agents & Tools", Component: asDyn(() => import("./ToolsPanel").then((m) => ({ default: m.ToolsPanel }))) },
  { id: "tool_router",      label: "Tool Router",        section: "Agents & Tools", Component: asDyn(() => import("./ToolRouterPanel").then((m) => ({ default: m.ToolRouterPanel }))) },
  { id: "skills",           label: "Skills",             section: "Agents & Tools", Component: asDyn(() => import("./SkillsPanel").then((m) => ({ default: m.SkillsPanel }))) },
  { id: "axioms",           label: "Axioms",             section: "Agents & Tools", Component: asDyn(() => import("./AxiomsPanel").then((m) => ({ default: m.AxiomsPanel }))) },

  // Storage
  { id: "database",         label: "Database",           section: "Storage",    Component: asDyn(() => import("./DatabasePanel").then((m) => ({ default: m.DatabasePanel }))) },
  { id: "postgres",         label: "PostgreSQL",         section: "Storage",    Component: asDyn(() => import("./PostgresPanel").then((m) => ({ default: m.PostgresPanel }))) },
  { id: "neo4j",            label: "Neo4j",              section: "Storage",    Component: asDyn(() => import("./Neo4jPanel").then((m) => ({ default: m.Neo4jPanel }))) },
  { id: "redis",            label: "Redis",              section: "Storage",    Component: asDyn(() => import("./RedisPanel").then((m) => ({ default: m.RedisPanel }))) },

  // Integrations
  { id: "mcp",              label: "MCP",                section: "Integrations", Component: asDyn(() => import("./McpPanel").then((m) => ({ default: m.McpPanel }))) },
  { id: "hooks",            label: "Hooks",              section: "Integrations", Component: asDyn(() => import("./HooksPanel").then((m) => ({ default: m.HooksPanel }))) },
  { id: "scheduling",       label: "Scheduling",         section: "Integrations", Component: asDyn(() => import("./SchedulingPanel").then((m) => ({ default: m.SchedulingPanel }))) },

  // Configuration
  { id: "config",           label: "Config",             section: "Configuration", Component: asDyn(() => import("./ConfigPanel").then((m) => ({ default: m.ConfigPanel }))) },
  { id: "keys",             label: "Keys",               section: "Configuration", Component: asDyn(() => import("./KeysPanel").then((m) => ({ default: m.KeysPanel }))) },
  { id: "settings",         label: "Settings",           section: "Configuration", Component: asDyn(() => import("./SettingsPanel").then((m) => ({ default: m.SettingsPanel }))) },
];

export function getPanel(id: string): PanelMeta | undefined {
  return PANELS.find((p) => p.id === id);
}
