/**
 * Tektos-Ultima v1 — Dashboard Route
 *
 * Standalone Next.js route for /dashboard.
 * Mirrors the dashboard view from the main page.tsx.
 */

"use client";

import React, { useState, useEffect, useMemo } from "react";
import dynamic from "next/dynamic";

// Dynamic imports for client-only components (SSR-safe)
const DynamicSystemDashboard = dynamic(() => import("@/components/panels/SystemDashboard").then((m) => m.SystemDashboard), { ssr: false });
const DynamicTelemetryPanel = dynamic(() => import("@/components/panels/TelemetryPanel").then((m) => m.TelemetryPanel), { ssr: false });
const DynamicModelRouterPanel = dynamic(() => import("@/components/panels/ModelRouterPanel").then((m) => m.ModelRouterPanel), { ssr: false });
const DynamicAxiomsPanel = dynamic(() => import("@/components/panels/AxiomsPanel").then((m) => m.AxiomsPanel), { ssr: false });
const DynamicMemorySystemPanel = dynamic(() => import("@/components/panels/MemoryPanel").then((m) => m.MemoryPanel), { ssr: false });
const DynamicSkillsPanel = dynamic(() => import("@/components/panels/SkillsPanel").then((m) => m.SkillsPanel), { ssr: false });
const DynamicConfigPanel = dynamic(() => import("@/components/panels/ConfigPanel").then((m) => m.ConfigPanel), { ssr: false });
const DynamicKeysPanel = dynamic(() => import("@/components/panels/KeysPanel").then((m) => m.KeysPanel), { ssr: false });
const DynamicMcpPanel = dynamic(() => import("@/components/panels/McpPanel").then((m) => m.McpPanel), { ssr: false });
const DynamicHooksPanel = dynamic(() => import("@/components/panels/HooksPanel").then((m) => m.HooksPanel), { ssr: false });
const DynamicLogsPanel = dynamic(() => import("@/components/panels/LogsPanel").then((m) => m.LogsPanel), { ssr: false });
const DynamicSchedulingPanel = dynamic(() => import("@/components/panels/SchedulingPanel").then((m) => m.SchedulingPanel), { ssr: false });
const DynamicSettingsPanel = dynamic(() => import("@/components/panels/SettingsPanel").then((m) => m.SettingsPanel), { ssr: false });
const DynamicNervousSystemPanel = dynamic(() => import("@/components/panels/NervousSystemPanel").then((m) => m.NervousSystemPanel), { ssr: false });
const DynamicToolsPanel = dynamic(() => import("@/components/panels/ToolsPanel").then((m) => m.ToolsPanel), { ssr: false });
const DynamicMetabolismPanel = dynamic(() => import("@/components/panels/MetabolismPanel").then((m) => m.MetabolismPanel), { ssr: false });
const DynamicSchemaEvolutionPanel = dynamic(() => import("@/components/panels/SchemaEvolutionPanel").then((m) => m.SchemaEvolutionPanel), { ssr: false });
const DynamicImmuneSystemPanel = dynamic(() => import("@/components/panels/ImmuneSystemPanel").then((m) => m.ImmuneSystemPanel), { ssr: false });
const DynamicDatabasePanel = dynamic(() => import("@/components/panels/DatabasePanel").then((m) => m.DatabasePanel), { ssr: false });
const DynamicSelfRepairPanel = dynamic(() => import("@/components/panels/SelfRepairPanel").then((m) => m.SelfRepairPanel), { ssr: false });
const DynamicThermalPanel = dynamic(() => import("@/components/panels/ThermalPanel").then((m) => m.ThermalPanel), { ssr: false });
const DynamicSelfImprovementPanel = dynamic(() => import("@/components/panels/SelfImprovementPanel").then((m) => m.SelfImprovementPanel), { ssr: false });
const DynamicPlannerPanel = dynamic(() => import("@/components/panels/PlannerPanel").then((m) => m.PlannerPanel), { ssr: false });
const DynamicBiologicalGraph = dynamic(() => import("@/components/graphs/BiologicalGraph").then((m) => m.BiologicalGraph), { ssr: false });

// New panels — backend modules without frontend coverage
const DynamicEmbedderPanel = dynamic(() => import("@/components/panels/EmbedderPanel").then((m) => m.EmbedderPanel), { ssr: false });
const DynamicInferencePanel = dynamic(() => import("@/components/panels/InferencePanel").then((m) => m.InferencePanel), { ssr: false });
const DynamicContextPanel = dynamic(() => import("@/components/panels/ContextPanel").then((m) => m.ContextPanel), { ssr: false });
const DynamicContextCuratorPanel = dynamic(() => import("@/components/panels/ContextCuratorPanel").then((m) => m.ContextCuratorPanel), { ssr: false });
const DynamicEvaluationPanel = dynamic(() => import("@/components/panels/EvaluationPanel").then((m) => m.EvaluationPanel), { ssr: false });
const DynamicMultiAgentOrchestratorPanel = dynamic(() => import("@/components/panels/MultiAgentOrchestratorPanel").then((m) => m.MultiAgentOrchestratorPanel), { ssr: false });
const DynamicObservabilityPanel = dynamic(() => import("@/components/panels/ObservabilityPanel").then((m) => m.ObservabilityPanel), { ssr: false });
const DynamicRagPanel = dynamic(() => import("@/components/panels/RagPanel").then((m) => m.RagPanel), { ssr: false });
const DynamicRagRetrieverPanel = dynamic(() => import("@/components/panels/RagRetrieverPanel").then((m) => m.RagRetrieverPanel), { ssr: false });
const DynamicRepoMapPanel = dynamic(() => import("@/components/panels/RepoMapPanel").then((m) => m.RepoMapPanel), { ssr: false });
const DynamicToolRouterPanel = dynamic(() => import("@/components/panels/ToolRouterPanel").then((m) => m.ToolRouterPanel), { ssr: false });
const DynamicVisionPanel = dynamic(() => import("@/components/panels/VisionPanel").then((m) => m.VisionPanel), { ssr: false });

// External backend panels
const DynamicNeo4jPanel = dynamic(() => import("@/components/panels/Neo4jPanel").then((m) => m.Neo4jPanel), { ssr: false });
const DynamicPostgresPanel = dynamic(() => import("@/components/panels/PostgresPanel").then((m) => m.PostgresPanel), { ssr: false });
const DynamicRedisPanel = dynamic(() => import("@/components/panels/RedisPanel").then((m) => m.RedisPanel), { ssr: false });
const DynamicHindsightPanel = dynamic(() => import("@/components/panels/HindsightPanel").then((m) => m.HindsightPanel), { ssr: false });

// ---------------------------------------------------------------------------
// Dashboard tabs (same as page.tsx)
// ---------------------------------------------------------------------------

type DashboardTab = "overview" | "nervous" | "tools" | "metabolism" | "schema" | "graph" | "telemetry" | "router" | "axioms" | "memory" | "skills" | "config" | "keys" | "mcp" | "hooks" | "logs" | "scheduling" | "settings" | "immune" | "database" | "self_repair" | "thermal" | "self_improvement" | "planner" | "embedder" | "inference" | "context" | "context_curator" | "evaluation" | "multi_agent" | "observability" | "rag" | "rag_retriever" | "repo_map" | "tool_router" | "vision" | "neo4j" | "postgres" | "redis" | "hindsight";

const DASHBOARD_TABS: { id: DashboardTab; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "◈" },
  { id: "nervous", label: "Nervous System", icon: "⚡" },
  { id: "tools", label: "Tools", icon: "🔧" },
  { id: "metabolism", label: "Metabolism", icon: "♻" },
  { id: "schema", label: "Schema", icon: "🏗" },
  { id: "graph", label: "System Graph", icon: "⬡" },
  { id: "telemetry", label: "Telemetry", icon: "◉" },
  { id: "router", label: "Router", icon: "⊘" },
  { id: "axioms", label: "Axioms", icon: "∞" },
  { id: "memory", label: "Memory", icon: "◐" },
  { id: "skills", label: "Skills", icon: "★" },
  { id: "config", label: "Config", icon: "⚙" },
  { id: "keys", label: "Keys", icon: "🔑" },
  { id: "mcp", label: "MCP", icon: "◆" },
  { id: "hooks", label: "Hooks", icon: "⚓" },
  { id: "logs", label: "Logs", icon: "▤" },
  { id: "scheduling", label: "Schedule", icon: "⏱" },
  { id: "settings", label: "Settings", icon: "⚙" },
  { id: "immune", label: "Immune", icon: "🛡" },
  { id: "database", label: "Database", icon: "🗄" },
  { id: "self_repair", label: "Self-Repair", icon: "🔧" },
  { id: "thermal", label: "Thermal", icon: "🌡️" },
  { id: "self_improvement", label: "Self-Improvement", icon: "🧠" },
  { id: "planner", label: "Planner", icon: "📋" },
  { id: "embedder", label: "Embedder", icon: "🔤" },
  { id: "inference", label: "Inference", icon: "🧠" },
  { id: "context", label: "Context", icon: "📋" },
  { id: "context_curator", label: "Context Curator", icon: "📑" },
  { id: "evaluation", label: "Evaluation", icon: "📊" },
  { id: "multi_agent", label: "Multi-Agent", icon: "🤖" },
  { id: "observability", label: "Observability", icon: "📊" },
  { id: "rag", label: "RAG", icon: "🔍" },
  { id: "rag_retriever", label: "RAG Retriever", icon: "📚" },
  { id: "repo_map", label: "Repo Map", icon: "🗺️" },
  { id: "tool_router", label: "Tool Router", icon: "🔀" },
  { id: "vision", label: "Vision", icon: "👁️" },
  { id: "neo4j", label: "Neo4j", icon: "🌐" },
  { id: "postgres", label: "PostgreSQL", icon: "🐘" },
  { id: "redis", label: "Redis", icon: "🔴" },
  { id: "hindsight", label: "Hindsight", icon: "🔮" },
];

// ---------------------------------------------------------------------------
// Main Dashboard component
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");

  const renderDashboardTab = useMemo(() => {
    const tabMap: Record<DashboardTab, () => React.ReactNode> = {
      overview: () => <DynamicSystemDashboard />,
      nervous: () => <DynamicNervousSystemPanel />,
      tools: () => <DynamicToolsPanel />,
      metabolism: () => <DynamicMetabolismPanel />,
      schema: () => <DynamicSchemaEvolutionPanel />,
      graph: () => <DynamicBiologicalGraph />,
      telemetry: () => <DynamicTelemetryPanel />,
      router: () => <DynamicModelRouterPanel />,
      axioms: () => <DynamicAxiomsPanel />,
      memory: () => <DynamicMemorySystemPanel />,
      skills: () => <DynamicSkillsPanel />,
      config: () => <DynamicConfigPanel />,
      keys: () => <DynamicKeysPanel />,
      mcp: () => <DynamicMcpPanel />,
      hooks: () => <DynamicHooksPanel />,
      logs: () => <DynamicLogsPanel />,
      scheduling: () => <DynamicSchedulingPanel />,
      settings: () => <DynamicSettingsPanel />,
      immune: () => <DynamicImmuneSystemPanel />,
      database: () => <DynamicDatabasePanel />,
      self_repair: () => <DynamicSelfRepairPanel />,
      thermal: () => <DynamicThermalPanel />,
      self_improvement: () => <DynamicSelfImprovementPanel />,
      planner: () => <DynamicPlannerPanel />,
      embedder: () => <DynamicEmbedderPanel />,
      inference: () => <DynamicInferencePanel />,
      context: () => <DynamicContextPanel />,
      context_curator: () => <DynamicContextCuratorPanel />,
      evaluation: () => <DynamicEvaluationPanel />,
      multi_agent: () => <DynamicMultiAgentOrchestratorPanel />,
      observability: () => <DynamicObservabilityPanel />,
      rag: () => <DynamicRagPanel />,
      rag_retriever: () => <DynamicRagRetrieverPanel />,
      repo_map: () => <DynamicRepoMapPanel />,
      tool_router: () => <DynamicToolRouterPanel />,
      vision: () => <DynamicVisionPanel />,
      neo4j: () => <DynamicNeo4jPanel />,
      postgres: () => <DynamicPostgresPanel />,
      redis: () => <DynamicRedisPanel />,
      hindsight: () => <DynamicHindsightPanel />,
    };
    return tabMap[activeTab];
  }, [activeTab]);

  return (
    <div className="flex-1 overflow-y-auto flex flex-col min-h-screen">
      {/* Dashboard tab bar */}
      <div className="flex items-center gap-1 px-4 py-2 border-b border-border overflow-x-auto bg-bg-2">
        {DASHBOARD_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all whitespace-nowrap ${
              activeTab === tab.id
                ? "bg-accent text-white shadow-sm"
                : "text-text-muted hover:text-text-primary hover:bg-surface-hover"
            }`}
          >
            <span>{tab.icon}</span>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>
      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-4">
        {renderDashboardTab()}
      </div>
    </div>
  );
}
