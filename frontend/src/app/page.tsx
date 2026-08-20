/**
 * Tektos-Ultima v1 — Main Layout Shell (Streaming Architecture)
 *
 * Uses @assistant-ui/react primitives for streaming:
 * - TektosExternalStoreAdapter bridges WebSocket to the library
 * - useExternalStoreRuntime creates the runtime from the adapter
 * - AssistantRuntimeProvider wraps the chat UI
 * - ThreadPrimitive.Root + Viewport + Messages renders messages
 * - useAui().thread().state.isRunning for streaming state
 */

"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import { ProtocolClient, EventType, type WSEnvelopeClient } from "@/lib/protocol";
import { SessionStore, type SessionSnapshot, type SessionEvent } from "@/lib/session-store";
import { useExternalStoreRuntime, AssistantRuntimeProvider, type ExternalStoreAdapter, type ThreadMessage, type AppendMessage, type ExternalThreadQueueAdapter } from "@assistant-ui/react";
import { TektosExternalStoreAdapter, TektosExternalStoreAdapterWrapper } from "@/lib/tektos-store-adapter";
import { Sidebar } from "@/components/sidebar/Sidebar";
import { Composer } from "@/components/composer/Composer";
import { ThreadView } from "@/components/streaming/ThreadView";
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

// ---------------------------------------------------------------------------
// Page types
// ---------------------------------------------------------------------------

type PageType = "chat" | "dashboard";
type DashboardTab = "overview" | "nervous" | "tools" | "metabolism" | "schema" | "graph" | "telemetry" | "router" | "axioms" | "memory" | "skills" | "config" | "keys" | "mcp" | "hooks" | "logs" | "scheduling" | "settings";

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
  const [activeModel, setActiveModel] = useState("qwen3.6-35b-a3b-ud-q4_k_xl");
  const [visionAvailable, setVisionAvailable] = useState(false);
  const [visionModel, setVisionModel] = useState("");
  const [hasHydrated, setHasHydrated] = useState(false);

  // Streaming adapter + runtime
  // Persistent base adapter holds all message data.
  // A wrapper is memoized and recreated via useMemo keyed on adapterVersion,
  // giving the runtime a new object reference so __internal_setAdapter
  // bypasses its === short-circuit and re-reads fresh messages.
  const adapterRef = useRef(new TektosExternalStoreAdapter());
  const [adapterVersion, setAdapterVersion] = useState(0);
  
  const adapter = useMemo(
    () => new TektosExternalStoreAdapterWrapper(adapterRef.current),
    [adapterVersion]
  );
  
  const runtime = useExternalStoreRuntime(adapter);

  // Stream elapsed timer
  const streamStart = useRef<number | null>(null);
  const [streamElapsed, setStreamElapsed] = useState(0);

  // Update elapsed timer during streaming
  useEffect(() => {
    const interval = setInterval(() => {
      if (streamStart.current) {
        setStreamElapsed(Math.floor((Date.now() - streamStart.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // -------------------------------------------------------------------
  // Connection management
  // -------------------------------------------------------------------

  useEffect(() => {
    setHasHydrated(true);

    // Auto-create a session on load — direct API call to backend
    let cancelled = false;
    
    // Create session directly via backend (bypasses Next.js dev proxy)
    fetch('http://localhost:8020/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    }).then(async (r) => {
      if (cancelled) return;
      if (!r.ok) {
        console.error('Session creation failed:', r.status, r.statusText);
        return;
      }
      const data = await r.json();
      
      // Build session snapshot from API response
      const session: SessionSnapshot = {
        id: data.id,
        title: data.title || 'New Session',
        model: data.model || 'qwen3.6-35b-a3b-ud-q4_k_xl',
        cwd: data.cwd,
        status: data.status || 'created',
        is_active: true,
        is_archived: false,
        is_failed: false,
        current_seq: 0,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      
      console.log('Auto-session created:', session.id, 'is_active:', session.is_active);
      setActiveSession(session);
      protocolClient.setSessionId(session.id);
    }).catch((err) => {
      if (!cancelled) {
        console.error('Auto-session creation error:', err);
      }
    });

    protocolClient.onStateChange((state) => setConnectionState(state.state));

    const checkVision = () => {
      if (cancelled) return;
      fetch('http://localhost:8020/api/vision/status', { cache: 'no-store' })
        .then((r) => r.json())
        .then((data) => {
          if (cancelled) return;
          if (data.initialized) {
            setVisionAvailable(true);
            setVisionModel(data.model || "");
          }
        })
        .catch(() => {});
    };

    checkVision();

    return () => { cancelled = true; protocolClient.disconnect(); };
  }, [protocolClient]);

  // -------------------------------------------------------------------
  // Reconnect WS when session changes — no delay
  // -------------------------------------------------------------------

  useEffect(() => {
    if (activeSession?.id) {
      protocolClient.setSessionId(activeSession.id);
      protocolClient.connect();
    }
  }, [activeSession?.id, protocolClient]);

  // -------------------------------------------------------------------
  // Event handling from backend (streaming-aware via adapter)
  // -------------------------------------------------------------------

  useEffect(() => {
    const handler = (envelope: WSEnvelopeClient) => {
      switch (envelope.event_type) {
        case EventType.ASSISTANT_DELTA: {
          const text = envelope.payload.text as string;
          if (text) {
            adapterRef.current.addDelta(text);
            if (streamStart.current === null) {
              streamStart.current = Date.now();
            }
            setAdapterVersion(v => v + 1);
          }
          break;
        }
        case EventType.ASSISTANT_COMPLETED: {
          adapterRef.current.completeMessage();
          streamStart.current = null;
          setAdapterVersion(v => v + 1);
          break;
        }
        default:
          break;
      }
    };

    protocolClient.on("*", handler);
    return () => {
      protocolClient.off("*", handler);
    };
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

  const handleSendMessage = useCallback(
    async (message: string) => {
      if (!activeSession) return;
      await adapterRef.current.sendMessage(message);
      protocolClient.sendPrompt(message, { model: activeSession.model, cwd: activeSession.cwd });
      setAdapterVersion(v => v + 1);
    },
    [activeSession, protocolClient]
  );

  const handleInterrupt = useCallback(() => {
    protocolClient.sendInterrupt();
    adapterRef.current.interrupt();
    streamStart.current = null;
    setAdapterVersion(v => v + 1);
  }, [protocolClient]);

  const handleSelectSession = useCallback(
    (sessionId: string) => {
      sessionStore.getSession(sessionId).then((session) => {
        if (session) {
          setActiveSession(session);
          protocolClient.setSessionId(sessionId);
          streamStart.current = null;
        }
      });
    },
    [sessionStore, protocolClient]
  );

  const handleAttachFiles = useCallback((files: File[]) => {
    if (!files.length || !activeSession?.id) return;
    
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    
    fetch(`/api/sessions/${activeSession.id}/attach`, {
      method: 'POST',
      body: formData,
    }).then(res => {
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      return res.json();
    }).then(data => {
      console.log('Files attached:', data);
    }).catch(err => {
      console.error('File upload error:', err);
    });
  }, [activeSession?.id]);

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
        model: data.model || 'qwen3.6-35b-a3b-ud-q4_k_xl',
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

  const handleVisionAnalyze = useCallback(async (imageBase64: string, prompt: string) => {
    if (!activeSession?.id) return;
    try {
      const res = await fetch('http://localhost:8020/api/vision/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: activeSession.id,
          image_base64: imageBase64.split(',')[1],
          prompt: prompt,
          model: visionModel,
        }),
      });
      if (!res.ok) throw new Error(`Vision analyze failed: ${res.status}`);
      const data = await res.json();
      await adapterRef.current.sendMessage(`[Vision: ${data.model}]\n${data.text}`);
      setAdapterVersion(v => v + 1);
    } catch (err) {
      console.error('Vision analyze error:', err);
    }
  }, [activeSession, visionModel]);

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
            <h1 className="text-sm font-semibold text-text-primary">
              {activePage === "chat" ? (activeSession?.title || "Tektos") : "System Dashboard"}
            </h1>
            {activePage === "chat" && activeSession && (
              <span className="text-xs text-text-muted truncate max-w-[12rem]">{activeSession.model?.split('/').pop()?.split('-').slice(0, 2).join('-')}</span>
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
                {connectionState}
              </span>
            </div>

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

        {activePage === "chat" ? (
          <AssistantRuntimeProvider runtime={runtime}>
            {!activeSession ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center space-y-4">
                  <h2 className="text-2xl font-semibold text-text-primary">Welcome to Tektos</h2>
                  <p className="text-sm text-text-muted">Create a session to start chatting</p>
                </div>
              </div>
            ) : (
              <>
                <ThreadView />
                <div className="border-t border-border bg-surface/80 backdrop-blur-sm">
                  <Composer
                    isActive={!!activeSession}
                    sessionId={activeSession?.id}
                    adapter={adapterRef.current}
                    model={activeModel}
                    onModelChange={handleModelChange}
                    connectionState={connectionState}
                    onSendMessage={handleSendMessage}
                    onInterrupt={handleInterrupt}
                    onAttachFiles={handleAttachFiles}
                    visionAvailable={visionAvailable}
                    visionModel={visionModel}
                    onVisionAnalyze={handleVisionAnalyze}
                    onNewSession={handleCreateSession}
                  />
                </div>
              </>
            )}
          </AssistantRuntimeProvider>
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
