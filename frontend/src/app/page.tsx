/**
 * Tektos-Ultima v1 — Main Layout Shell
 *
 * Full app layout: Sidebar + content area with theme management.
 * Three themes: Abyss (dark), Temple (Tibetan), Clarity (minimalist).
 * Organic, biological design with flowing gradients and breathing animations.
 * Dashboard with biological system graph, telemetry, and all management panels.
 */

"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import { ProtocolClient, EventType, type WSEnvelopeClient } from "@/lib/protocol";
import { SessionStore, type SessionSnapshot, type SessionEvent } from "@/lib/session-store";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { Transcript, type TranscriptEvent } from "@/components/transcript/Transcript";
import { Composer } from "@/components/composer/Composer";
import { themeStore, type ThemeName } from "@/lib/theme-store";

// Dynamic imports for client-only components (SSR-safe)
const DynamicBiologicalGraph = dynamic(() => import("@/components/graphs/BiologicalGraph").then((m) => m.BiologicalGraph), { ssr: false });
const DynamicSystemDashboard = dynamic(() => import("@/components/panels/SystemDashboard").then((m) => m.SystemDashboard), { ssr: false });
const DynamicTelemetryPanel = dynamic(() => import("@/components/panels/TelemetryPanel").then((m) => m.TelemetryPanel), { ssr: false });
const DynamicModelRouterPanel = dynamic(() => import("@/components/panels/ModelRouterPanel").then((m) => m.ModelRouterPanel), { ssr: false });
const DynamicAxiomsPanel = dynamic(() => import("@/components/panels/AxiomsPanel").then((m) => m.AxiomsPanel), { ssr: false });
const DynamicMemorySystemPanel = dynamic(() => import("@/components/panels/MemorySystemPanel").then((m) => m.MemorySystemPanel), { ssr: false });
const DynamicSkillsPanel = dynamic(() => import("@/components/panels/SkillsPanel").then((m) => m.SkillsPanel), { ssr: false });
const DynamicConfigPanel = dynamic(() => import("@/components/panels/ConfigPanel").then((m) => m.ConfigPanel), { ssr: false });
const DynamicKeysPanel = dynamic(() => import("@/components/panels/KeysPanel").then((m) => m.KeysPanel), { ssr: false });
const DynamicMcpPanel = dynamic(() => import("@/components/panels/McpPanel").then((m) => m.McpPanel), { ssr: false });
const DynamicHooksPanel = dynamic(() => import("@/components/panels/HooksPanel").then((m) => m.HooksPanel), { ssr: false });
const DynamicLogsPanel = dynamic(() => import("@/components/panels/LogsPanel").then((m) => m.LogsPanel), { ssr: false });
const DynamicSchedulingPanel = dynamic(() => import("@/components/panels/SchedulingPanel").then((m) => m.SchedulingPanel), { ssr: false });

// ---------------------------------------------------------------------------
// Page types
// ---------------------------------------------------------------------------

type PageType = "chat" | "dashboard";
type DashboardTab = "overview" | "graph" | "telemetry" | "router" | "axioms" | "memory" | "skills" | "config" | "keys" | "mcp" | "hooks" | "logs" | "scheduling";

const DASHBOARD_TABS: { id: DashboardTab; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "◈" },
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
];

// ---------------------------------------------------------------------------
// Main App component
// ---------------------------------------------------------------------------

export default function App() {
  const [protocolClient] = useState(() => new ProtocolClient());
  const [sessionStore] = useState(() => new SessionStore(protocolClient));
  const [activeSession, setActiveSession] = useState<SessionSnapshot | null>(null);
  const [transcriptEvents, setTranscriptEvents] = useState<TranscriptEvent[]>([]);
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [connectionState, setConnectionState] = useState<"disconnected" | "connecting" | "connected" | "reconnecting">("disconnected");
  const [activePage, setActivePage] = useState<PageType>("chat");
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");

  const streamBuffer = useRef("");

  // -------------------------------------------------------------------
  // Connection management
  // -------------------------------------------------------------------

  useEffect(() => {
    protocolClient.onStateChange((state) => setConnectionState(state.state));
    return () => { protocolClient.disconnect(); };
  }, [protocolClient]);

  // -------------------------------------------------------------------
  // Event handling from backend
  // -------------------------------------------------------------------

  useEffect(() => {
    protocolClient.on("*", (envelope: WSEnvelopeClient) => {
      const event: TranscriptEvent = {
        type: mapEventType(envelope.event_type),
        session_id: envelope.session_id,
        seq: envelope.seq ?? 0,
        payload: envelope.payload,
        timestamp: envelope.timestamp ?? new Date().toISOString(),
      };

      switch (envelope.event_type) {
        case EventType.ASSISTANT_DELTA: {
          const text = envelope.payload.text as string;
          if (text) {
            streamBuffer.current += text;
            setStreamingContent(streamBuffer.current);
            setIsStreaming(true);
          }
          break;
        }
        case EventType.ASSISTANT_COMPLETED: {
          if (streamBuffer.current) {
            setTranscriptEvents((prev) => [...prev, event]);
            streamBuffer.current = "";
            setStreamingContent("");
          }
          setIsStreaming(false);
          break;
        }
        default:
          setTranscriptEvents((prev) => [...prev, event]);
      }
    });
  }, [protocolClient]);

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
        setTranscriptEvents([]);
        protocolClient.setSessionId("");
      }
    });
  }, [sessionStore, protocolClient, activeSession]);

  // -------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------

  const handleSendMessage = useCallback(
    (message: string) => {
      if (!activeSession) return;
      setTranscriptEvents((prev) => [...prev, {
        type: "message", session_id: activeSession.id, seq: 0,
        payload: { text: message }, timestamp: new Date().toISOString(),
      }]);
      protocolClient.sendPrompt(message, { model: activeSession.model, cwd: activeSession.cwd });
    },
    [activeSession, protocolClient]
  );

  const handleInterrupt = useCallback(() => {
    protocolClient.sendInterrupt();
    if (streamBuffer.current) {
      setTranscriptEvents((prev) => [...prev, {
        type: "message", session_id: activeSession?.id ?? "", seq: 0,
        payload: { text: streamBuffer.current }, timestamp: new Date().toISOString(),
      }]);
      streamBuffer.current = "";
      setStreamingContent("");
    }
    setIsStreaming(false);
  }, [protocolClient, activeSession]);

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      sessionStore.getSession(sessionId).then((session) => {
        if (session) {
          setActiveSession(session);
          protocolClient.setSessionId(sessionId);
          fetch(`/api/sessions/${sessionId}/events`)
            .then((res) => res.json())
            .then((data) => {
              setTranscriptEvents((data.events || []).map((e: any) => ({
                type: mapEventType(e.type), session_id: e.session_id,
                seq: e.seq ?? 0, payload: e.payload ?? {},
                timestamp: e.timestamp ?? new Date().toISOString(),
              })));
              setStreamingContent("");
              setIsStreaming(false);
            })
            .catch(() => setTranscriptEvents([]));
        }
      });
    },
    [sessionStore, protocolClient]
  );

  const handleAttachFiles = useCallback((files: File[]) => {
    // TODO: Handle file attachment to session
    console.log("Files attached:", files.map(f => f.name));
  }, []);

  const handleCreateSession = useCallback(() => {
    sessionStore.createSession().then((session) => {
      setActiveSession(session);
      protocolClient.setSessionId(session.id);
      protocolClient.connect();
    });
  }, [sessionStore, protocolClient]);

  // -------------------------------------------------------------------
  // Dashboard tab renderer
  // -------------------------------------------------------------------

  const renderDashboardTab = useMemo(() => {
    const tabMap: Record<DashboardTab, () => React.ReactNode> = {
      overview: () => <DynamicSystemDashboard />,
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
    };
    return tabMap[activeTab];
  }, [activeTab]);

  // -------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------

  return (
    <div className="shell">
      <Sidebar
        sessionStore={sessionStore}
        activeSessionId={activeSession?.id ?? null}
        onSelectSession={handleSelectSession}
        onCreateSession={handleCreateSession}
        theme={themeStore.get()}
        collapsed={sidebarCollapsed}
        onToggleCollapsed={() => setSidebarCollapsed(!sidebarCollapsed)}
        activePage={activePage}
        onNavigate={setActivePage}
      />

      <div className="shell-main">
        <header className="shell-header">
          <div className="flex items-center gap-3">
            {activePage === "chat" ? (
              <h1 className="text-sm font-semibold text-text-primary">
                {activeSession?.title ?? "Tektos-Ultima"}
              </h1>
            ) : (
              <h1 className="text-sm font-semibold text-text-primary">System Dashboard</h1>
            )}
            {activePage === "chat" && activeSession && (
              <span className="text-xs text-text-muted">{activeSession.model}</span>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${
                connectionState === "connected" ? "bg-status-success" :
                connectionState === "connecting" || connectionState === "reconnecting" ? "bg-status-warning animate-pulse" :
                "bg-status-error"
              }`} />
              <span className="text-xs text-text-muted capitalize">
                {connectionState === "reconnecting" ? "reconnecting" : connectionState}
              </span>
            </div>

            <div className="flex items-center gap-1 bg-bg-3 rounded-lg p-0.5">
              <button onClick={() => { setActivePage("chat"); }}
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

        {activePage === "chat" ? (
          <>
            <Transcript
              activeSession={activeSession}
              events={transcriptEvents}
              streamingContent={streamingContent}
              isStreaming={isStreaming}
              onSendMessage={handleSendMessage}
              onInterrupt={handleInterrupt}
            />
            <Composer
              isActive={!!activeSession}
              isStreaming={isStreaming}
              sessionId={activeSession?.id}
              model={activeSession?.model}
              onSendMessage={handleSendMessage}
              onInterrupt={handleInterrupt}
              onAttach={handleAttachFiles}
            />
          </>
        ) : (
          /* ───────── Dashboard ───────── */
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* Tab bar */}
            <div className="flex items-center gap-1 px-4 py-2 border-b border-border overflow-x-auto scrollbar-thin">
              {DASHBOARD_TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg whitespace-nowrap transition-all ${
                    activeTab === tab.id
                      ? "bg-accent/10 text-accent border border-accent/20"
                      : "text-text-muted hover:text-text-primary hover:bg-surface-active"
                  }`}
                >
                  <span className="text-sm">{tab.icon}</span>
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Panel content */}
            <div className="flex-1 overflow-auto p-6">
              <div className="max-w-6xl mx-auto">
                {renderDashboardTab()}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mapEventType(backendType: string): "message" | "tool" | "system" {
  if (backendType.startsWith("session.") || backendType.startsWith("system.")) return "system";
  if (backendType.startsWith("tool.")) return "tool";
  if (backendType.startsWith("assistant.")) return "message";
  return "message";
}
