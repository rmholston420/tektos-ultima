/**
 * Tektos-Ultima v1 — Main Layout Shell (Hermes GUI Parity)
 *
 * Layout structure (mirrors Hermes Agent desktop GUI):
 *   ┌─────────────────────────────────────────────────────────────┐
 *   │ Sidebar (session management) │ ChatPage (xterm.js terminal) │
 *   │                              │ ┌──────────────────────────┐ │
 *   │  • Session list              │ │ Terminal area            │ │
 *   │  • Theme selector            │ │                          │ │
 *   │  • Nav (Chat/Dashboard)      │ │                          │ │
 *   │                              │ │                          │ │
 *   │                              │ │ ┌──────────────────────┐ │ │
 *   │                              │ │ │ ChatSidebar          │ │ │
 *   │                              │ │ │ • Model picker       │ │ │
 *   │                              │ │ │ • Connection badge   │ │ │
 *   │                              │ │ │ • Status strip       │ │ │
 *   │                              │ │ │ • Session list       │ │ │
 *   │                              │ │ │ • Footer             │ │ │
 *   │                              │ │ └──────────────────────┘ │ │
 *   └─────────────────────────────────────────────────────────────┘
 */

"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import { ProtocolClient, EventType, type WSEnvelopeClient } from "@/lib/protocol";
import { SessionStore, type SessionSnapshot, type SessionEvent } from "@/lib/session-store";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { themeStore, type ThemeName } from "@/lib/theme-store";

// Dynamic imports for client-only components (SSR-safe)
const DynamicBiologicalGraph = dynamic(() => import("@/components/graphs/BiologicalGraph").then((m) => m.BiologicalGraph), { ssr: false });
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

// Chat components (Hermes GUI parity) — dynamic import to avoid SSR issues with @assistant-ui/react
const DynamicChatPage = dynamic(() => import("@/components/chat/ChatPage").then((m) => m.default), { ssr: false });
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatSessionList } from "@/components/chat/ChatSessionList";
import { SidebarStatusStrip } from "@/components/chat/SidebarStatusStrip";
import { SidebarFooter } from "@/components/chat/SidebarFooter";

// ---------------------------------------------------------------------------
// Page types
// ---------------------------------------------------------------------------

type PageType = "chat" | "dashboard";
type DashboardTab = "overview" | "nervous" | "tools" | "metabolism" | "schema" | "graph" | "telemetry" | "router" | "axioms" | "memory" | "skills" | "config" | "keys" | "mcp" | "hooks" | "logs" | "scheduling" | "settings" | "immune" | "database" | "self_repair" | "thermal" | "self_improvement" | "planner";

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
];

// ---------------------------------------------------------------------------
// Main App component
// ---------------------------------------------------------------------------

export default function App() {
  const [protocolClient] = useState(() => new ProtocolClient());
  const [sessionStore] = useState(() => new SessionStore(protocolClient));
  const [activeSession, setActiveSession] = useState<SessionSnapshot | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [connectionState, setConnectionState] = useState<"disconnected" | "connecting" | "connected" | "reconnecting">("disconnected");
  const [activePage, setActivePage] = useState<PageType>("chat");
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const [activeModel, setActiveModel] = useState("Qwen_Qwen3.6-35B-A3B-Q4_K_M");
  const [visionAvailable, setVisionAvailable] = useState(false);
  const [visionModel, setVisionModel] = useState("");
  const [hasHydrated, setHasHydrated] = useState(false);
  const [clientTheme, setClientTheme] = useState<ThemeName>("abyss");
  const [chatPanelCollapsed, setChatPanelCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("hermes-chat-panel-collapsed") === "1";
  });

  // -------------------------------------------------------------------
  // Connection management
  // -------------------------------------------------------------------

  // Track whether we've already connected the WebSocket
  const wsConnectedRef = useRef(false);

  useEffect(() => {
    setHasHydrated(true);
    setClientTheme(themeStore.get());
    protocolClient.onStateChange((state) => setConnectionState(state.state));

    // Auto-create a session on load
    fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    }).then(async (r) => {
      if (!r.ok) {
        console.error('Session creation failed:', r.status, r.statusText);
        return;
      }
      const data = await r.json();
      
      const session: SessionSnapshot = {
        id: data.id,
        title: data.title || 'New Session',
        model: data.model || 'Qwen_Qwen3.6-35B-A3B-Q4_K_M',
        cwd: data.cwd,
        status: data.status || 'created',
        is_active: true,
        is_archived: false,
        is_failed: false,
        current_seq: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      
      console.log('Auto-session created:', session.id);
      setActiveSession(session);
      protocolClient.setSessionId(session.id);
    }).catch((err) => {
      console.error('Auto-session creation error:', err);
    });

    // Check vision status
    fetch('http://localhost:8020/api/vision/status', { cache: 'no-store' })
      .then((r) => r.json())
      .then((data) => {
        if (data.initialized) {
          setVisionAvailable(true);
          setVisionModel(data.model || "");
        }
      })
      .catch(() => {});

    return () => { protocolClient.disconnect(); };
  }, []);

  // Connect WebSocket when activeSession.id is available
  useEffect(() => {
    if (activeSession?.id && !wsConnectedRef.current) {
      wsConnectedRef.current = true;
      console.log('Connecting WebSocket for session:', activeSession.id);
      protocolClient.setSessionId(activeSession.id);
      protocolClient.connect();
    }
  }, [activeSession?.id, protocolClient]);

  // -------------------------------------------------------------------
  // Reconnect WS when session changes
  // -------------------------------------------------------------------

  // -------------------------------------------------------------------
  // Session management
  // -------------------------------------------------------------------

  useEffect(() => {
    sessionStore.on("created", (event: SessionEvent) => {
      if (event.type === "created") {
        setActiveSession(event.session);
        protocolClient.setSessionId(event.session.id);
      }
    });

    sessionStore.on("updated", (event: SessionEvent) => {
      if (event.type === "updated") {
        setActiveSession((prev) => {
          if (prev?.id === event.session.id) return { ...prev, ...event.session };
          return prev;
        });
      }
    });

    sessionStore.on("deleted", (event: SessionEvent) => {
      if (event.type === "deleted" && activeSession?.id === event.session_id) {
        setActiveSession(null);
        protocolClient.setSessionId("");
      }
    });

    sessionStore.on("model_changed", (event: SessionEvent) => {
      if (event.type === "model_changed" && activeSession?.id === event.session_id) {
        setActiveModel(event.model);
        setActiveSession(prev => prev ? { ...prev, model: event.model } : prev);
      }
    });
  }, [sessionStore, protocolClient, activeSession]);

  // -------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      sessionStore.getSession(sessionId).then((session) => {
        if (session) {
          setActiveSession(session);
          protocolClient.setSessionId(sessionId);
        }
      });
    },
    [sessionStore, protocolClient]
  );

  const handleCreateSession = useCallback(() => {
    fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    }).then(async (r) => {
      if (!r.ok) throw new Error(`Failed to create session: ${r.status}`);
      const data = await r.json();
      const session: SessionSnapshot = {
        id: data.id,
        title: data.title || 'New Session',
        model: data.model || 'Qwen_Qwen3.6-35B-A3B-Q4_K_M',
        cwd: data.cwd,
        status: data.status || 'created',
        is_active: false,
        is_archived: false,
        is_failed: false,
        current_seq: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setActiveSession(session);
      setActiveModel(session.model);
      protocolClient.setSessionId(session.id);
    }).catch((err) => {
      console.error('Failed to create session:', err);
    });
  }, [protocolClient]);

  const handleModelChange = useCallback(async (modelId: string) => {
    if (!activeSession?.id) return;
    try {
      const res = await fetch(`/api/sessions/${activeSession.id}/model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId }),
      });
      if (!res.ok) throw new Error(`Model switch failed: ${res.status}`);
      const data = await res.json();
      setActiveModel(data.model);
      setActiveSession(prev => prev ? { ...prev, model: data.model } : prev);
    } catch (err) {
      console.error('Failed to switch model:', err);
    }
  }, [activeSession]);

  // -------------------------------------------------------------------
  // Dashboard tab renderer
  // -------------------------------------------------------------------

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
    };
    return tabMap[activeTab];
  }, [activeTab]);

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------

  return (
    <div className="shell">
      {/* Left sidebar — session management */}
      <Sidebar
        sessionStore={sessionStore}
        activeSessionId={activeSession?.id ?? null}
        onSelectSession={handleSelectSession}
        onCreateSession={handleCreateSession}
        theme={hasHydrated ? clientTheme : "abyss"}
        collapsed={sidebarCollapsed}
        onToggleCollapsed={() => setSidebarCollapsed(!sidebarCollapsed)}
        activePage={activePage}
        onNavigate={setActivePage}
      />

      {/* Main content area */}
      <div className="shell-main">
        {/* Header */}
        <header className="shell-header">
          <div className="flex items-center gap-3">
            <h1 className="text-sm font-semibold text-text-primary">
              {activePage === "chat" ? (activeSession?.title || "Tektos") : "System Dashboard"}
            </h1>
            {activePage === "chat" && activeSession && (
              <span className="text-xs text-text-muted truncate max-w-[12rem]">
                {activeSession.model?.split('/').pop()?.split('-').slice(0, 2).join('-')}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Connection status */}
            <div className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${
                connectionState === "connected" ? "bg-status-success" :
                connectionState === "connecting" || connectionState === "reconnecting" ? "bg-status-warning animate-pulse" :
                "bg-status-error"
              }`} />
              <span className="text-xs text-text-muted capitalize">
                {connectionState}
              </span>
            </div>

            {/* Page toggle */}
            <div className="flex items-center gap-1 bg-bg-3 rounded-lg p-0.5">
              <button onClick={() => setActivePage("chat")}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                  activePage === "chat" ? "bg-accent text-white shadow-sm" : "text-text-muted hover:text-text-primary"
                }`}>Chat</button>
              <button onClick={() => setActivePage("dashboard")}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                  activePage === "dashboard" ? "bg-accent text-white shadow-sm" : "text-text-muted hover:text-text-primary"
                }`}>Dashboard</button>
            </div>
          </div>
        </header>

        {/* Page content */}
        {activePage === "chat" ? (
          <div className="flex-1 flex flex-col min-h-0">
            {!activeSession ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center space-y-4">
                  <h2 className="text-2xl font-semibold text-text-primary">Welcome to Tektos</h2>
                  <p className="text-sm text-text-muted">Create a session to start chatting</p>
                </div>
              </div>
            ) : (
              <>
                {/* Main terminal area */}
                <div className="flex-1 flex min-h-0">
                  <DynamicChatPage
                    activeSessionId={activeSession.id}
                    onSelectSession={handleSelectSession}
                    onCreateSession={handleCreateSession}
                    connectionState={connectionState}
                    activeModel={activeModel}
                    onModelChange={handleModelChange}
                    isActive={activePage === "chat"}
                    protocolClient={protocolClient}
                    sessionStore={sessionStore}
                  />
                </div>

                {/* Chat sidebar (right side) */}
                {!chatPanelCollapsed && (
                  <div className="w-80 border-l border-border/50 flex flex-col min-h-0">
                    <ChatSidebar
                      channel={activeSession.id}
                      profile=""
                      className="flex-shrink-0"
                    />
                    <div className="flex-1 min-h-0 overflow-y-auto">
                      <ChatSessionList
                        activeSessionId={activeSession.id}
                        profile=""
                        onPicked={handleSelectSession}
                        onNewChat={handleCreateSession}
                      />
                    </div>
                    <SidebarStatusStrip className="flex-shrink-0" />
                    <SidebarFooter className="flex-shrink-0" />
                  </div>
                )}
              </>
            )}
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto flex flex-col">
            {/* Dashboard tab bar */}
            <div className="flex items-center gap-1 px-4 py-2 border-b border-border overflow-x-auto">
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
        )}
      </div>
    </div>
  );
}
